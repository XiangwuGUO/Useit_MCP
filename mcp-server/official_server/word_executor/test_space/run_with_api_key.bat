@echo off
REM Windows批处理脚本 - 设置API Key并运行

echo ========================================
echo AI Excel Modifier
echo ========================================
echo.

REM 检查是否设置了API Key
if "%OPENAI_API_KEY%"=="" (
    echo ERROR: OPENAI_API_KEY not set!
    echo.
    echo Please set your API key first:
    echo   set OPENAI_API_KEY=your-api-key
    echo.
    echo Or edit this batch file and add your key below
    pause
    exit /b 1
)

REM 或者在这里直接设置API Key（不推荐，因为会暴露在文件中）
REM set OPENAI_API_KEY=sk-your-key-here

echo API Key: %OPENAI_API_KEY:~0,8%...
echo.

cd /d "%~dp0.."
python modify_test_excel.py

pause
