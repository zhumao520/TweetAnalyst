import os
import json
import time
import importlib.util
import traceback
from datetime import datetime, timezone
from tweety import Twitter
from utils.redisClient import redis_client
from modules.socialmedia.post import Post
from modules.langchain.llm import get_llm_response
from utils.logger import get_logger
from dotenv import load_dotenv

# 创建日志记录器
logger = get_logger('twitter')

load_dotenv()

# 检查并安装SOCKS代理支持
def ensure_socks_support():
    """
    确保系统支持SOCKS代理

    Returns:
        bool: 是否成功安装SOCKS支持
    """
    # 检查是否已安装socksio
    if importlib.util.find_spec("socksio") is None:
        try:
            logger.info("检测到SOCKS代理，但未安装socksio包，尝试安装...")
            import pip
            pip.main(['install', 'httpx[socks]', '--quiet'])
            logger.info("成功安装SOCKS代理支持")
            return True
        except Exception as e:
            logger.error(f"安装SOCKS代理支持失败: {str(e)}")
            return False
    return True

# 初始化Twitter客户端
def init_twitter_client():
    """
    初始化Twitter客户端

    支持三种登录方式：
    1. 使用会话文件（优先）
    2. 使用账号密码
    3. 使用API密钥（如果配置了）

    同时支持代理设置

    Returns:
        Twitter: Twitter客户端实例
    """
    # 检查代理设置
    proxy = os.getenv('HTTP_PROXY', '')
    if proxy:
        logger.info(f"使用代理连接Twitter: {proxy}")
        os.environ['HTTP_PROXY'] = proxy
        os.environ['HTTPS_PROXY'] = proxy

        # 如果是SOCKS代理，确保安装了必要的包
        if proxy.startswith('socks'):
            if not ensure_socks_support():
                logger.warning("SOCKS代理支持安装失败，可能无法正常连接Twitter")

    # 尝试使用会话文件
    twitter_session = os.getenv('TWITTER_SESSION')
    if twitter_session and twitter_session.strip():
        logger.info("使用会话文件登录Twitter")
        try:
            # 确保session文件目录存在
            session_file = 'session.tw_session'
            session_dir = os.path.dirname(os.path.abspath(session_file))
            if not os.path.exists(session_dir):
                os.makedirs(session_dir)

            with open(session_file, 'w') as f:
                f.write(twitter_session)

            app = Twitter('session')
            app.connect()

            if app.me is not None:
                logger.info(f"成功使用会话文件登录Twitter，用户: {app.me.username}")
                return app
            else:
                logger.warning("会话文件登录失败，尝试使用账号密码登录")
        except Exception as e:
            logger.error(f"使用会话文件登录Twitter时出错: {str(e)}")

    # 尝试使用账号密码
    username = os.getenv('TWITTER_USERNAME')
    password = os.getenv('TWITTER_PASSWORD')

    if username and password:
        logger.info(f"使用账号密码登录Twitter: {username}")
        try:
            app = Twitter('session')
            app.connect()

            if app.me is None:
                app.sign_in(username, password)

                if app.me is not None:
                    logger.info(f"成功使用账号密码登录Twitter，用户: {app.me.username}")
                    return app
                else:
                    logger.error("账号密码登录失败")
            else:
                logger.info(f"已登录Twitter，用户: {app.me.username}")
                return app
        except Exception as e:
            logger.error(f"使用账号密码登录Twitter时出错: {str(e)}")

    # 尝试使用API密钥（如果配置了）
    api_key = os.getenv('TWITTER_API_KEY')
    api_secret = os.getenv('TWITTER_API_SECRET')
    access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    access_secret = os.getenv('TWITTER_ACCESS_SECRET')

    if api_key and api_secret and access_token and access_secret:
        logger.info("使用API密钥登录Twitter")
        try:
            # 注意：tweety库目前不直接支持API密钥登录
            # 这里是一个占位，如果将来支持或者切换到其他库，可以实现这部分
            logger.warning("当前版本不支持API密钥登录，请使用会话文件或账号密码登录")
        except Exception as e:
            logger.error(f"使用API密钥登录Twitter时出错: {str(e)}")

    logger.error("所有Twitter登录方式均失败")
    return None

