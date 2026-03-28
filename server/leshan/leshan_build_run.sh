#!/bin/bash
#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

# Exit immediately if a command fails, and ensure pipeline failures are captured
set -e
set -o pipefail

JAR_FILE="target/leshan-svr-0.9-jar-with-dependencies.jar"

# If JAR already exists, skip build and run directly
if [ -f "$JAR_FILE" ]; then
    echo "JAR already exists, skipping build..."
    exec java -jar "$JAR_FILE"
fi

# Try to build - clean may fail due to permissions, so try install directly
mvn clean install || mvn install || true

# Check if JAR was created
if [ -f "$JAR_FILE" ]; then
    exec java -jar "$JAR_FILE"
else
    echo "ERROR: Build failed and no JAR file found"
    exit 1
fi
