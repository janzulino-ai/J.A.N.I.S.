#!/usr/bin/env bash
curl -sf -X POST http://127.0.0.1:8001/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"text":"rispondi solo: JANIS OK"}'
