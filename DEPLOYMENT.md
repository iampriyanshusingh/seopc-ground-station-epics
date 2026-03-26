# Deployment Guide — Project Argus

---

## Option 1: Local (WSL2 / Linux)

### Prerequisites

| Tool | Purpose |
|---|---|
| Docker Engine + Compose | All backend services |
| Go 1.21+ | Dashboard binary |
| GCC + `libraylib-dev` | GUI binary |
| tmux | Split terminal launcher |
| Python 3.10+ (optional) | Re-generating embeddings only |

**Install on Debian/Ubuntu:**
```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Go
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.zshrc && source ~/.zshrc

# Raylib (for GUI)
sudo apt install -y gcc libraylib-dev tmux

# (Optional) passwordless sudo for docker
echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/docker" | sudo tee /etc/sudoers.d/docker-nopasswd
```

### Clone and Run

```bash
git clone https://github.com/your-username/seopc-project.git
cd seopc-project

# Build the GUI binary (one time only)
cd gui && gcc main.c -o visualizer -lraylib -lm -lpthread -ldl && cd ..

# Build the dashboard binary (or just use 'go run main.go')
cd dashboard && go build -o dashboard . && cd ..

chmod +x launch.sh feed.sh
./launch.sh
```

> **WSL2 Note:** The `feed.sh` script uses `sudo docker cp` to inject tiles directly into the satellite container's filesystem. This is required because inotify events from WSL2 host writes to Docker volumes are not reliably propagated inside containers.

---

## Option 2: Cloud (Ubuntu 22.04 VM — AWS EC2 / GCP / Azure / Hetzner)

### Recommended Specs

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 4 vCPU | 8 vCPU |
| RAM | 8 GB | 16 GB |
| Disk | 30 GB | 60 GB |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

> The ViT model runs on CPU. GPU is not required. More CPU = faster inference.

### Step 1 — Provision the VM and SSH in

```bash
ssh ubuntu@<your-vm-ip>
```

### Step 2 — Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 golang gcc libraylib-dev tmux git

sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER && newgrp docker
```

### Step 3 — Clone and Configure

```bash
git clone https://github.com/your-username/seopc-project.git
cd seopc-project

# Build GUI and dashboard
cd gui && gcc main.c -o visualizer -lraylib -lm -lpthread -ldl && cd ..
cd dashboard && go build -o dashboard . && cd ..

chmod +x launch.sh feed.sh
```

### Step 4 — Open Firewall Ports (if needed)

| Port | Service |
|---|---|
| 9000 | MinIO API |
| 9001 | MinIO Console |
| 9090 | Prometheus |
| 3000 | Grafana |
| 19092 | Redpanda (external) |

On AWS EC2, add these to your Security Group inbound rules.

### Step 5 — Launch

```bash
./launch.sh
```

> **Cloud Note:** The Raylib GUI requires a display (X11/Wayland). On a headless cloud VM, either skip the GUI or use X11 forwarding:
> ```bash
> ssh -X ubuntu@<your-vm-ip>
> ```
> Or run with a virtual display:
> ```bash
> sudo apt install -y xvfb
> Xvfb :99 -screen 0 1024x768x24 &
> DISPLAY=:99 ./gui/visualizer
> ```

### Step 6 — Monitoring

- **Grafana**: `http://<your-vm-ip>:3000` (default login: admin/admin)
- **Prometheus**: `http://<your-vm-ip>:9090`
- **MinIO Console**: `http://<your-vm-ip>:9001` (admin/password123)

---

## Option 3: Headless Server (No GUI, CLI only)

If you only need the pipeline and dashboard (no Raylib window):

```bash
# Start only the backend services
sudo docker compose up -d redpanda minio postgis satellite processor

# Run the dashboard in your terminal
cd dashboard && go run main.go

# In another terminal, run the feeder
bash feed.sh
```

---

## Re-generating Embeddings

If you have a new tile dataset, regenerate the reference embeddings:

```bash
cd cv
pip install torch timm torchvision scikit-learn pillow pandas
python main.py   # Outputs embeddings.npy, lats.npy, lons.npy
cp embeddings.npy lats.npy lons.npy ../processor/
```

Then rebuild the processor container:
```bash
./launch.sh --rebuild
```

---

## Environment Variables

All configurable via `docker-compose.yml` or shell environment:

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BROKER` | `redpanda:9092` | Kafka/Redpanda broker address |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO endpoint |
| `MINIO_ROOT_USER` | `admin` | MinIO access key |
| `MINIO_ROOT_PASSWORD` | `password123` | MinIO secret key |
| `PG_CONN_STR` | see compose | PostgreSQL connection string |
| `WATCH_DIR` | `/downlink_buffer` | Satellite watch directory |
