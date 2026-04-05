@echo off
title ContractCheck Pro v12.5
echo Starting ContractCheck Pro...

:: 1. Navigate to the folder where this bat file is located
cd /d "%~dp0"

:: 2. Activate the virtual environment (adjust '.venv' if yours is named differently)
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found. Trying global python...
)

:: 3. Run the Streamlit app
streamlit run app.py

pause