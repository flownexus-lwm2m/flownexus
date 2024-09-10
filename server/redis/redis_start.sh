#!/bin/sh

# Ensure logs directory exists
mkdir -p logs

logfile="logs/redis_$(date +%Y-%m-%d_%H-%M-%S).log"
touch "$logfile"

# Start Redis server
redis-server /redis/redis.conf  2>&1 | tee -a $logfile

# Wait for Redis to start
until redis-cli ping; do
    echo "Waiting for Redis to start..."
    sleep 1
done

echo "Redis is running."

# Wait for Redis to exit
wait
