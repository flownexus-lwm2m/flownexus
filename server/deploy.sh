#!/bin/bash

# Sync directories: django and leshan
echo "Syncing directories: django"
rsync -az -e ssh ./django jonas@85.215.45.193:/home/jonas/

echo "Syncing directories: leshan"
rsync -az -e ssh ./leshan jonas@85.215.45.193:/home/jonas/

echo "Syncing directories: scripts"
rsync -az -e ssh ./docker-compose.yml jonas@85.215.45.193:/home/jonas/

echo "Stopping docker containers"
ssh -t jonas@85.215.45.193 "sudo docker-compose -f docker-compose.yml down"

echo "Starting docker containers"
ssh -t jonas@85.215.45.193 "sudo docker-compose -f docker-compose.yml up -d --build"
