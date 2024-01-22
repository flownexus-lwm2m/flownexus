#!/bin/bash

# General URLs:
# http://127.0.0.1:8000/admin/
# http://127.0.0.1:8000/timetemperature/list/
#
# Your server's base URL
BASE_URL="http://127.0.0.1:8000"

# Endpoint for the TimeTemperature model
ENDPOINT="/api/timetemperature/"

# Perform a POST request to create a new TimeTemperature instance
# Replace "23.5" with the temperature value you want to test
POST_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d '{"temperature": 23.5}' "${BASE_URL}${ENDPOINT}")

# Output the POST response
echo "POST request response:"
echo "$POST_RESPONSE"
echo

# Perform a GET request to retrieve all TimeTemperature instances
GET_RESPONSE=$(curl -s -X GET "${BASE_URL}${ENDPOINT}")

# Output the GET response
echo "GET request response:"
echo "$GET_RESPONSE"
echo
