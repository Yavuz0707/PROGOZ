#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ../frontend
npm install
echo "Kurulum tamamlandi."

