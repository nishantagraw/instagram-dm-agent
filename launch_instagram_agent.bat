@echo off
cd /d "c:\Users\megha\infinite club\instagram-dm-agent"
start "" python instagram_agent.py
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5002
