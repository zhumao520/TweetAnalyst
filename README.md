# TweetAnalyst - 社交媒体监控与分析助手

<div align="center" style="font-size: 24px; font-weight: bold; margin: 30px 0; padding: 20px; background-color: #f0f8ff; border: 2px solid #0366d6; border-radius: 10px;">
<h1 style="color: #0366d6; font-size: 36px; margin-bottom: 20px;">⭐ 特别鸣谢 ⭐</h1>

<p style="font-size: 26px; margin-bottom: 15px;">
这个项目是由一个<span style="color: #e63946; font-weight: bold; font-size: 30px;">连"Hello World"都要查Stack Overflow的超级菜鸟</span>
</p>

<p style="font-size: 26px; margin-bottom: 15px;">
（也就是那种把"Ctrl+C, Ctrl+V"称为编程技能的人）
</p>

<p style="font-size: 26px; margin-bottom: 15px;">
在下面这家神奇公司的AI魔法帮助下完成的：
</p>

<p style="font-size: 40px; color: #0366d6; font-weight: bold; margin: 20px 0;">
✨ AUGMENT CODE ✨
</p>

<p style="font-size: 26px; margin-bottom: 15px;">
<a href="https://augmentcode.com" style="color: #0366d6; text-decoration: underline;">https://augmentcode.com</a>
</p>

<p style="font-size: 26px; font-style: italic; margin: 20px 0;">
"让AI写代码，我来喝咖啡" —— 懒惰程序员的终极梦想
</p>

<p style="font-size: 30px; color: #0366d6; font-weight: bold; margin-top: 20px;">
由衷感谢 AUGMENT CODE！没有你们，我可能还在思考怎么创建一个文件夹...
</p>
</div>

## 项目简介

TweetAnalyst 是一个自动化的社交媒体分析工具，专门用于监控和分析社交媒体平台上的内容，并通过 AI 进行智能分析。该工具能够自动抓取指定账号的最新发言，根据配置的分析提示词进行内容分析，并将分析结果通过多种渠道（如企业微信机器人、Telegram、Discord等）推送给指定用户。通过灵活配置分析提示词，可以针对不同主题（如财经、政治、科技等）进行定制化分析，实现社交媒体内容的智能筛选和深度解读。

## 主要功能

