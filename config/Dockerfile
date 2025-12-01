# AutoDiary 集成服务器 Dockerfile
# 基于 reference 目录资源的容器化构建

FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    cmake \
    git \
    curl \
    wget \
    libsndfile1 \
    ffmpeg \
    libsox-dev \
    libsox-fmt-all \
    libffi-dev \
    libssl-dev \
    pkg-config \
    portaudio19-dev \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements_new.txt /app/requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 安装FunASR（如果需要）
RUN pip install --no-cache-dir -U funasr modelscope

# 复制应用代码
COPY . /app/

# 创建必要的目录
RUN mkdir -p /app/data/Images /app/data/Audio /app/data/Transcriptions \
    /app/data/Summaries /app/data/Analysis /app/data/Logs \
    /app/config /app/logs /app/models

# 设置权限
RUN chmod +x /app/*.py

# 创建非root用户
RUN useradd -m -u 1000 autodiary && \
    chown -R autodiary:autodiary /app

USER autodiary

# 暴露端口
EXPOSE 8000 8001 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# 启动命令
CMD ["python", "integrated_server.py"]
