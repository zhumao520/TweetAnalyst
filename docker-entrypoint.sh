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

# 检查SOCKS代理支持
if [[ -n "$HTTP_PROXY" && "$HTTP_PROXY" == socks* ]] || [[ -n "$HTTPS_PROXY" && "$HTTPS_PROXY" == socks* ]]; then
    echo -e "${YELLOW}检测到SOCKS代理，确保安装了必要的支持...${NC}"
    pip install --no-cache-dir httpx[socks] socksio
fi

# 检查依赖
echo -e "${GREEN}检查依赖...${NC}"
python -c "import tweety" || pip install --no-cache-dir tweety-ns
python -c "import flask" || pip install --no-cache-dir Flask
python -c "import flask_sqlalchemy" || pip install --no-cache-dir Flask-SQLAlchemy
python -c "import openai" || pip install --no-cache-dir openai
python -c "import psutil" || pip install --no-cache-dir psutil
python -c "import apprise" || pip install --no-cache-dir apprise

# 设置默认LLM API
if [ -z "$LLM_API_BASE" ]; then
    echo -e "${YELLOW}未设置LLM_API_BASE，使用默认值: https://api.x.ai/v1${NC}"
    export LLM_API_BASE="https://api.x.ai/v1"
fi

if [ -z "$LLM_API_MODEL" ]; then
    echo -e "${YELLOW}未设置LLM_API_MODEL，使用默认值: grok-2-latest${NC}"
    export LLM_API_MODEL="grok-2-latest"
fi

# 启动应用
echo -e "${GREEN}启动应用...${NC}"
exec python run_all.py