- 支持多个社交媒体平台的监控（目前仅支持Twitter）
- 可配置多个监控账号，每个账号可以设置不同的分析提示词
- 支持自定义分析主题和维度，通过配置提示词实现灵活的分析策略
- 支持设置特定账号绕过AI判断直接推送所有内容（通过`bypass_ai`参数）
- 使用 AI 进行内容翻译和分析
- 灵活的消息推送支持：
  - 基于 [Apprise](https://github.com/caronc/apprise) 的多平台推送支持
  - 支持 Telegram、Discord、Slack、企业微信等多种推送渠道
  - 支持同时配置多个推送目标，实现消息的多渠道分发
  - 可根据内容标签（tag）将不同主题的内容推送到不同的渠道
  - 支持自定义推送模板，灵活控制推送内容的格式和样式
- 强大的AI内容分析与翻译能力：
  - 基于LangChain生态系统，使用`langchain_openai`和`langchain_core`库
  - 支持配置任意符合OpenAI接口标准的模型（如X.AI的Grok系列、OpenAI的GPT系列等）
  - 灵活的模型配置，可自定义API地址、密钥、模型名称等参数
  - 支持高级参数调整，如reasoning_effort、temperature等
  - 内置错误处理和重试机制，确保分析稳定性
  - 详细说明请参考[LLM集成文档](docs/LLM_INTEGRATION.md)
- 支持多维度分析，例如：
  - 财经分析（市场影响、投资机会等）
  - 政治分析（政策影响、国际关系等）
  - 科技分析（技术趋势、创新影响等）
  - 其他自定义分析维度
- 支持调试模式，方便开发和测试

## 安装说明

### 方式一：使用 Docker（推荐）

1. 使用 Docker Compose 部署（最简单）：

```bash
# 创建数据目录
mkdir -p data

# 下载 docker-compose.yml
curl -O https://raw.githubusercontent.com/zhumao520/tweetAnalyst/main/docker-compose.yml

# 创建.env文件（可选，用于配置环境变量）
cat > .env << EOF
# 基础配置
FLASK_SECRET_KEY=your_random_secret_key_change_this

# LLM API 配置
LLM_API_KEY=your_api_key_here
LLM_API_MODEL=grok-3-mini-beta
LLM_API_BASE=https://api.x.ai/v1

# 代理配置（如果需要）
# HTTP_PROXY=http://your.proxy:port

# 推送配置（可选）
# APPRISE_URLS=tgram://bottoken/ChatID
EOF

# 启动容器
docker-compose up -d
```

2. 访问 Web 界面完成初始化设置：

打开浏览器访问 http://localhost:5000，系统会自动跳转到初始化页面，您需要：
- 设置管理员账号和密码
- 配置 LLM API 密钥（如果未在.env文件中设置）
- 选择LLM模型和API基础URL（默认使用X.AI的Grok模型）
- 点击"完成初始化"按钮

3. 登录系统并完成其他配置：

使用您设置的管理员账号和密码登录系统，然后在系统设置中配置：
- Twitter 账号信息
- 推送设置（Apprise URLs）
- 代理设置（如果需要）
- 自动回复设置（如果需要）
- 数据库自动清理设置（可选）

4. 添加要监控的社交媒体账号：

在"账号管理"页面添加要监控的 Twitter 账号，并配置分析提示词。

### 方式二：手动安装

1. 克隆项目到本地：
```bash
git clone https://github.com/zhumao520/tweetAnalyst.git
cd tweetAnalyst
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
创建 `.env` 文件并添加以下配置：
```
# 基础配置
FLASK_SECRET_KEY=your_random_secret_key

# LLM API 配置
LLM_API_MODEL=grok-2-latest
LLM_API_KEY=your_api_key
LLM_API_BASE=https://api.x.ai/v1

# Twitter 配置
TWITTER_USERNAME=your_twitter_username
TWITTER_PASSWORD=your_twitter_password
# 或者使用会话数据
# TWITTER_SESSION=your_twitter_session_data

# 推送配置（Apprise）
APPRISE_URLS=tgram://bottoken/ChatID,discord://webhook_id/webhook_token

# 代理配置（如果需要）
HTTP_PROXY=http://127.0.0.1:7890

# 自动回复配置
ENABLE_AUTO_REPLY=false
# AUTO_REPLY_PROMPT=

# 定时任务配置
SCHEDULER_INTERVAL_MINUTES=30

# 日志配置
LOG_DIR=logs
LOG_LEVEL=info
```

4. 启动应用：
```bash
# 启动 Web 应用和定时任务
python run_all.py

# 或者分别启动
# 只启动 Web 应用
python run_web.py
# 只启动定时任务
python run_scheduler.py
```

5. 访问 Web 界面：
打开浏览器访问 http://localhost:5000

### 环境变量详细说明

#### 基础配置
- `FLASK_SECRET_KEY`: Web应用的密钥，用于会话安全，建议使用随机字符串
- `DATABASE_PATH`: 数据库文件路径，默认为 `/data/tweetAnalyst.db`（Docker环境）或 `instance/tweetAnalyst.db`（本地环境）
- `FIRST_LOGIN`: 首次登录标志，可选值：
  - `auto`: 自动检测（默认值）
  - `true`: 强制初始化（谨慎使用，会重置数据）
  - `false`: 禁止初始化

#### AI模型配置
- `LLM_API_KEY`: LLM API 密钥，必需参数，用于访问AI模型API
  - 可以在容器启动时通过环境变量提供
  - 也可以在Web界面初始化时设置
  - 或在系统设置页面中更新
  - 存储在数据库的`system_config`表中，标记为敏感信息
- `LLM_API_MODEL`: 使用的 LLM 模型名称，默认为 `grok-3-mini-beta`
  - 支持X.AI的模型：`grok-3-mini-beta`、`grok-3-mini`、`grok-3-max`等
  - 支持OpenAI的模型：`gpt-4-turbo`、`gpt-3.5-turbo`等
  - 支持任何符合OpenAI接口标准的模型
- `LLM_API_BASE`: LLM API 基础地址
  - X.AI模型默认为 `https://api.x.ai/v1`
  - OpenAI模型默认为 `https://api.openai.com/v1`
  - 可以设置为任何兼容的API端点
- `LLM_PROCESS_MAX_RETRIED`: LLM 处理失败时的最大重试次数，默认为 3

#### 社交媒体账号配置
- `TWITTER_USERNAME`: Twitter 平台的用户名
- `TWITTER_PASSWORD`: Twitter 平台的密码
- `TWITTER_SESSION`: 之前登录过的 Twitter 平台的登录票据（可替代用户名和密码）

#### 推送配置
- `APPRISE_URLS`: Apprise 推送 URL，支持多种推送方式，多个 URL 用逗号分隔
  - 例如：`tgram://bottoken/ChatID,discord://webhook_id/webhook_token`
  - 支持多种推送平台：
    - Telegram: `tgram://bottoken/ChatID`
    - Discord: `discord://webhook_id/webhook_token`
    - Slack: `slack://tokenA/tokenB/tokenC`
    - 企业微信: `wxteams://TokenA/TokenB/TokenC`
    - 更多平台请参考[Apprise文档](https://github.com/caronc/apprise/wiki)
  - 可以为不同内容设置不同的推送目标，通过在监控账号配置中设置`tag`参数

#### 网络配置
- `HTTP_PROXY`: HTTP 代理地址，用于访问 Twitter 等需要代理的网站
  - 例如：`http://127.0.0.1:7890`或`socks5://127.0.0.1:1080`
  - 容器启动时会自动检测并应用代理设置

#### 自动回复配置
- `ENABLE_AUTO_REPLY`: 是否启用自动回复功能，值为 `true`/`false`
- `AUTO_REPLY_PROMPT`: 自动回复的提示词模板

#### 定时任务配置
- `SCHEDULER_INTERVAL_MINUTES`: 定时任务执行间隔（分钟），默认为 30

#### 日志配置
- `LOG_DIR`: 日志文件目录，默认为 `/app/logs`（Docker环境）或 `logs`（本地环境）
- `LOG_LEVEL`: 日志级别，可选值为 `debug`、`info`、`warning`、`error`、`critical`，默认为 `info`
- `LOG_TO_CONSOLE`: 是否将日志输出到控制台，值为 `true`/`false`，默认为 `true`

## 配置说明

### 环境变量与配置文件

#### 环境变量引用格式
环境变量支持两种引用格式：
- `${VAR}` 格式：例如 `${WECOM_TRUMP_ROBOT_ID}`
- `$VAR` 格式：例如 `$WECOM_TRUMP_ROBOT_ID`

这两种格式可以在 YAML 配置文件中的任何值中使用，包括但不限于：
- 企业微信机器人 ID
- 社交媒体账号 ID
- API 密钥
- 其他配置项

系统会自动递归处理所有配置项中的环境变量，将其替换为对应的环境变量值。如果环境变量不存在，将替换为空字符串。

例如，以下配置都是合法的：
```yaml
social_networks:
  - type: truthsocial
    socialNetworkId: $TRUTH_SOCIAL_ID
    apiKey: ${API_KEY}
    weComRobotId: $WECOM_ROBOT_ID
    customField: "前缀_${CUSTOM_VAR}_后缀"
```

#### 配置加载顺序
系统在启动时会按照以下顺序加载配置：

1. **默认配置**：系统内置的默认配置
2. **环境变量**：从操作系统环境变量中读取
3. **.env文件**：从项目根目录或`/data`目录的`.env`文件中读取
4. **数据库配置**：从数据库的`system_config`表中读取
5. **Web界面设置**：用户通过Web界面修改的设置

后加载的配置会覆盖先加载的配置，因此Web界面的设置优先级最高。

### 监控账号配置

创建 `config/social-networks.yml` 文件，配置需要监控的社交媒体账号：
```yaml
social_networks:
  # 示例1：标准配置，使用AI分析内容
  - type: truthsocial
    socialNetworkId: realDonaldTrump
    prompt: >-
      你现在是一名财经专家，请对以下美国总统的发言进行分析，并给按我指定的格式返回分析结果。

      这是你需要分析的内容：{content}

      这是输出格式的说明：
      {
          "is_relevant": "是否与财经相关，且与美股市场或美债市场或科技股或半导体股或中国股票市场或香港股票市场或人民币兑美元汇率或中美关系相关。如果相关就返回1，如果不相关就返回0。只需要返回1或0这两个值之一即可",
          "analytical_briefing": "分析简报"
      }

      其中analytical_briefing的值是一个字符串，它是针对内容所做的分析简报，仅在is_relevant为1时会返回这个值。

      analytical_briefing的内容是markdown格式的，它需要符合下面的规范

      ```markdown
      原始正文，仅当需要分析的内容为英文时，这部分内容才会以markdown中引用的格式返回，否则这部分的内容为原始的正文

      翻译后的内容，仅当需要分析的内容为英文时，才会有这部分的内容。

      ## Brief Analysis

      分析结果。这部分会展示一个列表，列表中分别包含美股市场、美债市场、科技股、半导体股、中国股票市场、香港股票市场、人民币兑美元汇率、中美关系这8个选项。
      每个选项的值为分别为📈利多和📉利空。如果分析内容对于该选项没有影响，就不要针对这个选项返回任何内容。

      ## Summarize

      这部分需要用非常简明扼要的文字对分析结果进行总结，以及解释为什么在上面针对不同选项会得出不同的结论。
      ```
    weComRobotId: $WECOM_TRUMP_ROBOT_ID
    sendToWeChat: true

  # 示例2：绕过AI判断，直接推送所有内容
  - type: twitter
    socialNetworkId: elonmusk
    bypass_ai: true  # 设置为true，所有推文将直接推送，不经过AI判断
    tag: tech
    weComRobotId: $WECOM_TECH_ROBOT_ID

  # 示例3：标准配置，使用AI分析内容
  - type: twitter
    socialNetworkId:
      - myfxtrader
      - zaobaosg
      - business
      - HAOHONG_CFA
    prompt: >-
      你现在是一名财经专家，请对以下财经博主的发言进行分析，并给按我指定的格式返回分析结果。
      # ... 其他配置与上面类似 ...
    weComRobotId: $WECOM_FINANCE_ROBOT_ID
```

> ⚠️ **重要提示**：
> 1. 在配置 prompt 时，必须确保大模型返回的结果是一个合法的 JSON 字符串，并且包含以下两个必需属性：
>    - `is_relevant`：表示内容是否相关，值为 1 或 0
>    - `analytical_briefing`：分析简报内容，仅在 `is_relevant` 为 1 时返回
> 2. 如果设置 `bypass_ai: true`，则系统会跳过AI分析，直接推送该账号的所有新内容，这对于重要账号或需要实时获取所有更新的场景非常有用。
> 3. 在配置企业微信机器人 ID 时，需要使用 `$` 前缀来引用环境变量，例如：`$WECOM_TRUMP_ROBOT_ID`
>
> 如果返回的 JSON 格式不正确或缺少必需属性，程序将无法正常处理分析结果。

## 使用方法

### Web 管理界面

1. 访问 Web 界面：http://localhost:5000
2. 使用管理员账号登录
3. 在"账号管理"页面添加要监控的 Twitter 账号
4. 在"系统设置"页面配置推送、代理等选项
5. 系统会自动按照设定的时间间隔执行监控任务

### 系统功能说明

#### 主要页面功能
- **首页**：显示系统概览，包括监控账号数量、分析结果统计等
- **账号管理**：添加、编辑和删除监控的社交媒体账号
- **分析结果**：查看所有分析结果，支持筛选和搜索
- **数据分析**：查看数据统计和趋势分析
- **配置管理**：配置分析提示词模板和其他系统参数
- **系统设置**：
  - **统一设置中心**：集中管理所有系统设置
  - **导出数据**：导出系统数据备份
  - **导入数据**：导入系统数据
  - **系统测试**：测试系统各组件功能
  - **系统日志**：查看系统运行日志

#### AI配置管理
- 在"统一设置中心"页面的"AI设置"部分，可以配置：
  - LLM API密钥：用于访问AI模型的API密钥
  - LLM API模型：选择使用的AI模型
  - LLM API基础URL：设置API端点地址
- 系统会自动测试API连接，确保配置正确
- 密钥在UI中显示为`******`，保护敏感信息

### 手动执行

如果需要手动执行监控任务：

```bash
# 使用 Docker
docker exec -it tweetAnalyst-tweetAnalyst-1 python main.py

# 本地安装
python main.py
```

程序会自动：
- 抓取配置的社交媒体账号的最新发言
- 根据每个账号配置的提示词进行 AI 分析和翻译
- 生成分析报告
- 通过配置的 Apprise 推送分析结果

## 输出格式

分析结果将以 Markdown 格式推送，包含：
- 发言时间
- 原文内容（如果是英文内容会以引用格式显示）
- 中文翻译（仅当原文为英文时显示）
- 分析结果（根据提示词配置的格式）
- 分析总结

## 重置数据

如果需要重置系统（例如，在测试后或出现问题时），可以使用以下方法：

1. 停止容器：
```bash
docker-compose down
```

2. 删除数据目录：
```bash
rm -rf ./data
```

3. 设置环境变量强制初始化：
```bash
echo "FIRST_LOGIN=true" > .env
```

4. 重新启动容器：
```bash
docker-compose up -d
```

这将删除所有数据并重新初始化系统。请注意，此操作不可逆，请确保在执行前备份重要数据。

## 故障排除

### 缺少依赖问题

如果在启动容器时遇到以下错误：

```
ModuleNotFoundError: No module named 'flask_wtf'
```

这是因为容器中缺少必要的Python依赖。可以通过以下方法解决：

#### 方法1: 在现有容器中安装依赖

```bash
# 找到容器ID
docker ps

# 在容器中安装依赖
docker exec -it <容器ID> pip install Flask-WTF==1.1.1 Flask==2.3.3 Werkzeug==2.3.7

# 重启容器
docker restart <容器ID>
```

#### 方法2: 重新构建镜像

```bash
# 停止并删除现有容器
docker-compose down

# 重新构建镜像（不使用缓存）
docker-compose build --no-cache

# 启动新容器
docker-compose up -d
```

## 注意事项

### 基本使用注意事项
- 确保网络连接正常，访问 Twitter 可能需要代理
- 首次使用时需要在 Web 界面完成初始化设置
- 推送通知需要正确配置 Apprise URLs
- 建议使用 Python 3.9 或更高版本
- 每个监控账号可以配置不同的分析提示词和推送目标
- 提示词配置决定了分析的主题和维度，可以根据需求灵活调整

### AI模型与API密钥管理
- **API密钥存储位置**：
  - API密钥可以通过环境变量提供，也可以在Web界面设置
  - 在容器启动时，系统会按以下顺序查找API密钥：
    1. 环境变量`LLM_API_KEY`
    2. 数据库中的`system_config`表
  - 密钥在数据库中以明文形式存储，但标记为敏感信息，在UI中显示为`******`
  - 在日志中，密钥也会被替换为`******`以保护安全
- **API密钥安全建议**：
  - 使用环境变量或`.env`文件提供API密钥，而不是直接在Web界面输入
  - 确保`.env`文件和数据目录有适当的访问权限限制
  - 定期轮换API密钥，提高安全性
- **模型选择**：
  - 默认使用X.AI的`grok-3-mini-beta`模型，性价比较高
  - 可以根据需要切换到其他模型，如OpenAI的GPT系列
  - 不同模型的分析质量和成本各不相同，请根据实际需求选择

### 数据处理与错误处理
- Twitter 登录后会生成会话文件，可以在系统配置中保存会话数据
- 当 LLM 返回的 JSON 格式无法解析时，系统会自动重试，重试次数由环境变量 `LLM_PROCESS_MAX_RETRIED` 控制，默认为 3 次
- 如果重试次数用完仍然无法解析 JSON，系统会跳过当前内容的处理并继续处理下一条内容

### 数据持久化与备份
- 使用 Docker 部署时，数据会保存在 `./data` 目录中，请确保该目录有足够的权限
- 容器重启后数据会保持不变，因为数据库文件存储在持久化卷中
- 系统会自动检测是否是首次部署，首次部署时会自动初始化数据库
- 建议定期备份`./data`目录，特别是在更新系统或修改配置前
- 如果遇到容器重启后数据丢失问题，请检查以下几点：
  1. 确保 `./data` 目录存在且有正确的权限
  2. 确保 `docker-compose.yml` 中的卷映射配置正确
  3. 可以在 `.env` 文件中设置 `FIRST_LOGIN` 环境变量：
     - `FIRST_LOGIN=auto`：自动检测（默认值，检查数据库文件是否存在）
     - `FIRST_LOGIN=true`：强制初始化（谨慎使用，会重置数据）
     - `FIRST_LOGIN=false`：禁止初始化（确保数据保留）

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。
