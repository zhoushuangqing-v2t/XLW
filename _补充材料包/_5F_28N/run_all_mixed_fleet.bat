@echo off
chcp 65001 >nul
cd /d %~dp0
python solve_lrp_mixed_fleet_three_scenarios.py --input-dir input --output-dir results
echo.
echo Calculation finished. Check the results folder.
pause
