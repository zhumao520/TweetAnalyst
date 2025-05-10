FROM python:3.11-slim

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

# 安装所有依赖的最新版本
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN pip install --no-cache-dir openai langchain-openai langchain-core
RUN pip install --no-cache-dir Flask Flask-WTF Werkzeug Flask-SQLAlchemy
RUN pip install --no-cache-dir tweety-ns apprise "httpx[socks]"

# 清理pip缓存
RUN pip cache purge

# 创建数据和日志目录
RUN mkdir -p /data /data/logs

# 复制应用代码
COPY . .

# 设置环境变量
ENV DATABASE_PATH=/data/tweetAnalyst.db
ENV FLASK_SECRET_KEY=default_secret_key_please_change_in_env
ENV LOG_DIR=/data/logs
ENV FIRST_LOGIN=auto
ENV FLASK_DEBUG=false

# 设置默认LLM API
ENV LLM_API_BASE=https://api.x.ai/v1
ENV LLM_API_MODEL=grok-3-mini-beta

# 暴露端口
EXPOSE 5000

# 添加启动脚本
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 启动命令
CMD ["/app/docker-entrypoint.sh"]