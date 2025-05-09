# SocialInsight - 社交媒体内容分析与监控平台

## 项目简介

Secretary 是一个自动化的社交媒体分析工具，专门用于监控和分析社交媒体平台上的内容，并通过 AI 进行智能分析。该工具能够自动抓取指定账号的最新发言，根据配置的分析提示词进行内容分析，并将分析结果通过企业微信机器人、个人微信号推送给指定用户。通过灵活配置分析提示词，可以针对不同主题（如财经、政治、科技等）进行定制化分析。

## 主要功能

- 支持多个社交媒体平台的监控（目前支持 Truth Social 和 Twitter）
- 可配置多个监控账号，每个账号可以设置不同的分析提示词
- 支持自定义分析主题和维度，通过配置提示词实现灵活的分析策略
- 使用 AI 进行内容翻译和分析
- 灵活的消息推送支持：
  - 支持企业微信多机器人配置（可同时推送到财经、政治、科技等不同主题的群组）
  - 支持基于 [Gewechat](https://github.com/Devo919/Gewechat) 的个人微信推送
  - 支持基于 [Lagrange](https://github.com/LagrangeDev/Lagrange.Core) 的 个人 QQ 群消息推送
  - 可通过环境变量灵活开启/关闭不同的推送通道
- 使用 AI 进行内容翻译和分析，支持多种 LLM 模型：
  - 支持配置任意符合 OpenAI 接口标准的模型
  - 可自定义模型参数（API 地址、密钥等）
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
curl -O https://raw.githubusercontent.com/zkd8907/secretary/main/docker-compose.yml

# 启动容器
docker-compose up -d
```

2. 访问 Web 界面完成初始化设置：

打开浏览器访问 http://localhost:5000，系统会自动跳转到初始化页面，您需要：
- 设置管理员账号和密码
- 配置 LLM API 密钥（如 OpenAI API 密钥）
- 点击"完成初始化"按钮

3. 登录系统并完成其他配置：

使用您设置的管理员账号和密码登录系统，然后在系统设置中配置：
- Twitter 账号信息
- 推送设置（Apprise URLs）
- 代理设置（如果需要）
- 自动回复设置（如果需要）

4. 添加要监控的社交媒体账号：

在"账号管理"页面添加要监控的 Twitter 账号，并配置分析提示词。

### 方式二：手动安装

1. 克隆项目到本地：
```bash
git clone https://github.com/zkd8907/secretary.git
cd secretary
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

环境变量说明：
- `FLASK_SECRET_KEY`: Web应用的密钥，用于会话安全
- `DATABASE_PATH`: 数据库文件路径，默认为 `secretary.db`
- `TWITTER_USERNAME`: Twitter 平台的用户名
- `TWITTER_PASSWORD`: Twitter 平台的密码
- `TWITTER_SESSION`: 之前登录过的 Twitter 平台的登录票据
- `LLM_API_MODEL`: 使用的 LLM 模型名称，如 `grok-2-latest`
- `LLM_API_KEY`: LLM API 密钥
- `LLM_API_BASE`: LLM API 基础地址，默认为 `https://api.x.ai/v1`
- `LLM_PROCESS_MAX_RETRIED`: LLM 处理失败时的最大重试次数，默认为 3
- `APPRISE_URLS`: Apprise 推送 URL，支持多种推送方式，多个 URL 用逗号分隔
- `HTTP_PROXY`: HTTP 代理地址，用于访问 Twitter 等需要代理的网站
- `ENABLE_AUTO_REPLY`: 是否启用自动回复功能，值为 `true`/`false`
- `AUTO_REPLY_PROMPT`: 自动回复的提示词模板
- `SCHEDULER_INTERVAL_MINUTES`: 定时任务执行间隔（分钟），默认为 30
- `LOG_DIR`: 日志文件目录，默认为 `logs`
- `LOG_LEVEL`: 日志级别，可选值为 `debug`、`info`、`warning`、`error`、`critical`，默认为 `info`
- `LOG_TO_CONSOLE`: 是否将日志输出到控制台，值为 `true`/`false`，默认为 `true`

## 配置说明

### 环境变量

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

### 监控账号配置

创建 `config/social-networks.yml` 文件，配置需要监控的社交媒体账号：
```yaml
social_networks:
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
> 2. 在配置企业微信机器人 ID 时，需要使用 `$` 前缀来引用环境变量，例如：`$WECOM_TRUMP_ROBOT_ID`
>
> 如果返回的 JSON 格式不正确或缺少必需属性，程序将无法正常处理分析结果。

## 使用方法

### Web 管理界面

1. 访问 Web 界面：http://localhost:5000
2. 使用管理员账号登录
3. 在"账号管理"页面添加要监控的 Twitter 账号
4. 在"系统设置"页面配置推送、代理等选项
5. 系统会自动按照设定的时间间隔执行监控任务

### 手动执行

如果需要手动执行监控任务：

```bash
# 使用 Docker
docker exec -it secretary-secretary-1 python main.py

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

## 注意事项

- 确保网络连接正常，访问 Twitter 可能需要代理
- 首次使用时需要在 Web 界面完成初始化设置
- 推送通知需要正确配置 Apprise URLs
- 建议使用 Python 3.9 或更高版本
- 每个监控账号可以配置不同的分析提示词和推送目标
- 提示词配置决定了分析的主题和维度，可以根据需求灵活调整
- Twitter 登录后会生成会话文件，可以在系统配置中保存会话数据
- 当 LLM 返回的 JSON 格式无法解析时，系统会自动重试，重试次数由环境变量 `LLM_PROCESS_MAX_RETRIED` 控制，默认为 3 次
- 如果重试次数用完仍然无法解析 JSON，系统会跳过当前内容的处理并继续处理下一条内容
- 使用 Docker 部署时，数据会保存在 `./data` 目录中，请确保该目录有足够的权限

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。
