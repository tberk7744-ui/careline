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
5. **HTTPS** – obtain a Let's Encrypt certificate (port 80 must be free), then start the stack with the HTTPS layer
   (`docker-compose.https.yml` + `docker/nginx.https.conf.template`: 80 → 443 redirect, TLS 1.2/1.3, HSTS,
   Rasa CORS limited to `https://$DOMAIN`):
   ```bash
   echo "DOMAIN=<ip-with-dashes>.sslip.io" >> .env
   docker compose stop web
   sudo apt install -y certbot
   sudo certbot certonly --standalone -d <ip-with-dashes>.sslip.io --agree-tos --register-unsafely-without-email \
     --pre-hook  "docker compose -f $PWD/docker-compose.yml stop web" \
     --post-hook "docker compose -f $PWD/docker-compose.yml -f $PWD/docker-compose.https.yml start web"
   docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build --wait
   ```
   The hooks let the certbot timer renew the certificate automatically.
6. **Measure** – rerun the response-time script against `https://<ip-with-dashes>.sslip.io/webhooks/rest/webhook`.
7. **Screenshots** – VM instances page, firewall rules, `docker compose ps`, the chat in the browser (padlock).
8. **Stop the VM** (`gcloud compute instances stop careline-vm --zone=europe-west1-b`) so it does not consume credit;
   release the static IP when finished (a reserved but unused IP is billed).
