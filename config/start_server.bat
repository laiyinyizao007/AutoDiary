@echo off
echo ========================================
echo AutoDiary 服务器启动脚本
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未安装或未添加到 PATH
    echo 请先安装 Python 3.8+ 并确保已添加到系统 PATH
    pause
    exit /b 1
)

echo [信息] 检测到 Python:
python --version

REM 检查是否安装了必要的依赖
echo [信息] 检查 Python 依赖...
pip show websockets >nul 2>&1
if errorlevel 1 (
    echo [信息] 安装 websockets 库...
    pip install websockets
)

pip show Pillow >nul 2>&1
if errorlevel 1 (
    echo [信息] 安装 Pillow 库...
    pip install Pillow
)

echo [信息] 依赖检查完成
echo.

REM 检查端口是否被占用
netstat -an | findstr ":8000" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 8000 已被占用
    echo 请关闭占用该端口的程序或修改 server.py 中的端口配置
    echo.
    set /p choice="是否继续启动服务器? (y/n): "
    if /i not "%choice%"=="y" (
        echo [取消] 服务器启动已取消
        pause
        exit /b 1
    )
)

REM 创建数据目录
if not exist "data" mkdir data
if not exist "data\Images" mkdir data\Images
if not exist "data\Audio" mkdir data\Audio
if not exist "data\Logs" mkdir data\Logs

echo [信息] 数据目录已准备就绪
echo.

REM 启动服务器
echo [信息] 正在启动 AutoDiary WebSocket 服务器...
echo [信息] 监听地址: 0.0.0.0:8000
echo [信息] 按 Ctrl+C 停止服务器
echo ========================================
echo.

python server.py

echo.
echo [信息] 服务器已停止
pause
