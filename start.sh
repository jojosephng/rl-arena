#!/bin/bash

# 1. Start Redis in the background
redis-server --daemonize yes

# 2. Start the Celery Worker in the background
celery -A tasks worker --pool=solo --loglevel=info &

# 3. Start the Web Server (The main process)
uvicorn main:app --host 0.0.0.0 --port $PORT