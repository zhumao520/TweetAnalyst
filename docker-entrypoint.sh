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
mkdir -p /data /app/logs
chmod -R 755 /data /app/logs

# 检查数据库目录权限
if [ ! -w "/data" ]; then
    echo -e "${RED}警告: /data 目录没有写入权限，可能导致数据库无法创建${NC}"
    echo -e "${YELLOW}尝试修复权限...${NC}"
    chmod -R 755 /data
    if [ ! -w "/data" ]; then
        echo -e "${RED}无法修复 /data 目录权限，请检查卷挂载设置${NC}"
        # 在CI/CD环境中，这是一个严重错误，应该立即退出
        exit 1
    else
        echo -e "${GREEN}已修复 /data 目录权限${NC}"
    fi
fi

# 强制设置数据库路径环境变量
echo -e "${GREEN}设置数据库路径环境变量...${NC}"
export DATABASE_PATH="/data/tweetAnalyst.db"
echo -e "${GREEN}DATABASE_PATH已设置为: $DATABASE_PATH${NC}"

# 检查并清理重复的数据库文件
echo -e "${GREEN}检查并清理数据库文件...${NC}"

# 定义可能的数据库文件位置
MAIN_DB="/data/tweetAnalyst.db"
LOWERCASE_DB="/data/tweetanalyst.db"
INSTANCE_DB="/app/instance/tweetAnalyst.db"
INSTANCE_LOWERCASE_DB="/app/instance/tweetanalyst.db"

# 检查哪些数据库文件存在
echo -e "${YELLOW}检查数据库文件存在情况...${NC}"
if [ -f "$MAIN_DB" ]; then
    echo -e "${GREEN}  ✓ 主数据库存在: $MAIN_DB${NC}"
fi
if [ -f "$LOWERCASE_DB" ]; then
    echo -e "${YELLOW}  ! 小写数据库存在: $LOWERCASE_DB${NC}"
fi
if [ -f "$INSTANCE_DB" ]; then
    echo -e "${YELLOW}  ! 实例数据库存在: $INSTANCE_DB${NC}"
fi
if [ -f "$INSTANCE_LOWERCASE_DB" ]; then
    echo -e "${YELLOW}  ! 实例小写数据库存在: $INSTANCE_LOWERCASE_DB${NC}"
fi

# 处理重复数据库文件
if [ -f "$MAIN_DB" ]; then
    echo -e "${GREEN}主数据库已存在，清理其他重复文件...${NC}"

    # 备份并删除其他数据库文件
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    if [ -f "$LOWERCASE_DB" ]; then
        echo -e "${YELLOW}备份小写数据库: $LOWERCASE_DB -> ${LOWERCASE_DB}.bak.${TIMESTAMP}${NC}"
        mv "$LOWERCASE_DB" "${LOWERCASE_DB}.bak.${TIMESTAMP}"
    fi

    if [ -f "$INSTANCE_DB" ]; then
        echo -e "${YELLOW}备份实例数据库: $INSTANCE_DB -> ${INSTANCE_DB}.bak.${TIMESTAMP}${NC}"
        mv "$INSTANCE_DB" "${INSTANCE_DB}.bak.${TIMESTAMP}"
    fi

    if [ -f "$INSTANCE_LOWERCASE_DB" ]; then
        echo -e "${YELLOW}备份实例小写数据库: $INSTANCE_LOWERCASE_DB -> ${INSTANCE_LOWERCASE_DB}.bak.${TIMESTAMP}${NC}"
        mv "$INSTANCE_LOWERCASE_DB" "${INSTANCE_LOWERCASE_DB}.bak.${TIMESTAMP}"
    fi

else
    echo -e "${YELLOW}主数据库不存在，寻找其他数据库文件...${NC}"

    # 按优先级选择数据库文件
    if [ -f "$LOWERCASE_DB" ]; then
        echo -e "${YELLOW}使用小写数据库文件，重命名为主数据库: $LOWERCASE_DB -> $MAIN_DB${NC}"
        mv "$LOWERCASE_DB" "$MAIN_DB"
    elif [ -f "$INSTANCE_DB" ]; then
        echo -e "${YELLOW}使用实例数据库文件，移动为主数据库: $INSTANCE_DB -> $MAIN_DB${NC}"
        mv "$INSTANCE_DB" "$MAIN_DB"
    elif [ -f "$INSTANCE_LOWERCASE_DB" ]; then
        echo -e "${YELLOW}使用实例小写数据库文件，移动为主数据库: $INSTANCE_LOWERCASE_DB -> $MAIN_DB${NC}"
        mv "$INSTANCE_LOWERCASE_DB" "$MAIN_DB"
    else
        echo -e "${GREEN}没有找到现有数据库文件，将在应用启动时创建新的数据库${NC}"
    fi
fi

echo -e "${GREEN}数据库文件清理完成，确保只使用: $DATABASE_PATH${NC}"

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

# 检查并安装必要的依赖
echo -e "${GREEN}检查必要的依赖...${NC}"

# 使用python模块导入检查代替pip list，避免管道错误
check_module() {
    python -c "import $1" 2>/dev/null
    return $?
}

install_if_needed() {
    local module_name=$1
    local package_name=$2

    if check_module "$module_name"; then
        echo -e "${GREEN}${package_name}已安装${NC}"
    else
        echo -e "${YELLOW}未安装${package_name}，正在安装...${NC}"
        pip install --no-cache-dir "$package_name" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}${package_name}安装成功${NC}"
        else
            echo -e "${RED}${package_name}安装失败${NC}"
        fi
    fi
}

