#!/bin/bash
#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

echo "Running migrate..."
python manage.py migrate

echo "Loading initial data..."
python manage.py loaddata db_initial_data.json

# Check for existing records
exists=$(python manage.py shell -c "from sensordata.models import ResourceType; print(ResourceType.objects.count())" | tail -n 1)

if [ -z "$exists" ] || [ "$exists" -eq "0" ]; then
    echo "Loading lwm2m resource types data..."
    python manage.py loaddata db_initial_resource_types.json
else
    echo "lwm2m resource types data already loaded, skipping..."
fi

# Choosing gevent as the event loop for celery for significantly lower memory
# usage. The application is IO bound as it is waiting for ReST API responses.
#
# -P gevent -c 100: 100 concurrent workers
echo "Starting the Celery worker..."
celery -A core worker --loglevel=info -P gevent -c 100 &

echo "Starting the server..."
exec uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --workers "${DJANGO_WORKERS:-2}"
