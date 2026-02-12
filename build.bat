@echo off
echo Building Standalone Executable...
pip install pyinstaller
pyinstaller --noconsole --clean --name "EcoPack_Optimizer" ^
    --add-data "core;core" ^
    main.py
echo.
echo Build complete. Check the 'dist' folder.
pause
