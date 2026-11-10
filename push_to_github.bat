@echo off
set "PATH=C:\Users\balaa\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd;%PATH%"
cd /d "C:\sre-observability-rag"
echo ===================================================
echo Pushing SRE Observability RAG to GitHub...
echo ===================================================
git push -u origin main
echo.
pause
