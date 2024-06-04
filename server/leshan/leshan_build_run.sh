#!/bin/bash

# Ensure logs directory exists
mkdir -p logs

logfile="logs/leshan_$(date +%Y-%m-%d_%H-%M-%S).log"
touch "$logfile"

mvn clean install 2>&1 | tee -a "$logfile"
java -jar target/leshan-svr-0.9-jar-with-dependencies.jar 2>&1 | tee -a "$logfile"
