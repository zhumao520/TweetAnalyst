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

# 检查SOCKS代理
if [[ -n "$HTTP_PROXY" && "$HTTP_PROXY" == socks* ]] || [[ -n "$HTTPS_PROXY" && "$HTTPS_PROXY" == socks* ]]; then
    echo -e "${YELLOW}检测到SOCKS代理，检查必要的支持...${NC}"
    if ! python -c "import socksio" &>/dev/null; then
        echo -e "${YELLOW}安装SOCKS代理支持...${NC}"
        pip install --no-cache-dir httpx[socks] socksio
    else
        echo -e "${GREEN}SOCKS代理支持已安装${NC}"
    fi
fi

# 快速检查关键依赖
echo -e "${GREEN}检查关键依赖...${NC}"

# 检查Flask-WTF (解决之前的问题)
if ! python -c "import flask_wtf" &>/dev/null; then
    echo -e "${YELLOW}安装缺失的Flask-WTF依赖...${NC}"
    pip install --no-cache-dir Flask-WTF==1.1.1 Flask==2.3.3 Werkzeug==2.3.7
else
    echo -e "${GREEN}Flask-WTF依赖检查通过${NC}"
fi

# 检查其他关键依赖
MISSING_DEPS=0
for pkg in "flask" "flask_sqlalchemy" "openai" "tweety" "apprise" "langchain_openai"; do
    if ! python -c "import $pkg" &>/dev/null; then
        MISSING_DEPS=1
        case $pkg in
            "flask") pip install --no-cache-dir Flask==2.3.3 ;;
            "flask_sqlalchemy") pip install --no-cache-dir Flask-SQLAlchemy==3.1.1 ;;
            "openai") pip install --no-cache-dir openai==1.12.0 ;;
            "tweety") pip install --no-cache-dir tweety-ns==0.9.0 ;;
            "apprise") pip install --no-cache-dir apprise==1.7.1 ;;
            "langchain_openai") pip install --no-cache-dir langchain-openai==0.0.5 langchain-core==0.1.15 ;;
        esac
        echo -e "${YELLOW}已安装缺失的依赖: $pkg${NC}"
    fi
done

if [ $MISSING_DEPS -eq 0 ]; then
    echo -e "${GREEN}所有依赖检查通过${NC}"
fi

# 设置默认LLM API
if [ -z "$LLM_API_BASE" ]; then
    echo -e "${YELLOW}未设置LLM_API_BASE，使用默认值: https://api.x.ai/v1${NC}"
    export LLM_API_BASE="https://api.x.ai/v1"
fi

if [ -z "$LLM_API_MODEL" ]; then
    echo -e "${YELLOW}未设置LLM_API_MODEL，使用默认值: grok-3-mini-beta${NC}"
    export LLM_API_MODEL="grok-3-mini-beta"
fi

# 确保使用正确的API端点
echo -e "${GREEN}使用API基础URL: $LLM_API_BASE${NC}"
echo -e "${GREEN}使用模型: $LLM_API_MODEL${NC}"

# 启动应用
echo -e "${GREEN}启动应用...${NC}"
exec python run_all.py
