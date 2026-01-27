#!/bin/sh

# Ensure logs directory exists
mkdir -p logs

logfile="logs/redis_$(date +%Y-%m-%d_%H-%M-%S).log"
touch "$logfile"

# Start Redis server in the background to allow the health check loop to run
redis-server /redis/redis.conf 2>&1 | tee -a "$logfile" &

# Wait for Redis to start
until redis-cli ping > /dev/null 2>&1; do
    echo "Waiting for Redis to start..."
    sleep 1
done

echo "Redis is running."

# Wait for the background process to exit
wait
