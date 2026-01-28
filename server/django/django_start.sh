#!/bin/bash

# Ensure logs directory exists
mkdir -p logs

logfile="logs/django_$(date +%Y-%m-%d_%H-%M-%S).log"
touch "$logfile"

# Start Django Server
# python manage.py collectstatic --noinput 2>&1 | tee -a "$logfile"
echo "Running migrate..."
python manage.py migrate 2>&1 | tee -a $logfile
echo "Loading initial data..."
python manage.py loaddata db_initial_data.json 2>&1 | tee -a $logfile

# Check for existing records
exists=$(python manage.py shell -c "from sensordata.models import ResourceType; print(ResourceType.objects.count())" | tail -n 1)

if [ -z "$exists" ] || [ "$exists" -eq "0" ]; then
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
celery -A core worker --loglevel=info -P gevent -c 100 2>&1 | tee -a "logs/celery_$(date +%Y-%m-%d_%H-%M-%S).log" &

echo "Starting the server..."
python manage.py runserver 0.0.0.0:8000 2>&1 | tee -a "$logfile"
