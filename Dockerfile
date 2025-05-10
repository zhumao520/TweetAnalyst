FROM python:3.11-slim

LABEL maintainer="TweetAnalyst Team"
LABEL description="TweetAnalyst - 社交媒体内容分析助手"
LABEL version="1.0"

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 升级pip和基本工具
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 复制requirements.txt
COPY requirements.txt /app/requirements.txt

# 安装所有依赖（合并多个RUN命令减少层数）
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir openai langchain-openai langchain-core && \
    pip install --no-cache-dir Flask Flask-WTF Werkzeug Flask-SQLAlchemy && \
    pip install --no-cache-dir tweety-ns apprise "httpx[socks]" && \
    pip cache purge

# 创建数据和日志目录
RUN mkdir -p /data /data/logs && chmod -R 777 /data

# 添加启动脚本
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 复制应用代码
COPY . .

# 设置环境变量
ENV DATABASE_PATH=/data/tweetAnalyst.db \
    FLASK_SECRET_KEY=default_secret_key_please_change_in_env \
    LOG_DIR=/data/logs \
    FIRST_LOGIN=auto \
    FLASK_DEBUG=false \
    LLM_API_BASE=https://api.x.ai/v1 \
    LLM_API_MODEL=grok-3-mini-beta \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# 启动命令
CMD ["/app/docker-entrypoint.sh"]