# 完整的依赖检查和安装函数
install_requirements() {
    local requirements_file="/app/requirements.txt"

    if [ ! -f "$requirements_file" ]; then
        echo -e "${RED}未找到requirements.txt文件，跳过依赖安装${NC}"
        return 1
    fi

    echo -e "${GREEN}开始检查和安装requirements.txt中的所有依赖...${NC}"

    # 读取requirements.txt并逐行处理
    local total_packages=0
    local installed_packages=0
    local failed_packages=0

    while IFS= read -r line || [ -n "$line" ]; do
        # 跳过空行和注释行
        if [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]]; then
            continue
        fi

        # 提取包名（去掉版本要求）
        local package_spec="$line"
        local package_name=$(echo "$package_spec" | sed 's/[>=<!=].*//' | sed 's/\[.*\]//' | tr -d '[:space:]')

        # 跳过空包名
        if [[ -z "$package_name" ]]; then
            continue
        fi

        total_packages=$((total_packages + 1))

        echo -e "${YELLOW}检查包: $package_name${NC}"

        # 将包名转换为Python模块名（处理常见的命名差异）
        local module_name="$package_name"
        case "$package_name" in
            "Flask-Login") module_name="flask_login" ;;
            "Flask-SQLAlchemy") module_name="flask_sqlalchemy" ;;
            "Flask-WTF") module_name="flask_wtf" ;;
            "python-dotenv") module_name="dotenv" ;;
            "pyyaml") module_name="yaml" ;;
            "tweety-ns") module_name="tweety" ;;
            "langchain-openai") module_name="langchain_openai" ;;
            "langchain-core") module_name="langchain_core" ;;
            *) module_name=$(echo "$package_name" | tr '[:upper:]' '[:lower:]' | tr '-' '_') ;;
        esac

        # 检查模块是否已安装
        if check_module "$module_name"; then
            echo -e "${GREEN}  ✓ $package_name 已安装${NC}"
            installed_packages=$((installed_packages + 1))
        else
            echo -e "${YELLOW}  → 正在安装 $package_name...${NC}"

            # 尝试安装包
            if pip install --no-cache-dir "$package_spec" >/dev/null 2>&1; then
                echo -e "${GREEN}  ✓ $package_name 安装成功${NC}"
                installed_packages=$((installed_packages + 1))
            else
                echo -e "${RED}  ✗ $package_name 安装失败${NC}"
                failed_packages=$((failed_packages + 1))

                # 尝试不带版本要求安装
                if pip install --no-cache-dir "$package_name" >/dev/null 2>&1; then
                    echo -e "${YELLOW}  ⚠ $package_name 安装成功（忽略版本要求）${NC}"
                    installed_packages=$((installed_packages + 1))
                    failed_packages=$((failed_packages - 1))
                fi
            fi
        fi
    done < "$requirements_file"

    # 输出安装总结
    echo -e "${GREEN}===== 依赖安装总结 =====${NC}"
    echo -e "${GREEN}总包数: $total_packages${NC}"
    echo -e "${GREEN}已安装: $installed_packages${NC}"
    if [ $failed_packages -gt 0 ]; then
        echo -e "${RED}安装失败: $failed_packages${NC}"
        echo -e "${YELLOW}注意: 某些包安装失败，应用可能无法正常运行${NC}"
    else
        echo -e "${GREEN}所有依赖安装成功！${NC}"
    fi

    return 0
}

# 执行完整的依赖安装
install_requirements

# 设置默认环境变量
if [ -z "$AUTO_FETCH_ENABLED" ]; then
    echo -e "${YELLOW}未设置AUTO_FETCH_ENABLED，使用默认值: false${NC}"
    export AUTO_FETCH_ENABLED="false"
fi

if [ "$AUTO_FETCH_ENABLED" = "true" ]; then
    echo -e "${GREEN}已启用自动抓取功能${NC}"
else
    echo -e "${YELLOW}自动抓取功能已禁用，请通过Web界面手动启动抓取任务${NC}"
fi

# 设置推送队列配置
if [ -z "$PUSH_QUEUE_ENABLED" ]; then
    echo -e "${YELLOW}未设置PUSH_QUEUE_ENABLED，使用默认值: true${NC}"
    export PUSH_QUEUE_ENABLED="true"
fi

if [ -z "$PUSH_QUEUE_INTERVAL_SECONDS" ]; then
    echo -e "${YELLOW}未设置PUSH_QUEUE_INTERVAL_SECONDS，使用默认值: 30${NC}"
    export PUSH_QUEUE_INTERVAL_SECONDS="30"
fi

if [ "$PUSH_QUEUE_ENABLED" = "true" ]; then
    echo -e "${GREEN}已启用推送队列功能，处理间隔: ${PUSH_QUEUE_INTERVAL_SECONDS}秒${NC}"

    # 检查是否是主容器
    if [ "$HOSTNAME" = "tweetAnalyst" ]; then
        echo -e "${GREEN}主容器不启动推送队列处理器，由专用容器处理${NC}"
    else
        echo -e "${GREEN}这是推送队列处理容器，将启动推送队列处理器${NC}"
    fi
else
    echo -e "${YELLOW}推送队列功能已禁用，将使用直接推送模式${NC}"
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
