import os
import json
import time
from tweety import Twitter
from utils.redisClient import redis_client
from modules.socialmedia.post import Post
from modules.langchain.llm import get_llm_response
from utils.logger import get_logger
from dotenv import load_dotenv

# 创建日志记录器
logger = get_logger('twitter')

load_dotenv()

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
            cursor = str(cursor, encoding='utf-8')
            logger.debug(f"找到用户 {user_id} 的上次处理记录，上次处理的最后一条推文ID: {cursor}")

    try:
        logger.debug(f"调用Twitter API获取用户 {user_id} 的推文")
        posts = app.get_tweets(user_id, cursor=cursor, pages=1 if limit is not None else None)
        logger.info(f"成功获取用户 {user_id} 的推文，数量: {len(posts) if posts else 0}")
    except Exception as e:
        logger.error(f"获取用户 {user_id} 的推文时出错: {str(e)}")
        return []

    noneEmptyPosts = []

    for post in posts:
        try:
            if 'tweets' in post:
                # 处理推文线程
                logger.debug(f"处理推文线程，ID: {post.id if hasattr(post, 'id') else 'unknown'}")
                latest_id = None
                latest_created_on = None
                combined_text = ""
                latest_url = ""
                poster = None

                for tweet in post.tweets:
                    if tweet.text:
                        combined_text += tweet.text + "\n"
                    if latest_created_on is None or tweet.created_on > latest_created_on:
                        latest_created_on = tweet.created_on
                        latest_id = tweet.id
                        latest_url = tweet.url
                        poster = tweet.author

                if combined_text and latest_id and latest_created_on and poster:
                    logger.debug(f"添加推文线程到结果列表，ID: {latest_id}")
                    noneEmptyPosts.append(
                        Post(latest_id, latest_created_on, combined_text.strip(), latest_url, poster.name, poster.profile_url))
            elif post.text:
                # 处理单条推文
                logger.debug(f"处理单条推文，ID: {post.id}")
                noneEmptyPosts.append(Post(post.id, post.created_on, post.text,
                                      post.url, post.author.name, post.author.profile_url))
        except Exception as e:
            logger.error(f"处理推文时出错: {str(e)}")
            continue

    # 更新最后处理的推文ID
    if posts and hasattr(posts, 'cursor_top') and posts.cursor_top:
        logger.debug(f"更新用户 {user_id} 的最后处理记录，最后一条推文ID: {posts.cursor_top}")
        redis_client.set(f"twitter:{user_id}:last_post_id", posts.cursor_top)

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
    # 确保Twitter客户端已初始化
    if not ensure_initialized():
        logger.warning("Twitter客户端未初始化，尝试重新初始化")
        if not reinit_twitter_client():
            logger.error("Twitter客户端初始化失败，无法回复帖子")
            return False

    logger.info(f"准备回复帖子 {post_id}")
    logger.debug(f"回复内容: {content}")

    try:
        app.reply(post_id, content)
        logger.info(f"成功回复帖子 {post_id}")
        return True
    except Exception as e:
        logger.error(f"回复Twitter帖子 {post_id} 时出错: {str(e)}")
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

    prompt = prompt_template.format(content=content)
    logger.debug(f"原始内容: {content[:100]}..." if len(content) > 100 else content)

    try:
        logger.debug("调用LLM生成回复内容")
        response = get_llm_response(prompt)
        logger.debug(f"LLM返回内容: {response[:100]}..." if len(response) > 100 else response)

        result = json.loads(response)
        reply = result.get("reply", "")

        if reply:
            logger.info(f"成功生成回复内容: {reply[:100]}..." if len(reply) > 100 else reply)
        else:
            logger.warning("LLM返回的JSON中没有reply字段")

        return reply
    except json.JSONDecodeError as e:
        logger.error(f"解析LLM返回的JSON时出错: {str(e)}")
        logger.debug(f"无效的JSON: {response}")
        return ""
    except Exception as e:
        logger.error(f"生成回复内容时出错: {str(e)}")
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
    if not enable_auto_reply:
        logger.debug("自动回复功能未启用")
        return False

    logger.info(f"开始处理帖子 {post.id} 的自动回复")

    # 检查是否已经回复过
    replied = redis_client.get(f"twitter:replied:{post.id}")
    if replied:
        logger.info(f"帖子 {post.id} 已经回复过，跳过")
        return False

    # 生成回复内容
    reply_content = generate_reply(post.content, prompt_template)
    if not reply_content:
        logger.warning(f"未能为帖子 {post.id} 生成有效的回复内容")
        return False

    # 发送回复
    logger.info(f"准备回复帖子 {post.id}")
    success = reply_to_post(post.id, reply_content)

    # 如果成功，记录已回复状态
    if success:
        logger.info(f"成功回复帖子 {post.id}，记录回复状态")
        redis_client.set(f"twitter:replied:{post.id}", "1")
        # 设置过期时间，避免Redis中存储过多记录（30天过期）
        redis_client.expire(f"twitter:replied:{post.id}", 60 * 60 * 24 * 30)
    else:
        logger.warning(f"回复帖子 {post.id} 失败")

    return success


if __name__ == "__main__":
    posts = fetch('myfxtrader')
    for post in posts:
        print(post.content)
