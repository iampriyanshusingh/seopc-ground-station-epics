FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for OpenCV and other libs
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch FIRST to avoid downloading 3GB+ of NVIDIA drivers
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Copy requirements (implicit or explicit)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY worker.py .

# Pre-download YOLOv8n model to bake it into image
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

CMD ["python", "worker.py"]
