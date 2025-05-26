"""
Twitter工具函数模块
用于消除twitter.py和twitter_twikit.py中的重复代码
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from modules.socialmedia.post import Post
from utils.logger import get_logger

logger = get_logger('twitter_utils')


def extract_media_info(tweet_obj: Any) -> Tuple[List[str], List[str]]:
    """
    从推文对象中提取媒体信息

    Args:
        tweet_obj: 推文对象（可能来自tweety或twikit）

    Returns:
        Tuple[List[str], List[str]]: (媒体URL列表, 媒体类型列表)
    """
    media_urls = []
    media_types = []

    try:
        if hasattr(tweet_obj, 'media') and tweet_obj.media:
            for media in tweet_obj.media:
                media_url = None
                media_type = "image"  # 默认类型

                # 尝试不同的URL属性
                if hasattr(media, 'media_url_https'):
                    media_url = media.media_url_https
                elif hasattr(media, 'url'):
                    media_url = media.url

                # 获取媒体类型
                if hasattr(media, 'type'):
                    media_type = media.type
                elif hasattr(media, 'video_url') and getattr(media, 'video_url', None):
                    media_type = "video"

                if media_url:
                    media_urls.append(media_url)
                    media_types.append(media_type)

    except Exception as e:
        logger.warning(f"提取媒体信息时出错: {str(e)}")

    return media_urls, media_types


def extract_author_info(author_obj: Any, fallback_username: str = "Unknown") -> Dict[str, Optional[str]]:
    """
    从作者对象中提取作者信息

    Args:
        author_obj: 作者对象（可能来自tweety或twikit）
        fallback_username: 备用用户名

    Returns:
        Dict[str, Optional[str]]: 包含name, url, avatar_url的字典
    """
    author_info = {
        'name': fallback_username,
        'url': '',
        'avatar_url': None
    }

    try:
        if author_obj:
            # 获取用户名
            if hasattr(author_obj, 'name'):
                author_info['name'] = author_obj.name
            elif hasattr(author_obj, 'screen_name'):
                author_info['name'] = author_obj.screen_name

            # 获取用户URL
            if hasattr(author_obj, 'profile_url'):
                author_info['url'] = author_obj.profile_url
            elif hasattr(author_obj, 'screen_name'):
                author_info['url'] = f"https://x.com/{author_obj.screen_name}"

            # 获取头像URL
            if hasattr(author_obj, 'profile_image_url_https'):
                author_info['avatar_url'] = author_obj.profile_image_url_https
            elif hasattr(author_obj, 'profile_image_url'):
                author_info['avatar_url'] = author_obj.profile_image_url
            elif hasattr(author_obj, 'avatar_url'):
                author_info['avatar_url'] = author_obj.avatar_url

    except Exception as e:
        logger.warning(f"提取作者信息时出错: {str(e)}")

    return author_info


def create_post_from_tweet(
    tweet_obj: Any,
    author_obj: Any = None,
    fallback_username: str = "Unknown",
    post_url_template: str = "https://x.com/{username}/status/{tweet_id}"
) -> Optional[Post]:
    """
    从推文对象创建Post对象

    Args:
        tweet_obj: 推文对象
        author_obj: 作者对象（可选，如果为None则从tweet_obj中获取）
        fallback_username: 备用用户名
        post_url_template: 推文URL模板

    Returns:
        Optional[Post]: 创建的Post对象，失败时返回None
    """
    try:
        # 获取推文ID
        tweet_id = getattr(tweet_obj, 'id', None)
        if not tweet_id:
            logger.warning("推文缺少ID，跳过")
            return None

        # 获取推文内容
        content = getattr(tweet_obj, 'text', '') or getattr(tweet_obj, 'content', '')

        # 获取创建时间
        created_on = getattr(tweet_obj, 'created_on', None) or getattr(tweet_obj, 'created_at', None)
        if not created_on:
            logger.warning(f"推文 {tweet_id} 缺少创建时间，使用当前时间")
            created_on = datetime.now()

        # 如果没有提供author_obj，尝试从tweet_obj获取
        if author_obj is None:
            author_obj = getattr(tweet_obj, 'author', None) or getattr(tweet_obj, 'user', None)

        # 提取作者信息
        author_info = extract_author_info(author_obj, fallback_username)

        # 构建推文URL
        username = author_info['name']
        if hasattr(author_obj, 'screen_name'):
            username = author_obj.screen_name
        post_url = post_url_template.format(username=username, tweet_id=tweet_id)

        # 提取媒体信息
        media_urls, media_types = extract_media_info(tweet_obj)

        # 创建Post对象
        post = Post(
            id=str(tweet_id),
            post_on=created_on,
            content=content,
            url=post_url,
            poster_name=author_info['name'],
            poster_url=author_info['url'],
            media_urls=media_urls,
            media_types=media_types,
            poster_avatar_url=author_info['avatar_url']
        )

        # 添加统计信息（作为动态属性）
        if hasattr(tweet_obj, 'favorite_count'):
            post.like_count = tweet_obj.favorite_count
        if hasattr(tweet_obj, 'retweet_count'):
            post.retweet_count = tweet_obj.retweet_count
        if hasattr(tweet_obj, 'reply_count'):
            post.reply_count = tweet_obj.reply_count

        return post

    except Exception as e:
        logger.error(f"创建Post对象时出错: {str(e)}")
        return None


def set_timeline_metadata(post: Post, original_author: str = None) -> Post:
    """
    为时间线推文设置元数据

    Args:
        post: Post对象
        original_author: 原始作者名称

    Returns:
        Post: 设置了元数据的Post对象
    """
    if post:
        post.account_id = original_author or post.poster_name
        post.source_type = "timeline"
        post.original_author = original_author or post.poster_name

    return post


def parse_datetime_safe(datetime_obj: Any) -> datetime:
    """
    安全地解析日期时间对象

    Args:
        datetime_obj: 日期时间对象

    Returns:
        datetime: 解析后的datetime对象
    """
    try:
        if isinstance(datetime_obj, datetime):
            return datetime_obj
        elif isinstance(datetime_obj, str):
            # 尝试解析字符串格式的日期
            from dateutil import parser
            return parser.parse(datetime_obj)
        else:
            # 如果无法解析，返回当前时间
            logger.warning(f"无法解析日期时间对象: {datetime_obj}，使用当前时间")
            return datetime.now()
    except Exception as e:
        logger.warning(f"解析日期时间时出错: {str(e)}，使用当前时间")
        return datetime.now()


def batch_create_posts(
    tweets: List[Any],
    author_obj: Any = None,
    fallback_username: str = "Unknown",
    is_timeline: bool = False
) -> List[Post]:
    """
    批量创建Post对象

    Args:
        tweets: 推文对象列表
        author_obj: 作者对象（用于用户推文）
        fallback_username: 备用用户名
        is_timeline: 是否为时间线推文

    Returns:
        List[Post]: 创建的Post对象列表
    """
    posts = []

    for tweet in tweets:
        try:
            # 对于时间线推文，每条推文可能有不同的作者
            current_author = author_obj
            if is_timeline:
                current_author = getattr(tweet, 'author', None) or getattr(tweet, 'user', None)

            post = create_post_from_tweet(tweet, current_author, fallback_username)

            if post:
                # 如果是时间线推文，设置时间线元数据
                if is_timeline:
                    original_author = post.poster_name
                    post = set_timeline_metadata(post, original_author)

                posts.append(post)

        except Exception as e:
            logger.error(f"批量创建Post时处理推文出错: {str(e)}")
            continue

    return posts
