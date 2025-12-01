@echo off
setlocal enabledelayedexpansion

REM AutoDiary 集成服务器部署脚本 (Windows版本)
REM 基于 reference 目录资源的一键部署方案

title AutoDiary 集成服务器部署

REM 颜色定义
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM 日志函数
:log_info
echo %BLUE%[INFO]%NC% %~1
goto :eof

:log_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:log_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:log_error
echo %RED%[ERROR]%NC% %~1
goto :eof

REM 检查系统要求
:check_requirements
call :log_info "检查系统要求..."

REM 检查Docker
docker --version >nul 2>&1
if errorlevel 1 (
    call :log_error "Docker 未安装，请先安装 Docker Desktop"
    pause
    exit /b 1
)

REM 检查Docker Compose
docker-compose --version >nul 2>&1
if errorlevel 1 (
    call :log_error "Docker Compose 未安装，请先安装 Docker Compose"
    pause
    exit /b 1
)

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    call :log_warning "Python 未安装，将跳过本地部署选项"
) else (
    for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
    call :log_info "Python 版本: !PYTHON_VERSION!"
)

call :log_success "系统要求检查完成"
goto :eof

REM 创建目录结构
:create_directories
call :log_info "创建目录结构..."

set "directories=data\Images data\Audio data\Transcriptions data\Summaries data\Analysis data\Logs data\models_cache config logs models web\static config\ssl config\grafana\provisioning"

for %%d in (%directories%) do (
    if not exist "%%d" (
        mkdir "%%d"
        call :log_info "创建目录: %%d"
    )
)

call :log_success "目录结构创建完成"
goto :eof

REM 生成配置文件
:generate_configs
call :log_info "生成配置文件..."

REM Redis 配置
(
echo # Redis 配置文件
echo bind 0.0.0.0
echo port 6379
echo timeout 0
echo tcp-keepalive 300
echo daemonize no
echo supervised no
echo pidfile /var/run/redis_6379.pid
echo loglevel notice
echo logfile ""
echo databases 16
echo save 900 1
echo save 300 10
echo save 60 10000
echo stop-writes-on-bgsave-error yes
echo rdbcompression yes
echo rdbchecksum yes
echo dbfilename dump.rdb
echo dir /data
echo maxmemory-policy allkeys-lru
echo appendonly yes
echo appendfilename "appendonly.aof"
echo appendfsync everysec
) > config\redis.conf

REM Nginx 配置
(
echo events {
echo     worker_connections 1024;
echo }
echo.
echo http {
echo     upstream autodiary_backend {
echo         server autodiary-server:8080;
echo     }
echo     
echo     upstream websocket_backend {
echo         server autodiary-server:8000;
echo     }
echo     
echo     map $http_upgrade $connection_upgrade {
echo         default upgrade;
echo         '' close;
echo     }
echo     
echo     server {
echo         listen 80;
echo         server_name localhost;
echo         
echo         # Web 管理界面
echo         location / {
echo             proxy_pass http://autodiary_backend;
echo             proxy_set_header Host $host;
echo             proxy_set_header X-Real-IP $remote_addr;
echo             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
echo             proxy_set_header X-Forwarded-Proto $scheme;
echo         }
echo         
echo         # WebSocket 视频流
echo         location /video {
echo             proxy_pass http://websocket_backend;
echo             proxy_http_version 1.1;
echo             proxy_set_header Upgrade $http_upgrade;
echo             proxy_set_header Connection $connection_upgrade;
echo             proxy_set_header Host $host;
echo             proxy_set_header X-Real-IP $remote_addr;
echo             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
echo             proxy_set_header X-Forwarded-Proto $scheme;
echo             proxy_read_timeout 86400;
echo         }
echo         
echo         # WebSocket 音频流
echo         location /audio {
echo             proxy_pass http://autodiary-server:8001;
echo             proxy_http_version 1.1;
echo             proxy_set_header Upgrade $http_upgrade;
echo             proxy_set_header Connection $connection_upgrade;
echo             proxy_set_header Host $host;
echo             proxy_set_header X-Real-IP $remote_addr;
echo             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
echo             proxy_set_header X-Forwarded-Proto $scheme;
echo             proxy_read_timeout 86400;
echo         }
echo     }
echo }
) > config\nginx.conf

REM Prometheus 配置
(
echo global {
echo   scrape_interval: 15s
echo   evaluation_interval: 15s
echo }
echo.
echo scrape_configs:
echo   - job_name: 'autodiary'
echo     static_configs:
echo       - targets: ['autodiary-server:8080']
echo     metrics_path: '/api/metrics'
echo     scrape_interval: 5s
) > config\prometheus.yml

REM 创建 Grafana 数据源目录
if not exist "config\grafana\provisioning\datasources" mkdir "config\grafana\provisioning\datasources"

REM Grafana 数据源配置
(
echo apiVersion: 1
echo.
echo datasources:
echo   - name: Prometheus
echo     type: prometheus
echo     access: proxy
echo     url: http://prometheus:9090
echo     isDefault: true
) > config\grafana\provisioning\datasources\prometheus.yml

call :log_success "配置文件生成完成"
goto :eof

REM 显示部署选项
:show_options
echo.
call :log_info "AutoDiary 部署选项："
echo "1) Docker 容器部署（推荐）"
echo "2) 本地 Python 部署"
echo "3) 仅部署 FunASR 服务"
echo "4) 仅部署摄像头 Web 服务"
echo "5) 完整部署（包含监控）"
echo "6) 查看服务状态"
echo "7) 停止所有服务"
echo "8) 清理数据"
echo "0) 退出"
echo.
goto :eof

