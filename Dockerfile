FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 创建数据和日志目录
RUN mkdir -p /data /data/logs

# 复制应用代码
COPY . .

# 设置环境变量
ENV DATABASE_PATH=/data/tweetanalyst.db
ENV FLASK_SECRET_KEY=default_secret_key_please_change_in_env
ENV LOG_DIR=/data/logs
ENV FIRST_LOGIN=true

# 暴露端口
EXPOSE 5000

# 添加启动脚本
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 启动命令
CMD ["/app/docker-entrypoint.sh"]