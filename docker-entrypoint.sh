#!/bin/bash
set -e

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== TweetAnalyst应用启动脚本 =====${NC}"

# 创建必要的目录
echo -e "${GREEN}创建必要的目录...${NC}"
mkdir -p /data /data/logs
chmod -R 755 /data

# 检查代理设置
if [[ -n "$HTTP_PROXY" ]]; then
    echo -e "${GREEN}检测到HTTP_PROXY环境变量: $HTTP_PROXY${NC}"
fi

if [[ -n "$HTTPS_PROXY" ]]; then
    echo -e "${GREEN}检测到HTTPS_PROXY环境变量: $HTTPS_PROXY${NC}"
fi

# 检查依赖
echo -e "${GREEN}检查依赖...${NC}"
python -c "import tweety" || pip install --no-cache-dir tweety-ns
python -c "import flask" || pip install --no-cache-dir Flask
python -c "import flask_sqlalchemy" || pip install --no-cache-dir Flask-SQLAlchemy
python -c "import langchain_openai" || pip install --no-cache-dir langchain-openai
python -c "import langchain_core" || pip install --no-cache-dir langchain-core
python -c "import apprise" || pip install --no-cache-dir apprise

# 启动应用
echo -e "${GREEN}启动应用...${NC}"
exec python run_all.py
