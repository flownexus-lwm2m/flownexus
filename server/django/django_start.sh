#!/bin/sh
#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
# Usage: django_start.sh <command>...
#   migrate  Apply migrations and load initial data into an empty database
#   web      Run the ASGI server
#   worker   Run the Celery worker
# Commands run in order; the last one replaces the shell.

set -eu

run() {
    case "$1" in
        migrate)
            python manage.py migrate --noinput
            users=$(python manage.py shell -c \
                "from django.contrib.auth import get_user_model; print(get_user_model().objects.count())" \
                | tail -n 1)
            if [ "$users" = "0" ]; then
                echo "Empty database, loading initial data..."
                python manage.py loaddata db_initial_data.json
            fi
            python manage.py load_initial_resource_types
            ;;
        web)
            exec uvicorn core.asgi:application --host 0.0.0.0 --port 8000 \
                --workers "${DJANGO_WORKERS:-2}"
            ;;
        worker)
            # gevent keeps memory low; the worker mostly waits for HTTP responses.
            exec celery -A core worker --loglevel=info -P gevent -c 100
            ;;
        *)
            echo "Unknown command: $1" >&2
            exit 2
            ;;
    esac
}

[ "$#" -gt 0 ] || set -- web
for command in "$@"; do
    run "$command"
done
