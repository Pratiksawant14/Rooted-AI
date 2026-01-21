#!/bin/sh
# Force the application to start with hardcoded settings
# This ignores any "Start Command" overrides from the deployment platform
echo "Ignoring provided command arguments: $@"
echo "Starting Uvicorn on port 8080..."
exec uvicorn main:app --host 0.0.0.0 --port 8080
