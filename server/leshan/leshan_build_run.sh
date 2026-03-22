#!/bin/bash
#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

# Exit immediately if a command fails, and ensure pipeline failures are captured
set -e
set -o pipefail

mvn clean install
exec java -jar target/leshan-svr-0.9-jar-with-dependencies.jar
