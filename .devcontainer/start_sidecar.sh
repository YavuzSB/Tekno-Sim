#!/bin/bash
# TeknoSim V4.4 Sidecar Uvicorn Server Start Script

# Ensure log directory exists
mkdir -p /workspace/log

# Infinite loop to auto-restart uvicorn on crash
# Output and errors are redirected to fastapi.log
echo "Starting FastAPI Sidecar for TeknoSim..." >> /workspace/log/fastapi.log

while true; do
  python3 /workspace/teknosim_core/utils/sidecar_server.py >> /workspace/log/fastapi.log 2>&1
  echo "Sidecar server crashed or stopped. Restarting in 1 second..." >> /workspace/log/fastapi.log
  sleep 1
done
