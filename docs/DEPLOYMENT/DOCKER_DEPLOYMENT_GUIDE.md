# AutoDiary Docker 部署完整指南

## 🐳 Docker 部署概述

基于 reference 目录资源的完整 Docker 容器化部署方案，包含 FunASR 语音识别、摄像头 Web 管理、智能分析等所有功能模块。

## 📋 系统要求

### Docker 环境要求
- **Docker Desktop**: 4.0+ (Windows/macOS) 或 Docker Engine 20.10+ (Linux)
- **Docker Compose**: 2.0+
- **可用内存**: 至少 4GB (推荐 8GB+)
- **可用磁盘空间**: 至少 10GB

### 系统兼容性
- ✅ Windows 10/11 (Docker Desktop)
- ✅ macOS 10.15+ (Docker Desktop)  
- ✅ Ubuntu 18.04+ / CentOS 7+ / Debian 10+
- ✅ 支持 GPU 的 NVIDIA 系统 (可选)

## 🚀 快速部署

### 方式一：一键部署脚本

**Linux/macOS:**
```bash
chmod +x deploy.sh
./deploy.sh
# 选择选项 1 (Docker 容器部署)
```

**Windows:**
```cmd
deploy.bat
# 选择选项 1 (Docker 容器部署)
```

### 方式二：手动 Docker 部署

```bash
# 1. 创建必要目录
mkdir -p data/{Images,Audio,Transcriptions,Summaries,Analysis,Logs}
mkdir -p config/{ssl,grafana/provisioning}
mkdir -p logs models web/static

# 2. ��成配置文件
docker-compose config > docker-compose.yml

# 3. 构建并启动服务
docker-compose build
docker-compose up -d

# 4. 查看服务状态
docker-compose ps
```

## 📁 Docker 配置文件说明

### docker-compose.yml 完整配置

```yaml
version: '3.8'

services:
  # FunASR 语音识别服务
  funasr-server:
    image: registry.cn-hangzhou.aliyuncs.com/funasr/funasr-runtime-sdk:0.1.10
    container_name: autodiary_funasr
    restart: unless-stopped
    ports:
      - "10095:10095"
    volumes:
      - ./models:/workspace/models
      - ./data/models_cache:/workspace/cache
    environment:
      - MODEL_NAME=paraformer-zh
      - DEVICE=cpu  # GPU 用户改为 cuda
      - NUM_THREADS=4
    networks:
      - autodiary-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:10095/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis 缓存服务
  redis:
    image: redis:7-alpine
    container_name: autodiary_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./config/redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    networks:
      - autodiary-network

  # AutoDiary 主服务器
  autodiary-server:
    build: 
      context: .
      dockerfile: Dockerfile
    container_name: autodiary_main
    restart: unless-stopped
    ports:
      - "8000:8000"  # WebSocket 视频流
      - "8001:8001"  # WebSocket 音频流
      - "8080:8080"  # Web 管理界面
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/app/logs
      - ./models:/app/models
    environment:
      - PYTHONPATH=/app
      - FUNASR_SERVER_URL=http://funasr-server:10095
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    depends_on:
      - funasr-server
      - redis
    networks:
      - autodiary-network

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    container_name: autodiary_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf
      - ./config/ssl:/etc/nginx/ssl
    depends_on:
      - autodiary-server
    networks:
      - autodiary-network

volumes:
  redis_data:
    driver: local

networks:
  autodiary-network:
    driver: bridge
```

### Dockerfile 优化配置

```dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc g++ make cmake \
    git curl wget \
    libsndfile1 ffmpeg \
    libsox-dev libsox-fmt-all \
    libffi-dev libssl-dev \
    pkg-config portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements_new.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 安装FunASR
RUN pip install --no-cache-dir -U funasr modelscope

# 复制应用代码
COPY . /app/

# 创建目录和设置权限
RUN mkdir -p /app/data/Images /app/data/Audio /app/data/Transcriptions \
    /app/data/Summaries /app/data/Analysis /app/data/Logs \
    && chmod +x /app/*.py

# 创建用户
RUN useradd -m -u 1000 autodiary && chown -R autodiary:autodiary /app
USER autodiary

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

EXPOSE 8000 8001 8080

CMD ["python", "integrated_server.py"]
```

## 🔧 高级配置

### GPU 加速配置

如果您有 NVIDIA GPU，可以启用 GPU 加速：

1. **安装 NVIDIA Container Toolkit**
```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

2. **修改 docker-compose.yml**
```yaml
services:
  funasr-server:
    environment:
      - DEVICE=cuda  # 改为 cuda
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  autodiary-server:
    environment:
      - FUNASR_DEVICE=cuda  # 添加GPU支持
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### 生产环境配置

