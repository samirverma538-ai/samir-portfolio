#!/usr/bin/env bash
cd "$(dirname "$0")/backend"
../venv/bin/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
