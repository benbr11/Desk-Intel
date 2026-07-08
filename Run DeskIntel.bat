@echo off
REM ===================================================================
REM  Double-click this file to launch the DeskIntel app in your browser.
REM  It starts the local server and opens the split-screen UI.
REM  Close this black window to stop the app when you're done.
REM ===================================================================
cd /d "%~dp0"
echo Starting DeskIntel...  (a browser tab will open in a few seconds)
echo Keep this window open while using the app. Close it to stop.
".venv\Scripts\python.exe" -m streamlit run "app\streamlit_app.py"
pause
