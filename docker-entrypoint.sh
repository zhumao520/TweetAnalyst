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

# 自动检测和安装依赖
echo -e "${GREEN}自动检测和安装依赖...${NC}"

# 定义关键依赖映射（模块名:包名）
declare -A DEPENDENCIES=(
    ["flask_wtf"]="Flask-WTF"
    ["flask"]="Flask"
    ["flask_sqlalchemy"]="Flask-SQLAlchemy"
    ["werkzeug"]="Werkzeug"
    ["openai"]="openai"
    ["tweety"]="tweety-ns"
    ["apprise"]="apprise"
    ["langchain_core"]="langchain-core"
    ["langchain_openai"]="langchain-openai"
    ["psutil"]="psutil"
    ["yaml"]="pyyaml"
    ["dotenv"]="python-dotenv"
    ["schedule"]="schedule"
    ["requests"]="requests"
)

# 检查requirements.txt是否存在
if [ -f "/app/requirements.txt" ]; then
    echo -e "${GREEN}检测到requirements.txt文件${NC}"
else
    echo -e "${YELLOW}未检测到requirements.txt文件，将使用内置依赖列表${NC}"
fi

# 检查并安装缺失的依赖
MISSING_DEPS=0
for module in "${!DEPENDENCIES[@]}"; do
    package="${DEPENDENCIES[$module]}"

    # 尝试导入模块
    if ! python -c "import ${module}" &>/dev/null; then
        echo -e "${YELLOW}检测到缺失依赖: ${module} (将安装 ${package})${NC}"

        # 尝试安装包
        if pip install --no-cache-dir "${package}" &>/dev/null; then
            echo -e "${GREEN}成功安装: ${package}${NC}"
        else
            echo -e "${YELLOW}尝试安装兼容版本: ${package}${NC}"
            # 如果安装失败，尝试安装兼容版本
            case "${package}" in
                "Flask")
                    pip install --no-cache-dir "Flask<2.4.0,>=2.0.0" "Werkzeug<2.4.0,>=2.0.0"
                    ;;
                "Flask-WTF")
                    pip install --no-cache-dir "Flask-WTF<1.2.0,>=1.0.0"
                    ;;
                "Flask-SQLAlchemy")
                    pip install --no-cache-dir "Flask-SQLAlchemy<3.2.0,>=3.0.0"
                    ;;
                "openai")
                    pip install --no-cache-dir "openai>=1.0.0"
                    ;;
                "langchain-core")
                    pip install --no-cache-dir "langchain-core>=0.1.0"
                    ;;
                "langchain-openai")
                    pip install --no-cache-dir "langchain-openai>=0.0.1"
                    ;;
                *)
                    # 对于其他包，尝试不指定版本安装
                    pip install --no-cache-dir "${package}"
                    ;;
            esac
        fi
        MISSING_DEPS=1
    fi
done

# 特殊处理SOCKS代理支持
if [[ -n "$HTTP_PROXY" && "$HTTP_PROXY" == socks* ]] || [[ -n "$HTTPS_PROXY" && "$HTTPS_PROXY" == socks* ]]; then
    echo -e "${YELLOW}检测到SOCKS代理，检查必要的支持...${NC}"
    if ! python -c "import socksio" &>/dev/null; then
        echo -e "${YELLOW}安装SOCKS代理支持...${NC}"
        pip install --no-cache-dir "httpx[socks]" socksio
    else
        echo -e "${GREEN}SOCKS代理支持已安装${NC}"
    fi
fi

if [ $MISSING_DEPS -eq 0 ]; then
    echo -e "${GREEN}所有依赖检查通过${NC}"
else
    echo -e "${GREEN}所有缺失依赖已安装${NC}"
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
