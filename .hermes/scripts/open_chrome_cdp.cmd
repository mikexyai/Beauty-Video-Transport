@echo off
setlocal
set "PORT=%~1"
if "%PORT%"=="" set "PORT=9222"
set "START_URL=%~2"
if "%START_URL%"=="" set "START_URL=https://www.douyin.com/jingxuan"
set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "PROFILE_DIR=C:\Project\Chrome\chrome_profile"

curl -fsS "http://127.0.0.1:%PORT%/json/version" >nul 2>nul
if %ERRORLEVEL%==0 (
  echo Chrome CDP is already listening on 127.0.0.1:%PORT%
  curl -fsS "http://127.0.0.1:%PORT%/json/version"
  exit /b 0
)

if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"
start "" "%CHROME_EXE%" --remote-debugging-port=%PORT% --remote-allow-origins=* --user-data-dir="%PROFILE_DIR%" --restore-last-session "%START_URL%"
echo Started Chrome CDP on 127.0.0.1:%PORT% using profile: %PROFILE_DIR%
