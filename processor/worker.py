import json
import os
import time
import cv2
import numpy as np
from kafka import KafkaConsumer
from minio import Minio
import psycopg2
from io import BytesIO
from ultralytics import YOLO

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "127.0.0.1:19092")
TOPIC_NAME = "eo-events"
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "password123")
SOURCE_BUCKET = "satellite-raw"
DEST_BUCKET = "satellite-processed"
LOCAL_SYNC_PATH = "../local_sync/latest_processed.jpg"
PG_CONN_STR = os.getenv("PG_CONN_STR", "dbname=seopc_metadata user=admin password=password123 host=localhost port=5432")

def main():
    print("Starting Argus Processing Worker (YOLOv8)...")
    
    # Load Model (will download if missing)
    print("Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")
    print("Model loaded.")

    # 1. Connect to MinIO
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    if not minio_client.bucket_exists(DEST_BUCKET):
        try:
            minio_client.make_bucket(DEST_BUCKET)
            print(f"Created bucket: {DEST_BUCKET}")
        except Exception:
            pass 

    # 2. Connect to Postgres
    try:
        conn = psycopg2.connect(PG_CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processing_logs (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                processed_at TIMESTAMPTZ DEFAULT NOW(),
                latency_ms INTEGER,
                detections TEXT
            );
        """)
        # Check if detections column exists (migration for upgrade)
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='processing_logs' AND column_name='detections';")
        if not cur.fetchone():
            cur.execute("ALTER TABLE processing_logs ADD COLUMN detections TEXT;")
            print("Migrated DB: Added 'detections' column.")
            
        print("Connected to Postgres.")
    except Exception as e:
        print(f"Postgres connection failed: {e}")
        return

    # 3. Connect to Kafka (with retry)
    consumer = None
    retries = 30
    while retries > 0:
        try:
            print(f"Connecting to Kafka at {KAFKA_BROKER}...")
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=[KAFKA_BROKER],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print(f"Connected to Kafka! Listening on {TOPIC_NAME}...")
            break
        except Exception as e:
            print(f"Kafka connection failed: {e}. Retrying... ({retries} left)")
            time.sleep(2)
            retries -= 1
    
    if not consumer:
        print("Could not connect to Kafka.")
        return

    os.makedirs(os.path.dirname(LOCAL_SYNC_PATH), exist_ok=True)

    for message in consumer:
        try:
            start_time = time.time()
            data = message.value
            filename = data.get("file")
            print(f"Processing: {filename}")

            # Download
            response = minio_client.get_object(SOURCE_BUCKET, filename)
            file_data = response.read()
            response.close()
            response.release_conn()

            # Decode
            nparr = np.frombuffer(file_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                continue

            # Run / Inference
            results = model(img)
            
            # Draw boxes
            res_plotted = results[0].plot()
            
            # Count detections
            detection_summary = {}
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                detection_summary[label] = detection_summary.get(label, 0) + 1
            
            summary_str = json.dumps(detection_summary)
            print(f"Detections: {summary_str}")

            # Encode
            _, buffer = cv2.imencode('.jpg', res_plotted)
            processed_data = BytesIO(buffer)

            # Upload
            minio_client.put_object(
                DEST_BUCKET,
                filename,
                processed_data,
                len(buffer),
                content_type="image/jpeg"
            )

            # Local Save (Atomic write for GUI)
            temp_path = LOCAL_SYNC_PATH + ".tmp"
            with open(temp_path, "wb") as f:
                f.write(buffer)
            os.replace(temp_path, LOCAL_SYNC_PATH) # Atomic move prevents partial reads

            # Log
            latency = int((time.time() - start_time) * 1000)
            cur.execute(
                "INSERT INTO processing_logs (filename, latency_ms, detections) VALUES (%s, %s, %s)",
                (filename, latency, summary_str)
            )
            print(f"Finished {filename} in {latency}ms")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
