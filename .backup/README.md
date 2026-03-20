# Job/Internship Tracker (Flask + External APIs)

## Purpose
A lightweight tracker to search real job/internship listings and save roles you want to follow up on.

## APIs used (with attribution)
- Adzuna Jobs API: https://developer.adzuna.com/
- REST Countries API: https://restcountries.com/

## Local setup

### 1) Create a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Set environment variables (do not commit keys)

PowerShell (temporary for this terminal session):

```powershell
$env:ADZUNA_APP_ID="YOUR_ID"
$env:ADZUNA_APP_KEY="YOUR_KEY"
```

### 4) Run

```powershell
python app.py
```

Open:
- http://127.0.0.1:5000

## Features (rubric-aligned)
- Search jobs by keyword + location
- Filter by country (country list from REST Countries)
- Sort by newest / salary / relevance
- Filter by full-time, contract type, minimum salary
- Save jobs to a local SQLite database and view/remove them
- Error handling for missing API keys, timeouts, and API failures

## Deployment notes (Web01 + Web02 + Lb01)

These steps assume Ubuntu servers with Nginx available.

### On Web01 and Web02

In the steps below:
- Replace `YOUR_DOMAIN_OR_IP` with the server IP/hostname.
- Replace paths/usernames as needed.

1) Install dependencies
- Python 3
- pip

Example:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx
```

2) Copy the repository to the server (clone from GitHub)

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

3) Create venv and install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4) Create a `systemd` service (recommended)

Create:

```bash
sudo nano /etc/systemd/system/jobtracker.service
```

Paste (edit `User=`, `WorkingDirectory=`, and keys):

```ini
[Unit]
Description=Job Tracker (Flask + Gunicorn)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/YOUR_REPO
Environment=ADZUNA_APP_ID=YOUR_ID
Environment=ADZUNA_APP_KEY=YOUR_KEY
Environment=SERVER_NAME=Web01
Environment=PORT=5000
ExecStart=/home/ubuntu/YOUR_REPO/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

On Web02, set `Environment=SERVER_NAME=Web02`.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable jobtracker
sudo systemctl restart jobtracker
sudo systemctl status jobtracker --no-pager
```

5) Configure Nginx reverse proxy

Create:

```bash
sudo nano /etc/nginx/sites-available/jobtracker
```

Paste:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:

```bash
sudo ln -sf /etc/nginx/sites-available/jobtracker /etc/nginx/sites-enabled/jobtracker
sudo nginx -t
sudo systemctl reload nginx
```

Test directly on each web server:

```bash
curl -i http://127.0.0.1/health
curl -I http://127.0.0.1/ | grep -i x-served-by
```

### On Lb01 (load balancer)

Install Nginx:

```bash
sudo apt update
sudo apt install -y nginx
```

Create:

```bash
sudo nano /etc/nginx/sites-available/jobtracker-lb
```

Paste (replace IPs/hostnames):

```nginx
upstream jobtracker_upstream {
    server WEB01_IP:80;
    server WEB02_IP:80;
}

server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://jobtracker_upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:

```bash
sudo ln -sf /etc/nginx/sites-available/jobtracker-lb /etc/nginx/sites-enabled/jobtracker-lb
sudo nginx -t
sudo systemctl reload nginx
```

Verify:
- Run multiple requests through the load balancer and confirm `X-Served-By` changes:

```bash
for i in {1..10}; do curl -sI http://LB01_IP/ | grep -i x-served-by; done
curl -s http://LB01_IP/health
```

## Security
- API keys are read from environment variables and are ignored via `.gitignore` if stored in a `.env` file.
- Do not commit secrets to GitHub.
