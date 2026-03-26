import pandas as pd
import numpy as np
import torch
import timm
from PIL import Image
from torchvision import transforms
import os

def main():
    print("Loading ViT model for embedding extraction...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = timm.create_model("vit_base_patch16_224", pretrained=True)
    model.eval().to(device)

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
    ])

    df = pd.read_csv("tiles/labels.csv")
    
    embeddings = []
    lats = []
    lons = []
    valid_paths = []

    print(f"Processing {len(df)} tiles...")
    
    for i, row in df.iterrows():
        path = row["path"]
        lat = row["lat"]
        lon = row["lon"]
        
        if not os.path.exists(path):
            continue
            
        try:
            img = Image.open(path).convert("RGB")
            
            # Skip images that are completely black (common at the edges of satellite swaths)
            extrema = img.getextrema()
            if sum([ex[1] for ex in extrema]) == 0: 
                continue
                
            x = transform(img).unsqueeze(0).to(device)
            with torch.no_grad():
                features = model.forward_features(x)
            
            # Normalize embedding
            emb = features[:, 0, :]
            emb = emb / emb.norm(dim=1, keepdim=True)
            
            embeddings.append(emb.squeeze().cpu().numpy())
            lats.append(lat)
            lons.append(lon)
            valid_paths.append(path)
            
        except Exception as e:
            print(f"Failed {path}: {e}")
            
        if (i+1) % 50 == 0:
            print(f"Computed embeddings for {i+1} tiles...")

    # Save the numpy arrays required by processor/worker.py
    print("Saving embeddings.npy, lats.npy, lons.npy...")
    np.save("embeddings.npy", np.array(embeddings))
    np.save("lats.npy", np.array(lats))
    np.save("lons.npy", np.array(lons))
    
    # Save test CSV for cv/main.py
    filtered_df = pd.DataFrame({"path": valid_paths, "lat": lats, "lon": lons})
    filtered_df.to_csv("tiles/labels_clustered.csv", index=False)
    
    print(f"Success! Final valid tiles encoded: {len(valid_paths)}")

if __name__ == "__main__":
    main()
