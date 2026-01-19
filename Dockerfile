# Use standard Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system tools (Redis needs these)
RUN apt-get update && apt-get install -y redis-server

# Install Python libraries
RUN pip install fastapi uvicorn python-multipart celery redis eventlet torch numpy

# Copy all your code into the container
COPY . .

# --- THE NUCLEAR FIX ---
# 1. Delete the "infected" Windows file
RUN rm -f start.sh

# 2. Create a fresh, clean Linux script on the fly
RUN echo "#!/bin/bash" > start.sh
RUN echo "redis-server --daemonize yes" >> start.sh
RUN echo "celery -A tasks worker --pool=solo --loglevel=info &" >> start.sh
RUN echo "uvicorn main:app --host 0.0.0.0 --port 10000" >> start.sh

# 3. Make it runnable
RUN chmod +x start.sh

# The command to run
CMD ["./start.sh"]