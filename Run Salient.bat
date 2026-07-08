@echo off
REM ===================================================================
REM  Double-click this file to launch the Salient app in your browser.
REM  It starts the local server and opens the two-box home screen.
REM  Close this black window to stop the app when you're done.
REM ===================================================================
cd /d "%~dp0"
echo Starting Salient...  (a browser tab will open in a few seconds)
echo Keep this window open while using the app. Close it to stop.
".venv\Scripts\python.exe" -m streamlit run "app\streamlit_app.py"
pause
