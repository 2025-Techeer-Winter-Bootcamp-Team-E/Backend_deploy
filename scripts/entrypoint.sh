#!/bin/bash

set -e

# Wait for database
echo "Waiting for PostgreSQL..."
python /app/scripts/wait_for_db.py

# Only run migrations if we're starting the web server (not celery workers)
# Check if the command contains "runserver" or "gunicorn"
if [[ "$1" == *"runserver"* ]] || [[ "$1" == *"gunicorn"* ]] || [[ "$1" == "python" && "$2" == "manage.py" && "$3" == "runserver" ]]; then
    # Run migrations
    echo "Running migrations..."
    python manage.py migrate --noinput

    # Collect static files
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
else
    echo "Skipping migrations (non-web container)..."
fi

# Execute the main command
exec "$@"
