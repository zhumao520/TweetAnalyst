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
chmod -R 777 /data

# 检查数据库目录权限
if [ ! -w "/data" ]; then
    echo -e "${RED}警告: /data 目录没有写入权限，可能导致数据库无法创建${NC}"
    echo -e "${YELLOW}尝试修复权限...${NC}"
    chmod -R 777 /data
    if [ ! -w "/data" ]; then
        echo -e "${RED}无法修复 /data 目录权限，请检查卷挂载设置${NC}"
        # 在CI/CD环境中，这是一个严重错误，应该立即退出
        exit 1
    else
        echo -e "${GREEN}已修复 /data 目录权限${NC}"
    fi
fi

# 检查代理设置
if [[ -n "$HTTP_PROXY" ]]; then
    echo -e "${GREEN}检测到HTTP_PROXY环境变量: $HTTP_PROXY${NC}"

    # 特殊处理SOCKS代理支持
    if [[ "$HTTP_PROXY" == socks* ]]; then
        echo -e "${YELLOW}检测到SOCKS代理${NC}"
    fi
fi

if [[ -n "$HTTPS_PROXY" ]]; then
    echo -e "${GREEN}检测到HTTPS_PROXY环境变量: $HTTPS_PROXY${NC}"

    # 特殊处理SOCKS代理支持
    if [[ "$HTTPS_PROXY" == socks* ]]; then
        echo -e "${YELLOW}检测到SOCKS代理${NC}"
    fi
fi

# 依赖已在Dockerfile中安装
echo -e "${GREEN}所有依赖已在镜像构建时安装${NC}"

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
