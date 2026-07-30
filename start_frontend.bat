@echo off
set PATH=C:\Users\xinzi\AppData\Local\nvm\node-v20.19.0-win-x64;%PATH%
set DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001
cd /d C:\Users\xinzi\Desktop\DeepTutor\web
echo Starting Next.js on port 3782...
call npx next dev --port 3782
