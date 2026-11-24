# Deploying CareLine to a cloud VM (Azure)

1. **VM** – EU region (e.g. West Europe), Ubuntu 24.04, 2 vCPU / 4 GB RAM (e.g. `Standard_B2s`).
   4 GB is the lower bound because the Rasa model is loaded into memory.
2. **Network security group** – allow inbound 22 (SSH, ideally only your IP), 80 and 443. Nothing else;
   5005 and 5055 stay closed (they are not published by Compose either).
3. **DNS name** – in the VM's public IP settings set a DNS label, which gives
   `<label>.westeurope.cloudapp.azure.com` (needed for the Let's Encrypt certificate).
4. **Install Docker and get the code**
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
   sudo usermod -aG docker $USER && newgrp docker
   git clone <REPO_URL> careline && cd careline
   cp .env.example .env && sed -i "s/change-me/$(openssl rand -hex 32)/" .env
   docker compose up -d --build
   docker compose ps
   ```
5. **HTTPS** – stop the stack, obtain a certificate, and add a 443 server block to `docker/nginx.conf`:
   ```bash
   docker compose stop web
   sudo apt install -y certbot
   sudo certbot certonly --standalone -d <label>.westeurope.cloudapp.azure.com
   ```
   Mount `/etc/letsencrypt` read-only into the `web` service, publish `443:443`, redirect 80 → 443,
   and restrict CORS in `docker/rasa.Dockerfile` (`--cors "https://<label>.westeurope.cloudapp.azure.com"`).
   Then `docker compose up -d --build web`.
6. **Measure** – rerun the response-time script against `https://<label>.../webhooks/rest/webhook`.
7. **Screenshots** – VM overview, NSG inbound rules, `docker compose ps`, the chat in the browser (padlock).
8. **Stop the VM** (`Stop (deallocate)` in the portal) so it does not consume credit.
