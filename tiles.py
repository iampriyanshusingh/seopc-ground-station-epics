import os
import csv
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform
from PIL import Image

TILE_SIZE = 224
INPUT_DIR = "R2324DEC2025076186009400059PSANSTUC00GTDF"
BAND2_PATH = os.path.join(INPUT_DIR, "BAND2.tif")
BAND3_PATH = os.path.join(INPUT_DIR, "BAND3.tif")
BAND4_PATH = os.path.join(INPUT_DIR, "BAND4.tif")

OUTPUT_DIR = "tiles"
LABELS_CSV = os.path.join(OUTPUT_DIR, "labels.csv")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Opening TIF files...")
    
    with rasterio.open(BAND2_PATH) as src2, rasterio.open(BAND3_PATH) as src3, rasterio.open(BAND4_PATH) as src4:
        width = src2.width
        height = src2.height
        transform_matrix = src2.transform
        crs = src2.crs
        
        with open(LABELS_CSV, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "lat", "lon"])
            
            tile_count = 0
            for y in range(0, height - TILE_SIZE + 1, TILE_SIZE):
                for x in range(0, width - TILE_SIZE + 1, TILE_SIZE):
                    window = Window(x, y, TILE_SIZE, TILE_SIZE)
                    
                    # Center coordinates in pixel space
                    cx = x + TILE_SIZE / 2
                    cy = y + TILE_SIZE / 2
                    
                    # Transform pixel to map CRS
                    map_x, map_y = transform_matrix * (cx, cy)
                    
                    # Transform map CRS to WGS84 (Lat/Lon)
                    lon, lat = transform(crs, 'epsg:4326', [map_x], [map_y])
                    lat, lon = lat[0], lon[0]
                    
                    b2_data = src2.read(1, window=window)
                    b3_data = src3.read(1, window=window)
                    b4_data = src4.read(1, window=window)
                    
                    # Normalize to 0-255 based on 2nd and 98th percentiles to avoid outliers washing out image
                    b2_p2, b2_p98 = np.percentile(b2_data, (2, 98))
                    b3_p2, b3_p98 = np.percentile(b3_data, (2, 98))
                    b4_p2, b4_p98 = np.percentile(b4_data, (2, 98))
                    
                    b2_norm = np.clip((b2_data - b2_p2) / (b2_p98 - b2_p2 + 1e-5) * 255.0, 0, 255)
                    b3_norm = np.clip((b3_data - b3_p2) / (b3_p98 - b3_p2 + 1e-5) * 255.0, 0, 255)
                    b4_norm = np.clip((b4_data - b4_p2) / (b4_p98 - b4_p2 + 1e-5) * 255.0, 0, 255)
                    
                    # True RGB composite: R=B4, G=B3, B=B2
                    r = b4_norm.astype(np.uint8)
                    g = b3_norm.astype(np.uint8)
                    b = b2_norm.astype(np.uint8)
                    
                    rgb_array = np.stack([r, g, b], axis=-1)
                    img = Image.fromarray(rgb_array)
                    
                    filename = f"tile_{tile_count:04d}.jpg"
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    img.save(filepath, quality=95)
                    
                    # Write path relative to the root for main.py to find
                    writer.writerow([filepath, lat, lon])
                    tile_count += 1
                    
                    if tile_count % 100 == 0:
                        print(f"Processed {tile_count} tiles...")

    print(f"Extraction complete! Generated {tile_count} tiles and saved labels to {LABELS_CSV}.")
    print("Now you can run k.py to cluster them!")

if __name__ == "__main__":
    main()
