@echo off
setlocal

REM // python
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements

REM // gnu make
winget install -e --id GnuWin32.Make --accept-package-agreements --accept-source-agreements

REM // libs
python -m pip install Flask==3.0.0 feedparser==6.0.11 cryptography==42.0.8

python app.py
