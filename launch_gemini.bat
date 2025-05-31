@echo off

REM 仮想環境をアクティベート
call .venv\Scripts\activate.bat

REM Pythonスクリプトを実行
python main.py

REM 仮想環境をディアクティベート（任意）
REM call deactivate

pause