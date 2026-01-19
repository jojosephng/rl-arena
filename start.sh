#!/bin/bash

# Define a default port if Render doesn't provide one
PORT="${PORT:-10000}"

# 1. Start Redis in the background
redis-server --daemonize yes

# 2. Start the Celery Worker in the background
celery -A tasks worker --pool=solo --loglevel=info &

# 3. Start the Web Server
# We explicitly print the port so we can see it in logs
echo "Starting Uvicorn on port $PORT"
uvicorn main:app --host 0.0.0.0 --port $PORT