```yaml
version: '3.8'

services:
  funasr-server:
    image: registry.cn-hangzhou.aliyuncs.com/funasr/funasr-runtime-sdk:0.1.10
    restart: always
    environment:
      - MODEL_NAME=paraformer-zh
      - DEVICE=cuda
      - NUM_THREADS=8
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
        reservations:
          memory: 4G
          cpus: '2'

  autodiary-server:
    restart: always
    environment:
      - LOG_LEVEL=WARNING  # 生产环境使用WARNING级别
      - WORKERS=4         # 多worker进程
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
        reservations:
          memory: 2G
          cpus: '1'

  redis:
    restart: always
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
```

## 📊 监控和日志

### 启用监控服务

```bash
# 启动包含监控的完整部署
docker-compose --profile monitoring up -d
```

### 查看服务状态

```bash
# 查看所有容器状态
docker-compose ps

# 查看特定服务日志
docker-compose logs -f autodiary-server
docker-compose logs -f funasr-server

# 查看资源使用情况
docker stats
```

### 日志管理

```yaml
# 在 docker-compose.yml 中添加日志配置
services:
  autodiary-server:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
    volumes:
      - ./logs:/app/logs
```

## 🔍 故障排除

### 常见问题解决方案

#### 1. Docker 服务启动失败
```bash
# 检查Docker服务状态
systemctl status docker

# 重启Docker服务
sudo systemctl restart docker

# 检查磁盘空间
df -h
```

#### 2. 容器内存不足
```bash
# 查看容器资源使用
docker stats

# 增加Docker内存限制（Docker Desktop设置）
# 或修改docker-compose.yml中的memory限制
```

#### 3. 网络连接问题
```bash
# 检查网络
docker network ls
docker network inspect autodiary_autodiary-network

# 重建网络
docker-compose down
docker network prune
docker-compose up -d
```

#### 4. FunASR 模型下载失败
```bash
# 手动下载模型
docker exec -it autodiary_main bash
python -c "
from funasr import AutoModel
model = AutoModel(model='paraformer-zh')
print('模型下载完成')
"
```

#### 5. 端口冲突
```yaml
# 修改 docker-compose.yml 中的端口映射
ports:
  - "8001:8000"  # 修改外部端口
  - "8002:8001"
  - "8081:8080"
```

## 🚀 性能优化

### 1. 构建优化

```dockerfile
# 多阶段构建优化
FROM python:3.9-slim as builder

WORKDIR /app
COPY requirements_new.txt .
RUN pip install --user --no-cache-dir -r requirements_new.txt

FROM python:3.9-slim

WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd -m -u 1000 autodiary
USER autodiary

CMD ["python", "integrated_server.py"]
```

### 2. 镜像优化

```bash
# 构建时使用多CPU核心
DOCKER_BUILDKIT=1 docker-compose build

# 使用镜像缓存
docker-compose build --no-cache

# 压缩镜像
docker image prune -a
```

### 3. 运行时优化

```yaml
services:
  autodiary-server:
    deploy:
      replicas: 2  # 多实例负载均衡
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

## 🔒 安全配置

### 1. 网络安全

```yaml
networks:
  autodiary-network:
    driver: bridge
    internal: false  # 设为true可限制外网访问
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### 2. 用户权限

```dockerfile
# 使用非root用户
RUN groupadd -r autodiary && useradd -r -g autodiary autodiary
USER autodiary
```

### 3. SSL/TLS 配置

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
}
```

## 📈 扩展部署

### 1. 多机部署

```yaml
# 使用 Docker Swarm
version: '3.8'

services:
  autodiary-server:
    image: autodiary:latest
    deploy:
      mode: replicated
      replicas: 3
      placement:
        constraints:
          - node.role == worker
```

### 2. Kubernetes 部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autodiary-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: autodiary-server
  template:
    metadata:
      labels:
        app: autodiary-server
    spec:
      containers:
      - name: autodiary-server
        image: autodiary:latest
        ports:
        - containerPort: 8080
```

## 🎯 部署验证

部署完成后，验证所有服务正常运行：

```bash
# 检查服务状态
docker-compose ps

# 访问Web界面
curl http://localhost:8080/api/status

# 测试语音识别
curl -X POST http://localhost:10095/recognize \
  -H "Content-Type: application/json" \
  -d '{"audio": "base64-encoded-audio-data"}'

# 查看系统日志
docker-compose logs -f --tail=100
```

成功部署后，您可以通过以下地址访问服务：
- **Web管理界面**: http://localhost:8080
- **Nginx代理**: http://localhost (如果启用)
- **监控面板**: http://localhost:3000 (如果启用)

这个Docker部署方案提供了完整的容器化解决方案，支持生产环境使用，具备高可用、可扩展、易维护的特点。
