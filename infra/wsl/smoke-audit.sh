#!/usr/bin/env bash
set -euo pipefail
curl -s -X POST http://127.0.0.1:8001/api/lab/audit \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Rispondi solo: OK",
    "teacher_response": "OK",
    "student_response": "OK",
    "student_model": "gemma4:latest"
  }'
