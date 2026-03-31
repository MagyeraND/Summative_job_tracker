Job & Internship Tracker
A web app to search real job listings and track your applications. Live at http://3.87.239.83
APIs Used

Adzuna Jobs API — job listings
REST Countries API — country list and flags

Running Locally
bashgit clone https://github.com/MagyeraND/Summative_job_tracker.git
cd Summative_job_tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Create a .env file in the root folder:
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
SECRET_KEY=anything_random
Then run:
bashpython app.py
Open http://localhost:5000
Deployment
SSH into your server then run:
bashsudo apt update && sudo apt install python3-pip python3-venv nginx git -y
sudo git clone https://github.com/MagyeraND/Summative_job_tracker.git /var/www/job-tracker
cd /var/www/job-tracker
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
sudo venv/bin/pip install python-dotenv
Add your .env file with your keys, create a systemd service to run gunicorn, then configure Nginx to proxy port 80 to 127.0.0.1:5000.
Load Balancer
On Lb01, install Nginx and set up an upstream block pointing to Web01 and Web02 on port 80. Nginx will distribute traffic between them automatically.
