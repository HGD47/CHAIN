#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "Python 3 was not found. Install it from https://www.python.org/downloads/ then run this file again."
    read -p "Press Enter to close..."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "First run - setting things up, this takes a minute..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip > /dev/null
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "Starting Wire..."
echo "Your browser will open automatically. Close this window to stop the app."
echo ""
python3 app.py
