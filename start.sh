#!/bin/bash
# One command to run Story Weaver: ./start.sh
cd "$(dirname "$0")"

[ -d .venv ] || { echo "Installing (first time only)..."; python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
[ -f .env ] || cp .env.example .env

.venv/bin/python setup_db.py > /dev/null
.venv/bin/python seed_data.py > /dev/null

echo ""
echo "  Story Weaver is running at http://127.0.0.1:5000"
echo "  Log in as admin / password123   (Ctrl+C to stop)"
echo ""
(sleep 2 && open http://127.0.0.1:5000) &
.venv/bin/python run.py
