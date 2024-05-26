#!/bin/bash

logfile="logs/django_$(date +%Y-%m-%d_%H-%M-%S).log"
touch "$logfile"

# Start Django Server
# python manage.py collectstatic --noinput 2>&1 | tee -a "$logfile"
echo "Running makemigrations for sensordata..."
python manage.py makemigrations sensordata 2>&1 | tee -a "$logfile"
echo "Running migrate..."
python manage.py migrate 2>&1 | tee -a $logfile
echo "Loading initial data..."
python manage.py loaddata db_initial_data.json 2>&1 | tee -a $logfile
echo "Starting the server..."
python manage.py runserver 0.0.0.0:8000 2>&1 | tee -a "$logfile"
