import os
import json
import time
import importlib.util
import traceback
import asyncio
from datetime import datetime, timezone
from tweety import Twitter, TwitterAsync
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
def init_twitter_client(use_async=False):
    """
    初始化Twitter客户端

    支持三种登录方式：
    1. 使用会话文件（优先）
    2. 使用账号密码
    3. 使用API密钥（如果配置了）

    同时支持代理设置

    Args:
        use_async (bool): 是否使用异步客户端

    Returns:
        Twitter或TwitterAsync: Twitter客户端实例
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
        logger.info(f"使用会话文件登录Twitter{'Async' if use_async else ''}")
        try:
            # 确保session文件目录存在
            session_file = 'session.tw_session'
            session_dir = os.path.dirname(os.path.abspath(session_file))
            if not os.path.exists(session_dir):
                os.makedirs(session_dir)

            with open(session_file, 'w') as f:
                f.write(twitter_session)

            if use_async:
                app = TwitterAsync('session')
                # 异步连接需要特殊处理
                try:
                    asyncio.run(app.connect())
                    # 异步获取me属性
                    me = asyncio.run(app.me())
                    if me is not None:
                        logger.info(f"成功使用会话文件登录TwitterAsync，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                        return app
                    else:
                        logger.warning("会话文件登录TwitterAsync失败，尝试使用账号密码登录")
                except Exception as e:
                    logger.error(f"使用会话文件登录TwitterAsync时出错: {str(e)}")
            else:
                app = Twitter('session')
                app.connect()

                if app.me is not None:
                    logger.info(f"成功使用会话文件登录Twitter，用户: {app.me.username}")
                    return app
                else:
                    logger.warning("会话文件登录失败，尝试使用账号密码登录")
        except Exception as e:
            logger.error(f"使用会话文件登录Twitter{'Async' if use_async else ''}时出错: {str(e)}")

    # 尝试使用账号密码
    username = os.getenv('TWITTER_USERNAME')
    password = os.getenv('TWITTER_PASSWORD')

    if username and password:
        logger.info(f"使用账号密码登录Twitter{'Async' if use_async else ''}: {username}")
        try:
            if use_async:
                app = TwitterAsync('session')
                try:
                    asyncio.run(app.connect())
                    # 检查是否已登录
                    me = asyncio.run(app.me())
                    if me is None:
                        asyncio.run(app.sign_in(username, password))
                        me = asyncio.run(app.me())
                        if me is not None:
                            logger.info(f"成功使用账号密码登录TwitterAsync，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                            return app
                        else:
                            logger.error("账号密码登录TwitterAsync失败")
                    else:
                        logger.info(f"已登录TwitterAsync，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                        return app
                except Exception as e:
                    logger.error(f"使用账号密码登录TwitterAsync时出错: {str(e)}")
            else:
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
            logger.error(f"使用账号密码登录Twitter{'Async' if use_async else ''}时出错: {str(e)}")

    # 尝试使用API密钥（如果配置了）
    api_key = os.getenv('TWITTER_API_KEY')
    api_secret = os.getenv('TWITTER_API_SECRET')
    access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    access_secret = os.getenv('TWITTER_ACCESS_SECRET')

    if api_key and api_secret and access_token and access_secret:
        logger.info(f"使用API密钥登录Twitter{'Async' if use_async else ''}")
        try:
            # 注意：tweety库目前不直接支持API密钥登录
            # 这里是一个占位，如果将来支持或者切换到其他库，可以实现这部分
            logger.warning("当前版本不支持API密钥登录，请使用会话文件或账号密码登录")
        except Exception as e:
            logger.error(f"使用API密钥登录Twitter{'Async' if use_async else ''}时出错: {str(e)}")

    logger.error(f"所有Twitter{'Async' if use_async else ''}登录方式均失败")
    return None

# 初始化Twitter客户端变量
app = None
async_app = None

# 延迟初始化，确保在使用时已加载配置
def ensure_initialized(use_async=False):
    """
    确保Twitter客户端已初始化

    Args:
        use_async (bool): 是否使用异步客户端

    Returns:
        bool: 是否成功初始化
    """
    global app, async_app

    if use_async:
        if async_app is None:
            try:
                logger.info("首次使用时初始化异步Twitter客户端")
                async_app = init_twitter_client(use_async=True)
                return async_app is not None
            except Exception as e:
                logger.error(f"初始化异步Twitter客户端时出错: {str(e)}")
                return False
        return True
    else:
        if app is None:
            try:
                logger.info("首次使用时初始化Twitter客户端")
                app = init_twitter_client(use_async=False)
                return app is not None
            except Exception as e:
                logger.error(f"初始化Twitter客户端时出错: {str(e)}")
                return False
        return True

# 添加重新初始化函数，用于在需要时重新连接
def reinit_twitter_client(use_async=False):
    """
    重新初始化Twitter客户端

    Args:
        use_async (bool): 是否使用异步客户端

    Returns:
        bool: 是否成功初始化
    """
    global app, async_app

    try:
        if use_async:
            logger.info("尝试重新初始化异步Twitter客户端")
            async_app = init_twitter_client(use_async=True)
            return async_app is not None
        else:
            logger.info("尝试重新初始化Twitter客户端")
            app = init_twitter_client(use_async=False)
            return app is not None
    except Exception as e:
        logger.error(f"重新初始化Twitter{'Async' if use_async else ''}客户端时出错: {str(e)}")
        return False


def check_account_status(user_id: str, use_async: bool = False) -> dict:
    """
    检查Twitter账号状态

    Args:
        user_id (str): Twitter用户ID
        use_async (bool, optional): 是否使用异步API

    Returns:
        dict: 账号状态信息，包含以下字段：
            - exists (bool): 账号是否存在
            - protected (bool): 账号是否受保护
            - suspended (bool): 账号是否被暂停
            - error (str): 错误信息，如果有的话
    """
    global app, async_app

    # 初始化返回结果
    status = {
        "exists": False,
        "protected": False,
        "suspended": False,
        "error": None
    }

    # 检查缓存
    cache_key = f"twitter:{user_id}:account_status"
    try:
        cached_status = redis_client.get(cache_key)
        if cached_status:
            try:
                # 如果是字节类型，转换为字符串
                if isinstance(cached_status, bytes):
                    cached_status = str(cached_status, encoding='utf-8')

                # 解析JSON
                cached_status = json.loads(cached_status)

                # 检查缓存是否过期（24小时）
                if 'timestamp' in cached_status:
                    cache_time = cached_status.get('timestamp', 0)
                    current_time = int(time.time())

                    # 如果缓存不超过24小时，直接返回
                    if current_time - cache_time < 86400:  # 24小时 = 86400秒
                        logger.debug(f"使用缓存的账号状态信息: {user_id}")
                        result = cached_status.copy()
                        if 'timestamp' in result:
                            del result['timestamp']  # 删除时间戳字段
                        return result
            except Exception as e:
                logger.warning(f"解析缓存的账号状态信息时出错: {str(e)}")
    except Exception as e:
        logger.warning(f"获取缓存的账号状态信息时出错: {str(e)}")

    # 确保Twitter客户端已初始化
    if use_async:
        if not ensure_initialized(use_async=True):
            if not reinit_twitter_client(use_async=True):
                logger.error("异步Twitter客户端初始化失败，无法检查账号状态")
                status["error"] = "Twitter客户端初始化失败"
                return status
    else:
        if not ensure_initialized():
            if not reinit_twitter_client():
                logger.error("Twitter客户端初始化失败，无法检查账号状态")
                status["error"] = "Twitter客户端初始化失败"
                return status

    logger.debug(f"检查用户 {user_id} 的账号状态 {'(异步)' if use_async else ''}")

    try:
        # 尝试获取用户信息
        if use_async:
            try:
                user_info = asyncio.run(async_app.get_user_info(user_id))
            except Exception as e:
                error_msg = str(e).lower()
                if "user not found" in error_msg or "account wasn't found" in error_msg:
                    status["error"] = "账号不存在"
                    logger.warning(f"用户 {user_id} 不存在")
                elif "protected" in error_msg:
                    status["exists"] = True
                    status["protected"] = True
                    status["error"] = "账号受保护"
                    logger.warning(f"用户 {user_id} 的账号受保护")
                elif "suspended" in error_msg:
                    status["exists"] = True
                    status["suspended"] = True
                    status["error"] = "账号已被暂停"
                    logger.warning(f"用户 {user_id} 的账号已被暂停")
                else:
                    status["error"] = f"获取用户信息失败: {error_msg}"
                    logger.error(f"获取用户 {user_id} 信息时出错: {error_msg}")

                # 缓存结果
                try:
                    status_with_timestamp = status.copy()
                    status_with_timestamp['timestamp'] = int(time.time())
                    redis_client.set(cache_key, json.dumps(status_with_timestamp), ex=86400)  # 设置24小时过期
                except Exception as cache_error:
                    logger.warning(f"缓存账号状态信息时出错: {str(cache_error)}")

                return status
        else:
            try:
                user_info = app.get_user_info(user_id)
            except Exception as e:
                error_msg = str(e).lower()
                if "user not found" in error_msg or "account wasn't found" in error_msg:
                    status["error"] = "账号不存在"
                    logger.warning(f"用户 {user_id} 不存在")
                elif "protected" in error_msg:
                    status["exists"] = True
                    status["protected"] = True
                    status["error"] = "账号受保护"
                    logger.warning(f"用户 {user_id} 的账号受保护")
                elif "suspended" in error_msg:
                    status["exists"] = True
                    status["suspended"] = True
                    status["error"] = "账号已被暂停"
                    logger.warning(f"用户 {user_id} 的账号已被暂停")
                else:
                    status["error"] = f"获取用户信息失败: {error_msg}"
                    logger.error(f"获取用户 {user_id} 信息时出错: {error_msg}")

                # 缓存结果
                try:
                    status_with_timestamp = status.copy()
                    status_with_timestamp['timestamp'] = int(time.time())
                    redis_client.set(cache_key, json.dumps(status_with_timestamp), ex=86400)  # 设置24小时过期
                except Exception as cache_error:
                    logger.warning(f"缓存账号状态信息时出错: {str(cache_error)}")

                return status

        # 如果成功获取用户信息，说明账号存在且可访问
        if user_info:
            status["exists"] = True

            # 检查账号是否受保护
            if hasattr(user_info, 'protected') and user_info.protected:
                status["protected"] = True
                status["error"] = "账号受保护"
                logger.warning(f"用户 {user_id} 的账号受保护")
            else:
                logger.info(f"用户 {user_id} 的账号正常")

        # 缓存结果
        try:
            status_with_timestamp = status.copy()
            status_with_timestamp['timestamp'] = int(time.time())
            redis_client.set(cache_key, json.dumps(status_with_timestamp), ex=86400)  # 设置24小时过期
        except Exception as cache_error:
            logger.warning(f"缓存账号状态信息时出错: {str(cache_error)}")

        return status
    except Exception as e:
        logger.error(f"检查用户 {user_id} 的账号状态时出错: {str(e)}")
        status["error"] = f"检查账号状态时出错: {str(e)}"
        return status

def fetch(user_id: str, limit: int = None, use_async: bool = False) -> list[Post]:
    """
    获取指定用户的最新推文

    Args:
        user_id (str): Twitter用户ID
        limit (int, optional): 限制返回的推文数量，用于测试
        use_async (bool, optional): 是否使用异步API

    Returns:
        list[Post]: 帖子列表
    """
    global app, async_app

    # 首先检查账号状态
    account_status = check_account_status(user_id, use_async)

    # 如果账号不存在或受保护，直接返回空列表
    if not account_status["exists"] or account_status["protected"] or account_status["suspended"]:
        logger.warning(f"无法获取用户 {user_id} 的推文: {account_status['error']}")
        return []

    # 确保Twitter客户端已初始化
    if use_async:
        if not ensure_initialized(use_async=True):
            logger.warning("异步Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client(use_async=True):
                logger.error("异步Twitter客户端初始化失败，无法获取推文")
                # 尝试使用同步客户端作为备选
                logger.info("尝试使用同步客户端作为备选")
                return fetch(user_id, limit, use_async=False)
    else:
        if not ensure_initialized():
            logger.warning("Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client():
                logger.error("Twitter客户端初始化失败，无法获取推文")
                return []

    logger.info(f"开始获取用户 {user_id} 的最新推文 {'(异步)' if use_async else ''}")

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

    # 尝试获取推文
    posts = None

    if use_async:
        # 使用异步API获取推文
        try:
            logger.debug(f"调用异步Twitter API获取用户 {user_id} 的推文")

            # 尝试使用不同的参数组合调用get_tweets
            error_messages = []

            # 尝试方法1: 使用cursor和limit参数
            try:
                posts = asyncio.run(async_app.get_tweets(user_id, cursor=cursor, limit=limit))
                logger.debug("异步方法1成功")
            except Exception as e:
                error_messages.append(f"异步方法1失败: {str(e)}")

            # 尝试方法2: 只使用limit参数
            if posts is None and limit is not None:
                try:
                    posts = asyncio.run(async_app.get_tweets(user_id, limit=limit))
                    logger.debug("异步方法2成功")
                except Exception as e:
                    error_messages.append(f"异步方法2失败: {str(e)}")

            # 尝试方法3: 只使用用户ID
            if posts is None:
                try:
                    posts = asyncio.run(async_app.get_tweets(user_id))
                    logger.debug("异步方法3成功")
                except Exception as e:
                    error_messages.append(f"异步方法3失败: {str(e)}")

            # 如果所有异步方法都失败，尝试使用同步方法
            if posts is None:
                logger.warning(f"异步获取用户 {user_id} 的推文失败: {'; '.join(error_messages)}")
                logger.info("尝试使用同步方法作为备选")
                return fetch(user_id, limit, use_async=False)

            logger.info(f"成功使用异步API获取用户 {user_id} 的推文，数量: {len(posts) if posts else 0}")
        except Exception as e:
            logger.error(f"异步获取用户 {user_id} 的推文时出错: {str(e)}")
            logger.info("尝试使用同步方法作为备选")
            return fetch(user_id, limit, use_async=False)
    else:
        # 使用同步API获取推文
        try:
            logger.debug(f"调用同步Twitter API获取用户 {user_id} 的推文")

            # 尝试使用不同的参数组合调用get_tweets
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

    # 处理获取到的推文
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


def reply_to_post(post_id: str, content: str, use_async: bool = False) -> bool:
    """
    回复Twitter帖子

    Args:
        post_id (str): 要回复的帖子ID
        content (str): 回复内容
        use_async (bool, optional): 是否使用异步API

    Returns:
        bool: 是否成功回复
    """
    global app, async_app

    # 参数验证
    if not post_id:
        logger.error("回复帖子失败: 帖子ID为空")
        return False

    if not content or not content.strip():
        logger.error(f"回复帖子 {post_id} 失败: 回复内容为空")
        return False

    # 确保Twitter客户端已初始化
    if use_async:
        if not ensure_initialized(use_async=True):
            logger.warning("异步Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client(use_async=True):
                logger.error("异步Twitter客户端初始化失败，无法回复帖子")
                # 尝试使用同步客户端作为备选
                logger.info("尝试使用同步客户端作为备选")
                return reply_to_post(post_id, content, use_async=False)
    else:
        if not ensure_initialized():
            logger.warning("Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client():
                logger.error("Twitter客户端初始化失败，无法回复帖子")
                return False

    logger.info(f"准备回复帖子 {post_id} {'(异步)' if use_async else ''}")
    logger.debug(f"回复内容: {content}")

    # 尝试回复
    max_retries = 3
    retry_delay = 2  # 秒

    if use_async:
        # 使用异步API回复
        # 检查异步Twitter客户端是否有reply方法
        if not hasattr(async_app, 'reply'):
            logger.error("异步Twitter客户端不支持reply方法，可能是tweety库版本不兼容")
            logger.info("尝试使用同步客户端作为备选")
            return reply_to_post(post_id, content, use_async=False)

        for attempt in range(max_retries):
            try:
                asyncio.run(async_app.reply(post_id, content))
                logger.info(f"成功使用异步API回复帖子 {post_id}")
                return True
            except Exception as e:
                logger.error(f"异步回复Twitter帖子 {post_id} 时出错 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    import time
                    time.sleep(retry_delay)
                    # 增加重试延迟时间
                    retry_delay *= 2
                else:
                    logger.error(f"异步回复Twitter帖子 {post_id} 失败，已达到最大重试次数")
                    logger.info("尝试使用同步客户端作为备选")
                    return reply_to_post(post_id, content, use_async=False)
    else:
        # 使用同步API回复
        # 检查Twitter客户端是否有reply方法
        if not hasattr(app, 'reply'):
            logger.error("Twitter客户端不支持reply方法，可能是tweety库版本不兼容")
            return False

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


def fetch_timeline(limit: int = None) -> list[Post]:
    """
    获取用户时间线（关注账号的最新推文）

    Args:
        limit (int, optional): 限制返回的推文数量，用于测试

    Returns:
        list[Post]: 帖子列表
    """
    global app
    # 确保Twitter客户端已初始化
    if not ensure_initialized():
        logger.warning("Twitter客户端未初始化，尝试重新初始化")
        if not reinit_twitter_client():
            logger.error("Twitter客户端初始化失败，无法获取时间线")
            return []

    logger.info("开始获取用户时间线（关注账号的最新推文）")

    # 尝试使用异步API获取时间线
    try:
        # 创建异步客户端
        async_app = None
        try:
            # 使用与同步客户端相同的会话
            session_file = 'session.tw_session'
            if os.path.exists(session_file):
                logger.info("使用会话文件创建异步Twitter客户端")
                async_app = TwitterAsync("session")
                # 连接异步客户端
                asyncio.run(async_app.connect())
                logger.info("异步Twitter客户端连接成功")
            else:
                logger.warning("会话文件不存在，无法创建异步Twitter客户端")
        except Exception as e:
            logger.error(f"创建异步Twitter客户端时出错: {str(e)}")

        # 如果成功创建异步客户端，尝试获取时间线
        if async_app:
            timeline = None
            try:
                # 尝试获取主时间线
                logger.info("尝试使用异步API获取主时间线")
                timeline = asyncio.run(async_app.get_home_timeline(limit=limit if limit is not None else 20))
                logger.info(f"成功使用异步API获取主时间线，推文数量: {len(timeline) if timeline else 0}")
            except Exception as e:
                logger.error(f"使用异步API获取主时间线时出错: {str(e)}")

            # 如果成功获取时间线，处理推文
            if timeline:
                processed_posts = []

                # 处理每条推文
                for tweet in timeline:
                    try:
                        # 检查推文是否有效
                        if not tweet:
                            continue

                        # 获取推文属性
                        post_id = getattr(tweet, 'id', None)
                        if not post_id:
                            continue

                        created_on = getattr(tweet, 'created_on', datetime.now())
                        text = getattr(tweet, 'text', '')
                        post_url = getattr(tweet, 'url', '')

                        # 获取作者信息
                        author = getattr(tweet, 'author', None)
                        if author:
                            author_name = getattr(author, 'name', 'Unknown')
                            author_url = getattr(author, 'profile_url', '')
                        else:
                            author_name = "Unknown"
                            author_url = ""

                        # 创建Post对象
                        processed_posts.append(
                            Post(post_id, created_on, text, post_url, author_name, author_url))
                    except Exception as e:
                        logger.error(f"处理异步时间线推文时出错: {str(e)}")
                        continue

                logger.info(f"异步时间线处理完成，有效推文数量: {len(processed_posts)}")
                return processed_posts
    except Exception as e:
        logger.error(f"使用异步API获取时间线时出错: {str(e)}")

    # 如果异步方法失败，尝试使用同步方法
    logger.info("异步方法失败，尝试使用同步方法获取时间线")

    try:
        # 尝试使用同步API获取时间线
        timeline = None
        error_messages = []

        # 尝试方法1: 使用get_home_timeline
        try:
            if hasattr(app, 'get_home_timeline'):
                timeline = app.get_home_timeline(pages=1 if limit is not None else None)
                logger.info("成功使用get_home_timeline获取时间线")
            else:
                error_messages.append("app对象没有get_home_timeline方法")
        except Exception as e:
            error_messages.append(f"get_home_timeline方法失败: {str(e)}")

        # 尝试方法2: 使用get_timeline
        if timeline is None:
            try:
                if hasattr(app, 'get_timeline'):
                    timeline = app.get_timeline(pages=1 if limit is not None else None)
                    logger.info("成功使用get_timeline获取时间线")
                else:
                    error_messages.append("app对象没有get_timeline方法")
            except Exception as e:
                error_messages.append(f"get_timeline方法失败: {str(e)}")

        # 如果所有方法都失败，尝试使用替代方法
        if timeline is None:
            logger.warning(f"获取时间线失败: {'; '.join(error_messages)}")
            logger.info("尝试使用替代方法：获取关注账号的推文")

            # 获取当前账号信息
            try:
                me = app.me()
                logger.info(f"当前登录账号: {me.username if hasattr(me, 'username') else 'unknown'}")
            except Exception as e:
                logger.error(f"获取当前账号信息失败: {str(e)}")
                return []

            # 获取关注账号列表
            following = []
            try:
                # 尝试获取关注账号列表
                if hasattr(app, 'get_following'):
                    following = app.get_following(me.username)
                    logger.info(f"获取到 {len(following) if following else 0} 个关注账号")
                elif hasattr(app, 'get_friends'):
                    following = app.get_friends(me.username)
                    logger.info(f"获取到 {len(following) if following else 0} 个关注账号")
                else:
                    logger.error("Twitter客户端不支持获取关注账号列表功能")
                    return []
            except Exception as e:
                logger.error(f"获取关注账号列表失败: {str(e)}")
                return []

            if not following:
                logger.warning("未获取到关注账号列表或关注账号列表为空")
                return []

            # 获取每个关注账号的最新推文
            all_posts = []
            max_accounts = min(5, len(following))  # 限制处理的账号数量，避免请求过多

            logger.info(f"开始获取 {max_accounts} 个关注账号的最新推文")

            for i, account in enumerate(following[:max_accounts]):
                try:
                    account_id = account.username if hasattr(account, 'username') else str(account)
                    logger.debug(f"获取账号 {account_id} 的最新推文 ({i+1}/{max_accounts})")

                    # 检查账号状态，避免尝试获取不存在或受保护的账号
                    account_status = check_account_status(account_id)
                    if account_status["exists"] and not account_status["protected"] and not account_status["suspended"]:
                        # 获取账号的最新推文
                        posts = fetch(account_id, limit=5)  # 每个账号只获取最新的5条推文
                    else:
                        logger.warning(f"跳过账号 {account_id}: {account_status['error']}")
                        posts = []

                    if posts:
                        all_posts.extend(posts)
                        logger.debug(f"从账号 {account_id} 获取到 {len(posts)} 条推文")
                except Exception as e:
                    logger.error(f"获取账号 {account_id if 'account_id' in locals() else 'unknown'} 的推文时出错: {str(e)}")
                    continue

            # 按时间排序
            all_posts.sort(key=lambda x: x.created_on, reverse=True)

            # 如果是测试模式，限制返回数量
            if limit is not None and len(all_posts) > limit:
                all_posts = all_posts[:limit]

            logger.info(f"成功获取用户时间线（替代方法），共 {len(all_posts)} 条推文")
            return all_posts

        # 如果成功获取时间线，处理推文
        logger.info(f"成功获取用户时间线，推文数量: {len(timeline) if timeline else 0}")

        # 处理获取到的推文
        processed_posts = []

        # 确保timeline是可迭代的
        if timeline is None:
            logger.warning("获取到的时间线为None，返回空列表")
            return []

        # 如果是测试模式，限制返回数量
        if limit is not None:
            try:
                timeline = list(timeline)[:limit]
                logger.debug(f"测试模式：限制返回 {limit} 条推文")
            except Exception as e:
                logger.error(f"限制推文数量时出错: {str(e)}")

        # 处理每条推文
        for tweet in timeline:
            try:
                # 检查推文是否有效
                if not tweet:
                    logger.warning("跳过无效推文")
                    continue

                # 处理推文线程
                if hasattr(tweet, 'tweets') and tweet.tweets:
                    logger.debug(f"处理推文线程，ID: {tweet.id if hasattr(tweet, 'id') else 'unknown'}")
                    latest_id = None
                    latest_created_on = None
                    combined_text = ""
                    latest_url = ""
                    poster = None

                    for t in tweet.tweets:
                        if hasattr(t, 'text') and t.text:
                            combined_text += t.text + "\n"
                        if hasattr(t, 'created_on') and (latest_created_on is None or t.created_on > latest_created_on):
                            latest_created_on = t.created_on
                            latest_id = getattr(t, 'id', None)
                            latest_url = getattr(t, 'url', '')
                            poster = getattr(t, 'author', None)

                    if combined_text and latest_id and latest_created_on and poster:
                        try:
                            poster_name = getattr(poster, 'name', 'Unknown')
                            poster_url = getattr(poster, 'profile_url', '')

                            processed_posts.append(
                                Post(latest_id, latest_created_on, combined_text.strip(), latest_url, poster_name, poster_url))
                        except Exception as e:
                            logger.error(f"创建推文线程Post对象时出错: {str(e)}")
                            continue

                # 处理单条推文
                elif hasattr(tweet, 'text') and tweet.text:
                    try:
                        post_id = getattr(tweet, 'id', None)
                        if not post_id:
                            logger.warning("推文缺少ID，跳过")
                            continue

                        logger.debug(f"处理单条推文，ID: {post_id}")

                        created_on = getattr(tweet, 'created_on', None)
                        if not created_on:
                            logger.warning(f"推文 {post_id} 缺少创建时间，使用当前时间")
                            from datetime import datetime
                            created_on = datetime.now()

                        post_url = getattr(tweet, 'url', '')

                        author = getattr(tweet, 'author', None)
                        if author:
                            author_name = getattr(author, 'name', 'Unknown')
                            author_url = getattr(author, 'profile_url', '')
                        else:
                            author_name = "Unknown"
                            author_url = ""

                        processed_posts.append(
                            Post(post_id, created_on, tweet.text, post_url, author_name, author_url))
                    except Exception as e:
                        logger.error(f"创建单条推文Post对象时出错: {str(e)}")
                        continue
            except Exception as e:
                logger.error(f"处理时间线推文时出错: {str(e)}")
                continue

        logger.info(f"用户时间线处理完成，有效推文数量: {len(processed_posts)}")
        return processed_posts
    except Exception as e:
        logger.error(f"获取用户时间线时出错: {str(e)}")
        return []


if __name__ == "__main__":
    posts = fetch('myfxtrader')
    for post in posts:
        print(post.content)
