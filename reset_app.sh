#!/bin/bash

# 重置TweetAnalyst应用的脚本
# 作用：备份并删除数据库，删除配置文件，重启应用程序

# 设置颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}===== TweetAnalyst应用重置脚本 =====${NC}"
echo -e "${YELLOW}此脚本将备份并删除数据库和配置文件，然后重启应用程序${NC}"
echo -e "${RED}警告: 此操作将删除所有数据和配置，请确保您了解风险${NC}"
echo ""

# 确认操作
read -p "是否继续? (y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo -e "${YELLOW}操作已取消${NC}"
    exit 0
fi

# 创建备份目录
echo -e "${GREEN}创建备份目录...${NC}"
BACKUP_DIR="/data/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# 备份数据库
if [ -f "/data/tweetanalyst.db" ]; then
    echo -e "${GREEN}备份数据库...${NC}"
    cp /data/tweetanalyst.db $BACKUP_DIR/
    echo -e "${GREEN}数据库已备份到 $BACKUP_DIR/tweetanalyst.db${NC}"
else
    echo -e "${YELLOW}数据库文件不存在，跳过备份${NC}"
fi

# 备份配置文件
echo -e "${GREEN}备份配置文件...${NC}"
if [ -f "/data/.env" ]; then
    cp /data/.env $BACKUP_DIR/
    echo -e "${GREEN}.env文件已备份到 $BACKUP_DIR/.env${NC}"
fi

if [ -d "/app/config" ]; then
    mkdir -p $BACKUP_DIR/config
    cp -r /app/config/* $BACKUP_DIR/config/
    echo -e "${GREEN}配置目录已备份到 $BACKUP_DIR/config/${NC}"
fi

# 备份日志文件
echo -e "${GREEN}备份日志文件...${NC}"
if [ -d "/app/logs" ]; then
    mkdir -p $BACKUP_DIR/logs
    cp -r /app/logs/* $BACKUP_DIR/logs/
    echo -e "${GREEN}日志文件已备份到 $BACKUP_DIR/logs/${NC}"
fi

echo -e "${GREEN}所有文件已备份到 $BACKUP_DIR${NC}"
echo ""

# 删除数据库和配置文件
echo -e "${RED}开始删除文件...${NC}"

if [ -f "/data/tweetanalyst.db" ]; then
    rm /data/tweetanalyst.db
    echo -e "${RED}数据库已删除${NC}"
fi

if [ -f "/data/.env" ]; then
    rm /data/.env
    echo -e "${RED}.env文件已删除${NC}"
fi

if [ -d "/app/config" ]; then
    # 只删除配置文件，保留目录结构
    rm -f /app/config/social-networks.yml
    echo -e "${RED}配置文件已删除${NC}"
fi

# 清空日志文件
if [ -d "/app/logs" ]; then
    find /app/logs -type f -name "*.log" -exec sh -c 'echo "" > {}' \;
    echo -e "${RED}日志文件已清空${NC}"
fi

echo ""
echo -e "${GREEN}文件删除完成${NC}"

# 设置FIRST_LOGIN环境变量
echo -e "${GREEN}设置FIRST_LOGIN环境变量...${NC}"
export FIRST_LOGIN=true
echo -e "${GREEN}FIRST_LOGIN环境变量已设置为true${NC}"

# 重启应用程序
echo -e "${YELLOW}准备重启应用程序...${NC}"
echo -e "${YELLOW}注意: 此脚本无法直接重启容器，将尝试重启应用进程${NC}"

# 查找并终止Python进程
echo -e "${GREEN}终止当前运行的Python进程...${NC}"
pkill -f "python run_web.py" || true
pkill -f "python run_scheduler.py" || true
pkill -f "python run_all.py" || true

# 等待进程终止
sleep 2

# 启动应用程序
echo -e "${GREEN}启动应用程序...${NC}"
cd /app
if [ -f "/app/run_all.py" ]; then
    nohup python run_all.py > /dev/null 2>&1 &
    echo -e "${GREEN}应用程序已在后台启动${NC}"
else
    echo -e "${RED}找不到run_all.py文件，尝试分别启动web和scheduler${NC}"
    if [ -f "/app/run_web.py" ]; then
        nohup python run_web.py > /dev/null 2>&1 &
        echo -e "${GREEN}Web应用已在后台启动${NC}"
    else
        echo -e "${RED}找不到run_web.py文件，无法启动Web应用${NC}"
    fi

    if [ -f "/app/run_scheduler.py" ]; then
        sleep 3
        nohup python run_scheduler.py > /dev/null 2>&1 &
        echo -e "${GREEN}调度器已在后台启动${NC}"
    else
        echo -e "${RED}找不到run_scheduler.py文件，无法启动调度器${NC}"
    fi
fi

echo ""
echo -e "${GREEN}===== 重置操作完成 =====${NC}"
echo -e "${GREEN}请访问Web界面完成初始化设置${NC}"
echo -e "${YELLOW}备份文件位于: $BACKUP_DIR${NC}"
echo -e "${YELLOW}如果应用程序未正常启动，请考虑重启整个容器${NC}"
