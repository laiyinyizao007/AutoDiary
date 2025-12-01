#!/bin/bash

# AutoDiary 集成服务器部署脚本
# 基于 reference 目录资源的一键部署方案

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查系统要求
check_requirements() {
    log_info "检查系统要求..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    # 检查Python（可选，用于本地部署）
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_info "Python 版本: $PYTHON_VERSION"
    else
        log_warning "Python3 未安装，将跳过本地部署选项"
    fi
    
    log_success "系统要求检查完成"
}

# 创建目录结构
create_directories() {
    log_info "创建目录结构..."
    
    directories=(
        "data/Images"
        "data/Audio"
        "data/Transcriptions"
        "data/Summaries"
        "data/Analysis"
        "data/Logs"
        "data/models_cache"
        "config"
        "logs"
        "models"
        "web/static"
        "config/ssl"
        "config/grafana/provisioning"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        log_info "创建目录: $dir"
    done
    
    log_success "目录结构创建完成"
}

# 生成配置文件
generate_configs() {
    log_info "生成配置文件..."
    
    # Redis 配置
    cat > config/redis.conf << EOF
# Redis 配置文件
bind 0.0.0.0
port 6379
timeout 0
tcp-keepalive 300
daemonize no
supervised no
pidfile /var/run/redis_6379.pid
loglevel notice
logfile ""
databases 16
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /data
slaveof-serve-stale-data yes
slave-serve-stale-data yes
slave-read-only yes
repl-diskless-sync no
repl-diskless-sync-delay 5
slave-priority 100
maxmemory-policy allkeys-lru
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
aof-load-truncated yes
lua-time-limit 5000
slowlog-log-slower-than 10000
slowlog-max-len 128
latency-monitor-threshold 0
notify-keyspace-events ""
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
list-max-ziplist-size -2
list-compress-depth 0
set-max-intset-entries 512
zset-max-ziplist-entries 128
zset-max-ziplist-value 64
hll-sparse-max-bytes 3000
activerehashing yes
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit slave 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60
hz 10
aof-rewrite-incremental-fsync yes
EOF

    # Nginx 配置
    cat > config/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    upstream autodiary_backend {
        server autodiary-server:8080;
    }
    
    upstream websocket_backend {
        server autodiary-server:8000;
    }
    
    map \$http_upgrade \$connection_upgrade {
        default upgrade;
        '' close;
    }
    
    server {
        listen 80;
        server_name localhost;
        
        # Web 管理界面
        location / {
            proxy_pass http://autodiary_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
        
        # WebSocket 视频流
        location /video {
            proxy_pass http://websocket_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \$connection_upgrade;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_read_timeout 86400;
        }
        
        # WebSocket 音频流
        location /audio {
            proxy_pass http://autodiary-server:8001;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \$connection_upgrade;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_read_timeout 86400;
        }
        
        # 静态文件
        location /static/ {
            alias /usr/share/nginx/html/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
}
EOF

    # Prometheus 配置
    cat > config/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'autodiary'
    static_configs:
      - targets: ['autodiary-server:8080']
    metrics_path: '/api/metrics'
    scrape_interval: 5s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
EOF

    # Grafana 数据源配置
    mkdir -p config/grafana/provisioning/datasources
    cat > config/grafana/provisioning/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

    log_success "配置文件生成完成"
}

# 显示部署选项
show_options() {
    echo ""
    log_info "AutoDiary 部署选项："
    echo "1) Docker 容器部署（推荐）"
    echo "2) 本地 Python 部署"
    echo "3) 仅部署 FunASR 服务"
    echo "4) 仅部署摄像头 Web 服务"
    echo "5) 完整部署（包含监控）"
    echo "6) 查看服务状态"
    echo "7) 停止所有服务"
    echo "8) 清理数据"
    echo "0) 退出"
    echo ""
}

# Docker 容器部署
deploy_docker() {
    log_info "开始 Docker 容器部署..."
    
    # 检查 Docker 服务状态
    if ! docker info &> /dev/null; then
        log_error "Docker 服务未运行，请启动 Docker 服务"
        exit 1
    fi
    
    # 构建并启动服务
    log_info "构建 Docker 镜像..."
    docker-compose build
    
    log_info "启动服务..."
    docker-compose up -d
    
    log_success "Docker 容器部署完成"
    show_service_info
}

# 本地 Python 部署
deploy_local() {
    log_info "开始本地 Python 部署..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    # 安装依赖
    log_info "安装 Python 依赖..."
    pip3 install -r requirements_new.txt
    
    # 启动服务
    log_info "启动集成服务器..."
    python3 integrated_server.py &
    
    log_success "本地 Python 部署完成"
    show_local_service_info
}

# 完整部署（包含监控）
deploy_full() {
    log_info "开始完整部署（包含监控）..."
    
    docker-compose --profile monitoring up -d
    
    log_success "完整部署完成"
    show_service_info
    show_monitoring_info
}

# 显示服务信息
show_service_info() {
    echo ""
    log_success "服务部署完成！访问信息："
    echo "📱 Web 管理界面: http://localhost:8080"
    echo "🎥 视频流: ws://localhost:8000/video"
    echo "🎤 音频流: ws://localhost:8001/audio"
    echo "🔧 FunASR 服务: http://localhost:10095"
    echo ""
    
    if docker ps --format "table {{.Names}}" | grep -q "nginx"; then
        echo "🌐 Nginx 代理: http://localhost"
        echo "🔒 HTTPS: https://localhost"
    fi
}

# 显示本地服务信息
show_local_service_info() {
    echo ""
    log_success "本地服务启动完成！访问信息："
    echo "📱 Web 管理界面: http://localhost:8080"
    echo "🎥 视频流: ws://localhost:8000/video"
    echo "🎤 音频流: ws://localhost:8001/audio"
    echo ""
}

# 显示监控信息
show_monitoring_info() {
    echo "📊 监控服务："
    echo "   Prometheus: http://localhost:9090"
    echo "   Grafana: http://localhost:3000 (admin/admin123)"
    echo ""
}

# 查看服务状态
check_status() {
    log_info "检查服务状态..."
    
    if command -v docker-compose &> /dev/null && [ -f "docker-compose.yml" ]; then
        docker-compose ps
    else
        log_warning "Docker Compose 配置未找到"
    fi
    
    # 检查本地进程
    if pgrep -f "integrated_server.py" &> /dev/null; then
        log_info "本地集成服务器正在运行"
    fi
}

# 停止服务
stop_services() {
    log_info "停止所有服务..."
    
    # 停止 Docker 服务
    if command -v docker-compose &> /dev/null && [ -f "docker-compose.yml" ]; then
        docker-compose down
        log_success "Docker 服务已停止"
    fi
    
    # 停止本地进程
    if pgrep -f "integrated_server.py" &> /dev/null; then
        pkill -f "integrated_server.py"
        log_success "本地服务已停止"
    fi
}

# 清理数据
clean_data() {
    log_warning "这将删除所有数据，确认继续吗？(y/N)"
    read -r confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        log_info "清理数据..."
        
        # 停止服务
        stop_services
        
        # 删除数据目录
        if [ -d "data" ]; then
            rm -rf data/*
            log_info "数据目录已清理"
        fi
        
        # 清理 Docker 数据
        if command -v docker &> /dev/null; then
            docker system prune -f
            log_info "Docker 数据已清理"
        fi
        
        log_success "数据清理完成"
    else
        log_info "取消数据清理"
    fi
}

# 主菜单
main_menu() {
    while true; do
        show_options
        read -p "请选择部署选项 [0-8]: " choice
        
        case $choice in
            1)
                check_requirements
                create_directories
                generate_configs
                deploy_docker
                ;;
            2)
                check_requirements
                create_directories
                generate_configs
                deploy_local
                ;;
            3)
                log_info "部署 FunASR 服务..."
                docker-compose up -d funasr-server redis
                ;;
            4)
                log_info "部署摄像头 Web 服务..."
                docker-compose up -d autodiary-server nginx
                ;;
            5)
                check_requirements
                create_directories
                generate_configs
                deploy_full
                ;;
            6)
                check_status
                ;;
            7)
                stop_services
                ;;
            8)
                clean_data
                ;;
            0)
                log_info "退出部署脚本"
                exit 0
                ;;
            *)
                log_error "无效选项，请重新选择"
                ;;
        esac
        
        echo ""
        read -p "按回车键继续..."
    done
}

# 脚本入口
main() {
    log_info "AutoDiary 集成服务器部署脚本"
    log_info "基于 reference 目录资源: FunASR + Camera_HTTP_Server_STA + Minutes"
    echo ""
    
    main_menu
}

# 运行主函数
main "$@"
