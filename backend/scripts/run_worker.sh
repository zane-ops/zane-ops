#!/bin/bash
set -ex

# Activate the virtual environment
source /venv/bin/activate

# Wait for Loki and Temporal to be available with a timeout
wait-for-it zane.loki:3100 -t 60 -- wait-for-it zane.temporal:7233 -t 60 --

# Check if migrations are needed and apply them
echo "Checking for pending migrations..."
python manage.py makemigrations  # Generates migrations
python manage.py migrate --noinput  # Applies migrations without prompting

# Run the worker process
echo "Starting the worker process..."
python manage.py run_worker