# 初始化Twitter客户端变量
app = None

# 延迟初始化，确保在使用时已加载配置
def ensure_initialized():
    """确保Twitter客户端已初始化"""
    global app
    if app is None:
        try:
            logger.info("首次使用时初始化Twitter客户端")
            app = init_twitter_client()
            return app is not None
        except Exception as e:
            logger.error(f"初始化Twitter客户端时出错: {str(e)}")
            return False
    return True

# 添加重新初始化函数，用于在需要时重新连接
def reinit_twitter_client():
    """
    重新初始化Twitter客户端

    Returns:
        bool: 是否成功初始化
    """
    global app
    try:
        logger.info("尝试重新初始化Twitter客户端")
        app = init_twitter_client()
        return app is not None
    except Exception as e:
        logger.error(f"重新初始化Twitter客户端时出错: {str(e)}")
        return False


def fetch(user_id: str, limit: int = None) -> list[Post]:
    """
    获取指定用户的最新推文

    Args:
        user_id (str): Twitter用户ID
        limit (int, optional): 限制返回的推文数量，用于测试

    Returns:
        list[Post]: 帖子列表
    """
    global app
    # 确保Twitter客户端已初始化
    if not ensure_initialized():
        logger.warning("Twitter客户端未初始化，尝试重新初始化")
        if not reinit_twitter_client():
            logger.error("Twitter客户端初始化失败，无法获取推文")
            return []

    logger.info(f"开始获取用户 {user_id} 的最新推文")

    # 如果是测试模式（指定了limit），则不使用上次处理记录
    if limit is not None:
        logger.debug(f"测试模式：获取用户 {user_id} 的最新 {limit} 条推文")
        cursor = ''
    else:
        # 获取上次处理的最后一条推文ID
        cursor = redis_client.get(f"twitter:{user_id}:last_post_id")

        if cursor is None:
            logger.debug(f"未找到用户 {user_id} 的上次处理记录，将获取最新推文")
            cursor = ''
        else:
            # 如果是字节类型，转换为字符串
            if isinstance(cursor, bytes):
                cursor = str(cursor, encoding='utf-8')
            logger.debug(f"找到用户 {user_id} 的上次处理记录，上次处理的最后一条推文ID: {cursor}")

    try:
        logger.debug(f"调用Twitter API获取用户 {user_id} 的推文")

        # 尝试使用不同的参数组合调用get_tweets
        # 这是为了兼容tweety库的不同版本
        posts = None
        error_messages = []

        # 尝试方法1: 使用cursor和pages参数
        try:
            posts = app.get_tweets(user_id, cursor=cursor, pages=1 if limit is not None else None)
        except Exception as e:
            error_messages.append(f"方法1失败: {str(e)}")

        # 尝试方法2: 使用limit参数
        if posts is None and limit is not None:
            try:
                posts = app.get_tweets(user_id, limit=limit)
            except Exception as e:
                error_messages.append(f"方法2失败: {str(e)}")

        # 尝试方法3: 只使用用户ID
        if posts is None:
            try:
                posts = app.get_tweets(user_id)
            except Exception as e:
                error_messages.append(f"方法3失败: {str(e)}")

        # 如果所有方法都失败，记录错误并返回空列表
        if posts is None:
            logger.error(f"获取用户 {user_id} 的推文失败，尝试了多种方法: {'; '.join(error_messages)}")
            return []

        logger.info(f"成功获取用户 {user_id} 的推文，数量: {len(posts) if posts else 0}")
    except Exception as e:
        logger.error(f"获取用户 {user_id} 的推文时出错: {str(e)}")
        return []

    noneEmptyPosts = []

    # 确保posts是可迭代的
    if posts is None:
        logger.warning("获取到的推文为None，返回空列表")
        return []

    # 如果是测试模式，限制返回数量
    if limit is not None:
        try:
            posts = list(posts)[:limit]
            logger.debug(f"测试模式：限制返回 {limit} 条推文")
        except Exception as e:
            logger.error(f"限制推文数量时出错: {str(e)}")

    for post in posts:
        try:
            # 检查推文是否有效
            if not post:
                logger.warning("跳过无效推文")
                continue

            if 'tweets' in post:
                # 处理推文线程
                logger.debug(f"处理推文线程，ID: {post.id if hasattr(post, 'id') else 'unknown'}")
                latest_id = None
                latest_created_on = None
                combined_text = ""
                latest_url = ""
                poster = None

                # 确保tweets是可迭代的
                if not hasattr(post, 'tweets') or not post.tweets:
                    logger.warning(f"推文线程缺少tweets属性或为空，跳过")
                    continue

                for tweet in post.tweets:
                    if hasattr(tweet, 'text') and tweet.text:
                        combined_text += tweet.text + "\n"
                    if hasattr(tweet, 'created_on') and (latest_created_on is None or tweet.created_on > latest_created_on):
                        latest_created_on = tweet.created_on
                        latest_id = getattr(tweet, 'id', None)
                        latest_url = getattr(tweet, 'url', '')
                        poster = getattr(tweet, 'author', None)

                if combined_text and latest_id and latest_created_on and poster:
                    logger.debug(f"添加推文线程到结果列表，ID: {latest_id}")
                    try:
                        # 确保poster有必要的属性
                        poster_name = getattr(poster, 'name', user_id)
                        poster_url = getattr(poster, 'profile_url', '')

                        noneEmptyPosts.append(
                            Post(latest_id, latest_created_on, combined_text.strip(), latest_url, poster_name, poster_url))
                    except Exception as e:
                        logger.error(f"创建推文线程Post对象时出错: {str(e)}")
                        continue
            elif hasattr(post, 'text') and post.text:
                # 处理单条推文
                try:
                    post_id = getattr(post, 'id', None)
                    if not post_id:
                        logger.warning("推文缺少ID，跳过")
                        continue

                    logger.debug(f"处理单条推文，ID: {post_id}")

                    # 确保post有必要的属性
                    created_on = getattr(post, 'created_on', None)
                    if not created_on:
                        logger.warning(f"推文 {post_id} 缺少创建时间，使用当前时间")
                        from datetime import datetime
                        created_on = datetime.now()

                    post_url = getattr(post, 'url', f"https://twitter.com/{user_id}/status/{post_id}")

                    # 确保author有必要的属性
                    author = getattr(post, 'author', None)
                    if author:
                        author_name = getattr(author, 'name', user_id)
                        author_url = getattr(author, 'profile_url', '')
                    else:
                        author_name = user_id
                        author_url = ''

                    noneEmptyPosts.append(Post(post_id, created_on, post.text,
                                          post_url, author_name, author_url))
                except Exception as e:
                    logger.error(f"创建单条推文Post对象时出错: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"处理推文时出错: {str(e)}")
            continue

    # 更新最后处理的推文ID
    try:
        if posts and hasattr(posts, 'cursor_top') and posts.cursor_top:
            logger.debug(f"更新用户 {user_id} 的最后处理记录，最后一条推文ID: {posts.cursor_top}")
            redis_client.set(f"twitter:{user_id}:last_post_id", posts.cursor_top)
        elif noneEmptyPosts and len(noneEmptyPosts) > 0:
            # 如果没有cursor_top但有处理后的推文，使用第一条推文的ID
            latest_id = str(noneEmptyPosts[0].id)
            logger.debug(f"使用第一条推文ID更新用户 {user_id} 的最后处理记录: {latest_id}")
            redis_client.set(f"twitter:{user_id}:last_post_id", latest_id)
    except Exception as e:
        logger.error(f"更新最后处理推文ID时出错: {str(e)}")

    logger.info(f"用户 {user_id} 的推文处理完成，有效推文数量: {len(noneEmptyPosts)}")
    return noneEmptyPosts


def reply_to_post(post_id: str, content: str) -> bool:
    """
    回复Twitter帖子

    Args:
        post_id (str): 要回复的帖子ID
        content (str): 回复内容

    Returns:
        bool: 是否成功回复
    """
    global app

    # 参数验证
    if not post_id:
        logger.error("回复帖子失败: 帖子ID为空")
        return False

    if not content or not content.strip():
        logger.error(f"回复帖子 {post_id} 失败: 回复内容为空")
        return False

    # 确保Twitter客户端已初始化
    if not ensure_initialized():
        logger.warning("Twitter客户端未初始化，尝试重新初始化")
        if not reinit_twitter_client():
            logger.error("Twitter客户端初始化失败，无法回复帖子")
            return False

    # 检查Twitter客户端是否有reply方法
    if not hasattr(app, 'reply'):
        logger.error("Twitter客户端不支持reply方法，可能是tweety库版本不兼容")
        return False

    logger.info(f"准备回复帖子 {post_id}")
    logger.debug(f"回复内容: {content}")

    # 尝试回复
    max_retries = 3
    retry_delay = 2  # 秒

    for attempt in range(max_retries):
        try:
            app.reply(post_id, content)
            logger.info(f"成功回复帖子 {post_id}")
            return True
        except Exception as e:
            logger.error(f"回复Twitter帖子 {post_id} 时出错 (尝试 {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                import time
                time.sleep(retry_delay)
                # 增加重试延迟时间
                retry_delay *= 2
            else:
                logger.error(f"回复Twitter帖子 {post_id} 失败，已达到最大重试次数")
                return False

    return False


def generate_reply(content: str, prompt_template: str = None) -> str:
    """
    使用LLM生成回复内容

    Args:
        content (str): 原始帖子内容
        prompt_template (str, optional): 提示词模板

    Returns:
        str: 生成的回复内容
    """
    logger.info("开始生成回复内容")

    # 参数验证
    if not content:
        logger.error("生成回复失败: 原始内容为空")
        return ""

    # 限制内容长度，避免过长的提示词
    max_content_length = 1000
    if len(content) > max_content_length:
        logger.warning(f"原始内容超过{max_content_length}字符，将被截断")
        content = content[:max_content_length] + "..."

    # 使用默认或自定义提示词模板
    if not prompt_template:
        logger.debug("使用默认回复提示词模板")
        prompt_template = """
你是一名专业的社交媒体助手，请针对以下内容生成一个简短、友好且专业的回复。
回复应该表达感谢、认同或提供有价值的补充信息，长度控制在100字以内。

原始内容: {content}

请按以下JSON格式返回回复内容:
{{
    "reply": "你的回复内容"
}}
"""
    else:
        logger.debug("使用自定义回复提示词模板")
        # 确保模板中包含{content}占位符
        if "{content}" not in prompt_template:
            logger.warning("提示词模板中缺少{content}占位符，将使用默认模板")
            prompt_template = """
你是一名专业的社交媒体助手，请针对以下内容生成一个简短、友好且专业的回复。
回复应该表达感谢、认同或提供有价值的补充信息，长度控制在100字以内。

原始内容: {content}

请按以下JSON格式返回回复内容:
{{
    "reply": "你的回复内容"
}}
"""

    # 格式化提示词
    try:
        prompt = prompt_template.format(content=content)
    except Exception as e:
        logger.error(f"格式化提示词模板时出错: {str(e)}")
        # 使用简单的提示词作为备选
        prompt = f"请针对以下内容生成一个简短的回复（JSON格式，包含reply字段）: {content}"

    logger.debug(f"原始内容: {content[:100]}..." if len(content) > 100 else content)

    # 调用LLM生成回复
    max_retries = 2
    retry_delay = 1  # 秒

    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"调用LLM生成回复内容 (尝试 {attempt+1}/{max_retries+1})")
            response = get_llm_response(prompt)

            if not response:
                logger.warning("LLM返回空响应")
                if attempt < max_retries:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return ""

            logger.debug(f"LLM返回内容: {response[:100]}..." if len(response) > 100 else response)

            # 尝试解析JSON
            try:
                result = json.loads(response)
                reply = result.get("reply", "")

                if reply:
                    logger.info(f"成功生成回复内容: {reply[:100]}..." if len(reply) > 100 else reply)
                    return reply
                else:
                    logger.warning("LLM返回的JSON中没有reply字段")
                    # 尝试从响应中提取可能的回复内容
                    if len(response) < 280:  # Twitter字符限制
                        logger.info("使用完整响应作为回复内容")
                        return response
            except json.JSONDecodeError:
                logger.warning(f"解析LLM返回的JSON时出错，尝试提取文本")
                # 尝试从非JSON响应中提取可能的回复内容
                if len(response) < 280:  # Twitter字符限制
                    logger.info("使用完整响应作为回复内容")
                    return response

            # 如果到这里还没有返回，说明当前尝试失败
            if attempt < max_retries:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error("生成回复内容失败，已达到最大重试次数")
                return ""

        except Exception as e:
            logger.error(f"生成回复内容时出错: {str(e)}")
            if attempt < max_retries:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return ""

    return ""


def auto_reply(post: Post, enable_auto_reply: bool = False, prompt_template: str = None) -> bool:
    """
    自动回复功能

    Args:
        post (Post): 帖子对象
        enable_auto_reply (bool): 是否启用自动回复
        prompt_template (str, optional): 自定义提示词模板

    Returns:
        bool: 是否成功回复
    """
    # 参数验证
    if not post:
        logger.error("自动回复失败: 帖子对象为空")
        return False

    if not hasattr(post, 'id') or not post.id:
        logger.error("自动回复失败: 帖子ID为空")
        return False

    if not hasattr(post, 'content') or not post.content:
        logger.error(f"自动回复失败: 帖子 {post.id} 内容为空")
        return False

    # 检查是否启用自动回复
    if not enable_auto_reply:
        logger.debug("自动回复功能未启用")
        return False

    logger.info(f"开始处理帖子 {post.id} 的自动回复")

    try:
        # 检查是否已经回复过
        replied = redis_client.get(f"twitter:replied:{post.id}")
        if replied:
            logger.info(f"帖子 {post.id} 已经回复过，跳过")
            return False
    except Exception as e:
        logger.error(f"检查帖子 {post.id} 回复状态时出错: {str(e)}")
        # 继续执行，避免因为Redis错误而影响功能

    try:
        # 生成回复内容
        reply_content = generate_reply(post.content, prompt_template)
        if not reply_content:
            logger.warning(f"未能为帖子 {post.id} 生成有效的回复内容")
            return False

        # 检查回复内容长度
        if len(reply_content) > 280:  # Twitter字符限制
            logger.warning(f"帖子 {post.id} 的回复内容超过280字符，尝试截断")
            reply_content = reply_content[:277] + "..."
    except Exception as e:
        logger.error(f"生成帖子 {post.id} 回复内容时出错: {str(e)}")
        return False

    # 发送回复
    logger.info(f"准备回复帖子 {post.id}")
    success = reply_to_post(post.id, reply_content)

    # 如果成功，记录已回复状态
    if success:
        try:
            logger.info(f"成功回复帖子 {post.id}，记录回复状态")
            redis_client.set(f"twitter:replied:{post.id}", "1")
            # 设置过期时间，避免Redis中存储过多记录（30天过期）
            redis_client.expire(f"twitter:replied:{post.id}", 60 * 60 * 24 * 30)
        except Exception as e:
            logger.error(f"记录帖子 {post.id} 回复状态时出错: {str(e)}")
            # 不影响返回结果
    else:
        logger.warning(f"回复帖子 {post.id} 失败")

    return success


if __name__ == "__main__":
    posts = fetch('myfxtrader')
    for post in posts:
        print(post.content)
