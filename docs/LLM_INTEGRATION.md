# LLM集成说明

## 概述

TweetAnalyst使用LangChain生态系统中的`langchain_openai`和`langchain_core`库来与各种LLM API进行交互。这种集成方式提供了更高级的抽象和更好的扩展性，使代码更简洁、更易于维护。

## 依赖

项目依赖以下LLM相关的库：

```
langchain-openai>=0.0.1
langchain-core>=0.1.0
```

这些依赖已经在`requirements.txt`文件中指定。

## 配置

LLM API的配置通过环境变量进行设置：

- `LLM_API_KEY`: API密钥
- `LLM_API_MODEL`: 要使用的模型名称
- `LLM_API_BASE`: API基础URL

这些配置可以在系统初始化时设置，也可以通过Web界面进行修改。

## 支持的API提供商

TweetAnalyst支持多种LLM API提供商，包括但不限于：

- X.AI (Grok)
- OpenAI
- Groq
- Anthropic
- Mistral AI
- 其他兼容OpenAI API格式的提供商

## 代码示例

### 基本用法

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 创建ChatOpenAI实例
chat = ChatOpenAI(
    model="grok-3-mini-beta",  # 或环境变量中的LLM_API_MODEL
    openai_api_base="https://api.x.ai/v1",  # 或环境变量中的LLM_API_BASE
    openai_api_key="your-api-key",  # 或环境变量中的LLM_API_KEY
    temperature=0
)

# 创建消息
messages = [
    SystemMessage(content="你是一个有用的助手。"),
    HumanMessage(content="你好，请介绍一下自己。")
]

# 获取响应
response = chat.invoke(messages)
print(response.content)
```

### 特殊API参数

对于某些API提供商（如X.AI的Grok模型），我们添加了特殊参数：

```python
# 为X.AI或Grok模型添加reasoning_effort参数
model_kwargs = {"reasoning_effort": "high"}
chat = ChatOpenAI(
    model="grok-3-mini-beta",
    openai_api_base="https://api.x.ai/v1",
    openai_api_key="your-api-key",
    temperature=0,
    model_kwargs=model_kwargs
)
```

## 错误处理

TweetAnalyst实现了全面的错误处理机制，包括：

- 指数退避重试
- 特定API错误的分类（限流、认证、服务器错误等）
- 详细的日志记录

## 缓存

为了提高性能和减少API调用，TweetAnalyst实现了LLM响应缓存：

```python
# 使用缓存获取LLM响应
response = get_llm_response_with_cache(prompt, use_cache=True)
```

## 测试

可以使用以下方法测试LLM API连接：

```python
from utils.test_utils import test_llm_connection

# 测试LLM API连接
result = test_llm_connection(prompt="你好，世界！", model="grok-3-mini-beta")
print(result)
```

## 注意事项

1. 确保设置了正确的API密钥和基础URL
2. 不同的API提供商可能需要不同的参数设置
3. 某些API提供商可能需要代理才能正常连接
