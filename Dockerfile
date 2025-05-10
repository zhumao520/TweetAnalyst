FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装Python依赖
COPY requirements.txt /app/requirements.txt

# 安装所有依赖，确保指定关键包的精确版本
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir \
    openai==1.12.0 \
    langchain-openai==0.0.5 \
    langchain-core==0.1.15 \
    Flask==2.3.3 \
    Flask-WTF==1.1.1 \
    Werkzeug==2.3.7 \
    Flask-SQLAlchemy==3.1.1 \
    apprise==1.7.1 \
    httpx[socks]==0.25.2 \
    tweety-ns==0.9.0 \
    && pip cache purge

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