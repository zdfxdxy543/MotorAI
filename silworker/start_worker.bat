@echo off
setlocal EnableExtensions

cd /d "%~dp0"
python remote_sil_worker.py --host 0.0.0.0 --port 8787 --config silworker_config.json
exit /b %ERRORLEVEL%
