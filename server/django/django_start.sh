#!/bin/bash

logfile="logs/django_$(date +%Y-%m-%d_%H-%M-%S).log"
touch "$logfile"

# Start Django Server
python manage.py makemigrations 2>&1 | tee -a "$logfile"
python manage.py migrate 2>&1 | tee -a $logfile
python manage.py runserver 0.0.0.0:8000 2>&1 | tee -a "$logfile"