REM Docker 容器部署
:deploy_docker
call :log_info "开始 Docker 容器部署..."

REM 检查 Docker 服务状态
docker info >nul 2>&1
if errorlevel 1 (
    call :log_error "Docker 服务未运行，请启动 Docker Desktop"
    pause
    goto :main_menu
)

REM 构建并启动服务
call :log_info "构建 Docker 镜像..."
docker-compose build

call :log_info "启动服务..."
docker-compose up -d

call :log_success "Docker 容器部署完成"
call :show_service_info
goto :eof

REM 本地 Python 部署
:deploy_local
call :log_info "开始本地 Python 部署..."

python --version >nul 2>&1
if errorlevel 1 (
    call :log_error "Python 未安装"
    pause
    goto :main_menu
)

REM 安装依赖
call :log_info "安装 Python 依赖..."
pip install -r requirements_new.txt

REM 启动服务
call :log_info "启动集成服务器..."
start /B python integrated_server.py

call :log_success "本地 Python 部署完成"
call :show_local_service_info
goto :eof

REM 完整部署（包含监控）
:deploy_full
call :log_info "开始完整部署（包含监控）..."
docker-compose --profile monitoring up -d
call :log_success "完整部署完成"
call :show_service_info
call :show_monitoring_info
goto :eof

REM 显示服务信息
:show_service_info
echo.
call :log_success "服务部署完成！访问信息："
echo "📱 Web 管理界面: http://localhost:8080"
echo "🎥 视频流: ws://localhost:8000/video"
echo "🎤 音频流: ws://localhost:8001/audio"
echo "🔧 FunASR 服务: http://localhost:10095"
echo.

docker ps --format "table {{.Names}}" | findstr "nginx" >nul
if not errorlevel 1 (
    echo "🌐 Nginx 代理: http://localhost"
    echo "🔒 HTTPS: https://localhost"
)
goto :eof

REM 显示本地服务信息
:show_local_service_info
echo.
call :log_success "本地服务启动完成！访问信息："
echo "📱 Web 管理界面: http://localhost:8080"
echo "🎥 视频流: ws://localhost:8000/video"
echo "🎤 音频流: ws://localhost:8001/audio"
echo.
goto :eof

REM 显示监控信息
:show_monitoring_info
echo "📊 监控服务："
echo "   Prometheus: http://localhost:9090"
echo "   Grafana: http://localhost:3000 (admin/admin123)"
echo.
goto :eof

REM 查看服务状态
:check_status
call :log_info "检查服务状态..."
if exist "docker-compose.yml" (
    docker-compose ps
) else (
    call :log_warning "Docker Compose 配置未找到"
)

REM 检查本地进程
tasklist | findstr "python.exe" >nul
if not errorlevel 1 (
    call :log_info "本地 Python 进程正在运行"
)
goto :eof

REM 停止服务
:stop_services
call :log_info "停止所有服务..."

REM 停止 Docker 服务
if exist "docker-compose.yml" (
    docker-compose down
    call :log_success "Docker 服务已停止"
)

REM 停止本地进程
taskkill /f /im python.exe >nul 2>&1
if not errorlevel 1 (
    call :log_success "本地 Python 服务已停止"
)
goto :eof

REM 清理数据
:clean_data
call :log_warning "这将删除所有数据，确认继续吗？(y/N)"
set /p confirm=
if /i "!confirm!"=="y" (
    call :log_info "清理数据..."
    
    REM 停止服务
    call :stop_services
    
    REM 删除数据目录内容
    if exist "data" (
        del /Q /S data\* >nul 2>&1
        call :log_info "数据目录已清理"
    )
    
    REM 清理 Docker 数据
    docker system prune -f >nul 2>&1
    if not errorlevel 1 (
        call :log_info "Docker 数据已清理"
    )
    
    call :log_success "数据清理完成"
) else (
    call :log_info "取消数据清理"
)
goto :eof

REM 主菜单循环
:main_menu
:main_loop
call :show_options
set /p choice=请选择部署选项 [0-8]: 

if "%choice%"=="1" (
    call :check_requirements
    call :create_directories
    call :generate_configs
    call :deploy_docker
) else if "%choice%"=="2" (
    call :check_requirements
    call :create_directories
    call :generate_configs
    call :deploy_local
) else if "%choice%"=="3" (
    call :log_info "部署 FunASR 服务..."
    docker-compose up -d funasr-server redis
) else if "%choice%"=="4" (
    call :log_info "部署摄像头 Web 服务..."
    docker-compose up -d autodiary-server nginx
) else if "%choice%"=="5" (
    call :check_requirements
    call :create_directories
    call :generate_configs
    call :deploy_full
) else if "%choice%"=="6" (
    call :check_status
) else if "%choice%"=="7" (
    call :stop_services
) else if "%choice%"=="8" (
    call :clean_data
) else if "%choice%"=="0" (
    call :log_info "退出部署脚本"
    exit /b 0
) else (
    call :log_error "无效选项，请重新选择"
)

echo.
pause
goto :main_loop

REM 脚本入口
:main
cls
call :log_info "AutoDiary 集成服务器部署脚本 (Windows版本)"
call :log_info "基于 reference 目录资源: FunASR + Camera_HTTP_Server_STA + Minutes"
echo.
call :main_loop
goto :eof

REM 启动主函数
call :main
