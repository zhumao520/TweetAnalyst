#!/bin/bash

# TweetAnalyst 应用重置脚本
# 用于重置应用到初始状态

set -e

# 设置颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== TweetAnalyst 应用重置脚本 =====${NC}"

# 确认操作
echo -e "${YELLOW}警告: 此操作将删除所有数据，包括：${NC}"
echo -e "${YELLOW}  - 数据库文件${NC}"
echo -e "${YELLOW}  - 日志文件${NC}"
echo -e "${YELLOW}  - 缓存文件${NC}"
echo -e "${YELLOW}  - 临时文件${NC}"
echo ""
read -p "确定要继续吗？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}操作已取消${NC}"
    exit 0
fi

echo -e "${GREEN}开始重置应用...${NC}"

# 停止可能运行的进程
echo -e "${GREEN}停止运行中的进程...${NC}"
pkill -f "python.*run_all.py" || true
pkill -f "python.*web_app.py" || true
pkill -f "python.*main.py" || true

# 删除数据库文件
echo -e "${GREEN}删除数据库文件...${NC}"
rm -f instance/*.db
rm -f *.db
rm -f /data/*.db 2>/dev/null || true

# 删除日志文件
echo -e "${GREEN}删除日志文件...${NC}"
rm -rf logs/
rm -f *.log

# 删除缓存文件
echo -e "${GREEN}删除缓存文件...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

# 删除临时文件
echo -e "${GREEN}删除临时文件...${NC}"
rm -rf tmp/
rm -rf temp/
rm -f *.tmp

# 重新创建必要的目录
echo -e "${GREEN}重新创建目录结构...${NC}"
mkdir -p instance
mkdir -p logs
mkdir -p data

# 设置环境变量强制初始化
echo -e "${GREEN}设置强制初始化标志...${NC}"
if [ -f .env ]; then
    # 如果.env文件存在，更新FIRST_LOGIN
    if grep -q "FIRST_LOGIN" .env; then
        sed -i 's/FIRST_LOGIN=.*/FIRST_LOGIN=true/' .env
    else
        echo "FIRST_LOGIN=true" >> .env
    fi
else
    # 如果.env文件不存在，创建一个
    echo "FIRST_LOGIN=true" > .env
fi

echo -e "${GREEN}应用重置完成！${NC}"
echo -e "${YELLOW}下次启动应用时将进行初始化设置${NC}"
echo ""
echo -e "${GREEN}启动应用请运行:${NC}"
echo -e "${GREEN}  python run_all.py${NC}"
echo -e "${GREEN}或者:${NC}"
echo -e "${GREEN}  docker-compose up -d${NC}"
