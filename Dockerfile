FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建数据和日志目录
RUN mkdir -p /data /data/logs

# 复制应用代码
COPY . .

# 设置环境变量
ENV DATABASE_PATH=/data/secretary.db
ENV FLASK_SECRET_KEY=default_secret_key_please_change_in_env
ENV LOG_DIR=/data/logs

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "run_all.py"]