@echo off
echo [INFO] Installing dependencies...
pip install -r requirements.txt

echo [INFO] Starting Click Animator...
python main.py
pause
