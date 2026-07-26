#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR"

streamlit run src/dashboard/app.py \
    --server.address 0.0.0.0 \
    --server.port 8501 \
    --server.headless true
