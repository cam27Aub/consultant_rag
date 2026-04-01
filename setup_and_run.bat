@echo off
echo ============================================================
echo   CONSULTANT RAG - SETUP AND RUN (Windows)
echo ============================================================

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Running ingestion pipeline...
python naive_rag/ingest.py

echo.
echo Running test queries...
python naive_rag/query.py --demo

echo.
echo Done! Run  python naive_rag/query.py  to ask questions interactively.
pause
