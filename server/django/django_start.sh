#!/bin/bash

# Ensure logs directory exists
mkdir -p logs

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

# Check for existing records
exists=$(echo "from sensordata.models import ResourceType; print(ResourceType.objects.count())" | python manage.py shell)

if [ "$exists" -eq "0" ]; then
    echo "Loading lwm2m resource types data..."
    python manage.py loaddata db_initial_resource_types.json 2>&1 | tee -a $logfile
else
    echo "lwm2m resource types data already loaded, skipping..."
fi

# Choosing gevent as the event loop for celery for significantly lower memory
# usage. The application is IO bound as it is waiting for ReST API responses.
#
# -P gevent -c 100: 100 concurrent workers
echo "Starting the Celery worker..."
celery -A server worker --loglevel=info -P gevent -c 100 2>&1 | tee -a "logs/celery_$(date +%Y-%m-%d_%H-%M-%S).log" &

echo "Starting the server..."
python manage.py runserver 0.0.0.0:8000 2>&1 | tee -a "$logfile"
