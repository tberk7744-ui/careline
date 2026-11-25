# Deploying CareLine to a cloud VM (Google Cloud)

1. **VM** – Compute Engine, EU region `europe-west1`, Ubuntu 24.04 LTS, `e2-medium` (2 vCPU / 4 GB RAM), 30 GB disk.
   4 GB is the lower bound because the Rasa model is loaded into memory (the free `e2-micro` is too small).
   ```bash
   gcloud compute instances create careline-vm --zone=europe-west1-b --machine-type=e2-medium \
     --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud --boot-disk-size=30GB \
     --tags=http-server,https-server
   ```
2. **Firewall** – the default VPC allows 22 (SSH; ideally restrict to your IP). The `http-server` / `https-server`
   tags open 80 and 443 (tick "Allow HTTP/HTTPS traffic" in the console, or create the rules if missing).
   Nothing else; 5005 and 5055 stay closed (they are not published by Compose either).
3. **Address** – promote the external IP to a static address. GCP does not give a DNS label, so use
   `<ip-with-dashes>.sslip.io` (e.g. `34-77-12-5.sslip.io`), which resolves to the IP and works with Let's Encrypt.
4. **Install Docker and get the code** (`gcloud compute ssh careline-vm --zone=europe-west1-b`)
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
   sudo usermod -aG docker $USER && newgrp docker
   git clone https://github.com/tberk7744-ui/careline.git careline && cd careline
   cp .env.example .env && sed -i "s/change-me/$(openssl rand -hex 32)/" .env
   docker compose up -d --build
   docker compose ps
   ```
5. **HTTPS** – stop the web service, obtain a certificate, and add a 443 server block to `docker/nginx.conf`:
   ```bash
   docker compose stop web
   sudo apt install -y certbot
   sudo certbot certonly --standalone -d <ip-with-dashes>.sslip.io
   ```
   Mount `/etc/letsencrypt` read-only into the `web` service, publish `443:443`, redirect 80 → 443,
   and restrict CORS in `docker/rasa.Dockerfile` (`--cors "https://<ip-with-dashes>.sslip.io"`).
   Then `docker compose up -d --build web`.
6. **Measure** – rerun the response-time script against `https://<ip-with-dashes>.sslip.io/webhooks/rest/webhook`.
7. **Screenshots** – VM instances page, firewall rules, `docker compose ps`, the chat in the browser (padlock).
8. **Stop the VM** (`gcloud compute instances stop careline-vm --zone=europe-west1-b`) so it does not consume credit;
   release the static IP when finished (a reserved but unused IP is billed).
