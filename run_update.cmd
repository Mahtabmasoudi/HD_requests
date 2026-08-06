@echo off
REM ============================================================
REM  Click this to check TDEC for new determinations and update
REM  the map (tn_hd_streams.js) + push to GitHub.
REM ============================================================
cd /d "%~dp0"
python hd_daily_update.py
echo.
echo ------------------------------------------------------------
echo  Done. See update_log.txt for details, and needs_review.txt
echo  for any letters that need a manual look.
echo ------------------------------------------------------------
echo.
pause
