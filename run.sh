#!/bin/bash
cd /home/server/website
source /home/server/website/.venv/bin/activate
sudo gunicorn -b 0.0.0.0:80 app:app
