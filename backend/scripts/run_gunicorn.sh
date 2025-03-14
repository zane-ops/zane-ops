#!/bin/bash
set -ex

# Wait for Loki and Temporal to be available with a timeout
wait-for-it zane.loki:3100 -t 60 -- wait-for-it zane.temporal:7233 -t 60 --

# Activate the virtual environment
source /venv/bin/activate

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Create or update Temporal schedules
echo "Creating or updating Temporal schedules..."
python manage.py create_metrics_cleanup_schedule
python manage.py create_system_cleanup_schedule

# Start Gunicorn WSGI server
echo "Starting Gunicorn..."
gunicorn --config=/app/gunicorn.conf.py backend.wsgi:application
