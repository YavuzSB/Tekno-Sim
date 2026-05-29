#!/bin/bash
# TeknoSim Zero-Dependency Sidecar Server Auto-Restart Script
# Logs are written to teknosim_core/utils/sidecar.log

while true; do
  python3 /workspace/teknosim_core/utils/sidecar_server.py >> /workspace/teknosim_core/utils/sidecar.log 2>&1
  sleep 1
done
