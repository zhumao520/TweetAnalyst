import json
import os
import re
import time
import logging
import asyncio
import concurrent.futures
from datetime import datetime

# 先导入基础模块
from utils.logger import get_logger
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Tuple, List, Union

# 创建日志记录器
logger = get_logger('main')

# --- CLI App Setup ---
# This section must be at the top after imports but before most other code.
from flask import Flask
from models import db as main_db # Use an alias
from services.config_service import get_config as main_get_config # Use an alias

cli_app = None

def _init_cli_app():
    global cli_app
    if cli_app is None:
        cli_app = Flask(__name__)
        
        try:
            # Ensure config is initialized enough to get DATABASE_PATH
            # This might be a chicken-and-egg if init_config itself needs db.
            # For now, assume main_get_config can read env var or a pre-loaded cache.
            db_uri_raw = main_get_config('DATABASE_PATH', 'data/tweetAnalyst.db')
        except Exception:
            logger.warning("Could not use main_get_config for DATABASE_PATH during _init_cli_app, using os.getenv.")
            db_uri_raw = os.getenv('DATABASE_PATH', 'data/tweetAnalyst.db')

        if not db_uri_raw: # Final fallback if config service also returned None/empty
            db_uri_raw = 'data/tweetAnalyst.db'
            logger.warning(f"DATABASE_PATH is empty, defaulting to {db_uri_raw} for CLI app.")


        if not db_uri_raw.startswith('sqlite:///'):
            if not os.path.isabs(db_uri_raw):
                # Default path relative to the project root (assuming app runs from root)
                project_root = os.getcwd() 
                db_uri_raw = os.path.join(project_root, db_uri_raw)
            db_uri = f'sqlite:///{db_uri_raw}'
        else:
            db_uri = db_uri_raw
            
        cli_app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        cli_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        main_db.init_app(cli_app)
        logger.info(f"CLI Flask app initialized for DB operations with URI: {db_uri}")

# --- End CLI App Setup ---


# 在导入其他模块之前应用SSL修复
try:
    from utils.ssl_fix import apply_ssl_fixes
    apply_ssl_fixes()
    logger.info("✅ SSL连接修复已应用")
except Exception as e:
    logger.warning(f"⚠️ SSL修复应用失败: {str(e)}")
    # 继续执行，不阻止程序启动

from modules.socialmedia.twitter import fetch as fetchTwitter, auto_reply
# 导入twikit作为备选方案
try:
    from modules.socialmedia import twitter_twikit
    TWIKIT_AVAILABLE = True
    logger.info("Twikit库可用，支持库切换功能")
except ImportError:
    TWIKIT_AVAILABLE = False
    logger.info("Twikit库不可用，仅使用tweety库")

from modules.langchain.llm import get_llm_response_with_cache, LLMAPIError, LLMRateLimitError, LLMResponseFormatError
from models.llm_schemas import LLMAnalysisResponse # Import Pydantic model
from utils.yaml_utils import load_config_with_env

# 尝试导入队列版本的推送适配器，如果失败则使用原始版本
try:
    from modules.bots.apprise_adapter_queue import send_notification
    logger.info("使用队列版本的推送适配器")
except ImportError:
    from modules.bots.apprise_adapter import send_notification
    logger.info("使用原始版本的推送适配器")

def get_twitter_library_preference():
    """
    获取Twitter库偏好设置

    Returns:
        str: 'tweety', 'twikit', 或 'auto'
    """
    try:
        # 优先从数据库获取配置
        from services.config_service import get_config

        library_preference = get_config('TWITTER_LIBRARY')
        if library_preference and library_preference.strip():
            preference = library_preference.strip().lower()
            if preference in ['tweety', 'twikit', 'auto']:
                logger.info(f"使用数据库中的Twitter库设置: {preference}")
                return preference
    except Exception as e:
        logger.warning(f"从数据库获取Twitter库设置时出错: {str(e)}，回退到环境变量")

    # 回退到环境变量
    env_preference = os.getenv('TWITTER_LIBRARY', 'auto').strip().lower()
    if env_preference in ['tweety', 'twikit', 'auto']:
        logger.info(f"使用环境变量中的Twitter库设置: {env_preference}")
        return env_preference

    # 默认值
    logger.info("使用默认Twitter库设置: auto")
    return 'auto'

# 创建日志记录器
logger = get_logger('main')

async def fetch_twitter_posts_smart(user_id: str, limit: int = None, task_type: str = "account"):
    """
    智能Twitter抓取函数，根据配置选择使用tweety或twikit库

    Args:
        user_id (str): Twitter用户ID
        limit (int): 限制返回的推文数量
        task_type (str): 任务类型 - "account"(账号抓取) 或 "timeline"(时间线抓取)

    Returns:
        list[Post]: 帖子列表
    """
    library_preference = get_twitter_library_preference()

    # 如果是时间线任务，只能使用支持时间线的库
    if task_type == "timeline":
        if library_preference == "tweety":
            logger.info("时间线任务：使用tweety库")
            try:
                from modules.socialmedia.twitter import get_timeline_posts_async
                return await get_timeline_posts_async(limit or 20)
            except Exception as e:
                logger.error(f"tweety时间线抓取失败: {str(e)}")
                if TWIKIT_AVAILABLE:
                    logger.info("尝试使用twikit作为备选方案")
                    return await twitter_twikit.fetch_timeline_tweets(limit or 20)
                return []
        elif library_preference == "twikit":
            if TWIKIT_AVAILABLE:
                logger.info("时间线任务：使用twikit库")
                return await twitter_twikit.fetch_timeline_tweets(limit or 20)
            else:
                logger.warning("twikit库不可用，回退到tweety")
                try:
                    from modules.socialmedia.twitter import get_timeline_posts_async
                    return await get_timeline_posts_async(limit or 20)
                except Exception as e:
                    logger.error(f"tweety时间线抓取失败: {str(e)}")
                    return []
        else:  # auto
            logger.info("时间线任务：自动选择库")
            # 优先尝试tweety
            try:
                from modules.socialmedia.twitter import get_timeline_posts_async
                posts = await get_timeline_posts_async(limit or 20)
                if posts:
                    logger.info("时间线任务：tweety库成功")
                    return posts
            except Exception as e:
                logger.warning(f"tweety时间线抓取失败: {str(e)}")

            # 备选twikit
            if TWIKIT_AVAILABLE:
                logger.info("时间线任务：尝试twikit备选方案")
                return await twitter_twikit.fetch_timeline_tweets(limit or 20)

            return []

    # 账号抓取任务
    else:
        if library_preference == "tweety":
            logger.info(f"账号抓取任务：使用tweety库获取 {user_id}")
            posts = fetchTwitter(user_id, limit)
            if not posts and TWIKIT_AVAILABLE:
                logger.info("tweety失败，尝试twikit备选方案")
                return await twitter_twikit.fetch_tweets(user_id, limit)
            return posts
        elif library_preference == "twikit":
            if TWIKIT_AVAILABLE:
                logger.info(f"账号抓取任务：使用twikit库获取 {user_id}")
                return await twitter_twikit.fetch_tweets(user_id, limit)
            else:
                logger.warning("twikit库不可用，回退到tweety")
                return fetchTwitter(user_id, limit)
        else:  # auto
            logger.info(f"账号抓取任务：自动选择库获取 {user_id}")
            # 优先尝试tweety
            posts = fetchTwitter(user_id, limit)
            if posts:
                logger.info("账号抓取任务：tweety库成功")
                return posts

            # 备选twikit
            if TWIKIT_AVAILABLE:
                logger.info("账号抓取任务：尝试twikit备选方案")
                return await twitter_twikit.fetch_tweets(user_id, limit)

            return posts  # 返回tweety的结果（可能为空）

# 加载环境变量
load_dotenv()

# 初始化配置（使用统一的配置服务）
def init_config():
    """
    初始化配置：从数据库加载最新配置到环境变量
    这确保了即使在Web界面更改了配置，后台程序也能使用最新的设置

    Returns:
        dict: 包含初始化结果的字典
    """
    try:
        # 导入配置服务
        from services.config_service import init_config as service_init_config

        # 使用统一的配置初始化函数
        logger.info("初始化配置")
        result = service_init_config(force=True, validate=True)

        if result['success']:
            logger.info(f"配置初始化成功: {result['message']}")
            if result['missing_configs']:
                logger.warning(f"缺少 {len(result['missing_configs'])} 个关键配置: {', '.join(result['missing_configs'])}")
        else:
            logger.warning(f"配置初始化失败: {result['message']}")

        return result
    except Exception as e:
        logger.error(f"初始化配置时出错: {str(e)}")
        return {
            'success': False,
            'message': f"初始化配置时出错: {str(e)}",
            'missing_configs': [],
            'configs': {}
        }

# 避免在模块级别初始化配置，改为在需要时初始化
# init_config()

# 辅助函数

def get_prompt_for_account(account: Dict[str, Any], content: str, tag: str) -> str:
    """
    获取账号的提示词

    Args:
        account: 账号配置
        content: 内容
        tag: 标签

    Returns:
        str: 提示词
    """
    def safe_format_template(template: str, content: str) -> str:
        """安全地格式化模板，处理可能存在的其他占位符"""
        try:
            return template.format(content=content)
        except KeyError as e:
            # 如果模板包含其他占位符，尝试提供默认值
            error_key = str(e).strip("'\"")
            logger.warning(f"提示词模板包含未知占位符: {error_key}")

            # 检查是否是JSON格式中的换行符导致的问题
            if '\n' in error_key or '"' in error_key:
                logger.error(f"模板格式错误：检测到可能是JSON注释或格式问题导致的占位符错误")
                logger.error(f"问题占位符: {repr(error_key)}")
                logger.error("建议检查模板中的JSON格式，移除注释或修复格式")

                # 尝试清理模板中的问题格式
                cleaned_template = template
                # 移除可能的JSON注释
                import re
                cleaned_template = re.sub(r'//.*$', '', cleaned_template, flags=re.MULTILINE)

                try:
                    return cleaned_template.format(content=content)
                except KeyError:
                    logger.warning("清理模板后仍有格式问题，使用默认值填充")

            # 创建一个包含常见占位符的字典
            format_dict = {
                'content': content,
                'should_push': '',  # 空字符串作为默认值
                'confidence': '',
                'reason': '',
                'summary': '',
                'translation': '',
                'impact_areas': '',
                'tech_areas': '',
                'news_categories': '',
                # 添加可能出现的其他占位符
                error_key: ''  # 为具体的错误占位符提供空值
            }

            try:
                return template.format(**format_dict)
            except KeyError as e2:
                # 如果仍然有问题，记录详细错误并返回基本模板
                logger.error(f"模板格式化完全失败: {e2}")
                logger.error(f"原始模板: {repr(template[:200])}...")
                return f"请分析以下内容并决定是否推送：{content}"

    # 兼容两种字段名：prompt_template（数据库字段）和prompt（YAML配置字段）
    if 'prompt_template' in account and account['prompt_template']:
        return safe_format_template(account['prompt_template'], content)
    elif 'prompt' in account and account['prompt']:
        return safe_format_template(account['prompt'], content)
    else:
        try:
            # 导入默认提示词模板
            from utils.prompts.default_prompts import get_default_prompt
            template = get_default_prompt(tag)
            return safe_format_template(template, content)
        except ImportError:
            # 如果导入失败，使用服务中的默认模板
            try:
                from services.config_service import get_default_prompt_template
                template = get_default_prompt_template(tag)
                return safe_format_template(template, content)
            except Exception as service_error:
                logger.error(f"获取服务提示词模板失败: {service_error}")
                # 使用最基本的默认模板
                return f"请分析以下内容并决定是否推送：{content}"

def process_llm_result(format_result: Dict[str, Any], is_old_format: bool, content: str, tag: str) -> Tuple[bool, int, str, str]:
    """
    处理LLM返回的结果

    Args:
        format_result: LLM返回的解析结果
        is_old_format: 是否是旧格式
        content: 原始内容
        tag: 标签

    Returns:
        Tuple[bool, int, str, str]: (should_push, confidence, reason, summary)
    """
    should_push = llm_response.should_push
    confidence = llm_response.confidence if llm_response.confidence is not None else (100 if should_push else 0)
    reason = llm_response.reason or ("符合预设主题" if should_push else "不符合预设主题")
    summary = llm_response.summary

    # If analytical_briefing exists and summary is basic, merge it.
    # The Pydantic model now includes 'detailed_analysis' as a preferred field for this.
    # If 'analytical_briefing' is still used by the LLM, we can map it here.
    if llm_response.analytical_briefing and (summary == content[:200] + "..." or not summary.strip()):
        summary = llm_response.analytical_briefing
        logger.info("使用 'analytical_briefing' 作为主要摘要内容。")
    elif llm_response.detailed_analysis: # Prefer detailed_analysis if summary is basic
         if summary == content[:200] + "..." or not summary.strip():
            summary = llm_response.detailed_analysis
            logger.info("使用 'detailed_analysis' 作为主要摘要内容。")


    # 确保summary不为空
    if not summary or summary.strip() == '':
        summary = f"AI分析结果: {content[:200]}..." if len(content) > 200 else content
        logger.warning(f"分析结果摘要为空，使用原始内容作为摘要")

    # Append specific area info to summary
    if tag == 'finance' and llm_response.impact_areas:
        summary += f"\n\n**影响领域**: {', '.join(llm_response.impact_areas)}"
    elif tag == 'ai' and llm_response.tech_areas:
        summary += f"\n\n**技术领域**: {', '.join(llm_response.tech_areas)}"
    if llm_response.news_categories: # General news categories
        summary += f"\n\n**新闻分类**: {', '.join(llm_response.news_categories)}"
        
    return should_push, confidence, reason, summary

async def call_llm_with_retry(prompt: str, account_type: str, account_id: str) -> Optional[LLMAnalysisResponse]:
    """
    调用LLM并解析响应 (async), 支持重试和多AI提供商.
    The retry logic is now primarily handled by the @retry_with_exponential_backoff decorator
    on get_llm_response in llm.py. This function will focus on invoking it.
    """
    llm_response_obj: Optional[LLMAnalysisResponse] = None
    provider_info_dict: Dict[str, Any] = {}

    try:
        logger.debug(f"调用LLM进行内容分析 for {account_type}:{account_id}")
        # get_llm_response_with_cache is now async and returns a Pydantic object and provider_info
        llm_response_obj, provider_info_dict = await get_llm_response_with_cache(
            prompt, use_cache=USE_LLM_CACHE
        )

        if llm_response_obj:
            logger.info("成功获取并解析LLM响应")
            # Provider info is now part of the tuple from get_llm_response_with_cache
            # and can be added to the Pydantic object if needed (already done in get_llm_response)
        else: # Should ideally not happen if get_llm_response raises on error
            logger.error("LLM响应为空或解析失败 (unexpected None from get_llm_response_with_cache)")
            
    except LLMResponseFormatError as e:
        logger.error(f"LLM响应格式错误 (Pydantic解析失败) for {account_type}:{account_id}: {str(e)}")
        # This error will be caught by the retry decorator on get_llm_response
        # If it still propagates here, it means all retries failed.
        return None # Or re-raise if preferred
    except LLMAPIError as e: # Catch other specific LLM errors
        logger.error(f"LLM API调用特定错误 for {account_type}:{account_id}: {str(e)}")
        return None
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"处理内容时发生未预期的错误 for {account_type}:{account_id}: {str(e)}", exc_info=True)
        return None # Or re-raise

    return llm_response_obj # Return the Pydantic object

def ensure_env_vars() -> None:
    """
    确保必要的环境变量已设置（使用统一的配置服务）
    """
    try:
        # 使用配置服务确保环境变量已设置
        from services.config_service import ensure_env_vars as service_ensure_env_vars
        service_ensure_env_vars()
    except ImportError:
        # 如果配置服务不可用，使用基本的环境变量设置
        logger.warning("配置服务不可用，使用基本的环境变量设置")

        # 检查HTTP_PROXY是否已设置
        if 'HTTP_PROXY' in os.environ:
            # 同时设置http_proxy和https_proxy（小写版本）
            http_proxy = os.environ['HTTP_PROXY']
            os.environ['http_proxy'] = http_proxy
            os.environ['HTTPS_PROXY'] = http_proxy
            os.environ['https_proxy'] = http_proxy

def send_push_notification(
    post: Any,
    summary: str,
    reason: str,
    tag: str,
    is_ai_decision: bool = True,
    use_queue: bool = True
) -> bool:
    """
    发送推送通知

    Args:
        post: 帖子对象
        summary: 内容摘要
        reason: 推送原因
        tag: 标签
        is_ai_decision: 是否是AI决定推送
        use_queue: 是否使用队列，如果为False则直接发送

    Returns:
        bool: 是否成功发送
    """
    # 确保环境变量已设置
    ensure_env_vars()

    # 获取帖子时间
    post_time = post.get_local_time()

    # 处理可能包含转义换行符的内容
    processed_summary = summary.replace('\\n', '\n')

    # 构建通知消息
    decision_type = "AI推送理由" if is_ai_decision else "直接推送"

    # 获取完整的原始内容
    original_content = post.content if hasattr(post, 'content') else ""

    # 处理可能包含转义换行符的AI分析内容
    processed_summary = summary.replace('\\n', '\n')

    # 基本消息内容 - 包含完整原始内容和AI分析
    if is_ai_decision and processed_summary and processed_summary.strip() != original_content.strip():
        # 如果有AI分析且与原始内容不同，则显示AI分析
        markdown_msg = f"""# [{post.poster_name}]({post.poster_url}) {post_time.strftime('%Y-%m-%d %H:%M:%S')}

{original_content}

**AI分析**: {processed_summary}

**{decision_type}**: {reason}

origin: {post.url}"""
    else:
        # 如果没有AI分析或AI分析与原始内容相同，只显示原始内容
        markdown_msg = f"""# [{post.poster_name}]({post.poster_url}) {post_time.strftime('%Y-%m-%d %H:%M:%S')}

{original_content}

**{decision_type}**: {reason}

origin: {post.url}"""

    # 添加媒体内容（如果有）
    media_urls = []
    if hasattr(post, 'has_media') and callable(getattr(post, 'has_media')) and post.has_media():
        media_info = post.get_media_info()
        if media_info:
            # 添加媒体内容标题
            markdown_msg += "\n\n**媒体内容**:"

            # 最多显示3个媒体内容，避免消息过长
            max_media = 3
            for i, media in enumerate(media_info[:max_media]):
                media_url = media.get('url', '')
                media_type = media.get('type', 'image')

                # 收集媒体URL
                if media_url:
                    media_urls.append(media_url)

                # 根据媒体类型添加不同的标记，直接显示链接地址
                if media_type == 'video':
                    markdown_msg += f"\n- 视频: {media_url}"
                elif media_type == 'gif':
                    markdown_msg += f"\n- GIF: {media_url}"
                else:  # 默认为图片
                    markdown_msg += f"\n- 图片: {media_url}"

            # 如果有更多媒体内容，添加提示
            if len(media_info) > max_media:
                markdown_msg += f"\n- 还有 {len(media_info) - max_media} 个媒体内容未显示"

    # 确保tag是字符串，并且添加'all'标签确保所有推送服务都能收到
    tag_str = 'all'
    if tag is not None and str(tag) != 'all':
        # 使用逗号分隔的标签列表，确保包含'all'标签
        tag_str = f"{str(tag)},all"

    # 记录使用的标签
    logger.info(f"推送通知使用标签: {tag_str}")

    try:
        # 获取帖子ID和账号ID
        post_id = getattr(post, 'id', None)
        account_id = getattr(post, 'account_id', None)

        # 准备元数据
        metadata = {
            'is_ai_decision': is_ai_decision,
            'post_url': getattr(post, 'url', None),
            'post_time': post_time.isoformat() if post_time else None,
            'media_urls': media_urls if media_urls else None
        }

        # 发送通知
        notification_result = send_notification(
            message=markdown_msg,
            title=f"来自 {post.poster_name} 的更新",
            tag=tag_str,
            account_id=account_id,
            post_id=post_id,
            metadata=metadata,
            use_queue=use_queue
        )

        if notification_result:
            logger.info("通知已加入队列或发送成功")
            return True
        else:
            logger.warning("通知加入队列或发送失败")
            return False
    except Exception as e:
        logger.error(f"发送通知时出错: {str(e)}")
        return False

def save_analysis_to_db(
    post: Any,
    account_type: str,
    account_id: str,
    summary: str,
    is_relevant: bool,
    confidence: int,
    reason: str,
    save_to_db: bool = True,
    ai_provider: str = None,
    ai_model: str = None
) -> bool:
    """
    保存分析结果到数据库

    Args:
        post: 帖子对象
        account_type: 账号类型
        account_id: 账号ID
        summary: 内容摘要
        is_relevant: 是否相关
        confidence: 置信度
        reason: 原因
        save_to_db: 是否保存到数据库
        ai_provider: AI提供商ID或名称
        ai_model: AI模型名称

    Returns:
        bool: 是否成功保存
    """
    if not save_to_db:
        return False

    try:
        from web_app import AnalysisResult, db, app
        logger.debug("保存分析结果到数据库")

        post_time = post.get_local_time()
        content = post.content

        # 处理媒体内容
        has_media = False
        media_content = None

        if hasattr(post, 'has_media') and callable(getattr(post, 'has_media')) and post.has_media():
            has_media = True
            if hasattr(post, 'get_media_info') and callable(getattr(post, 'get_media_info')):
                media_info = post.get_media_info()
                if media_info:
                    import json
                    media_content = json.dumps(media_info)
                    logger.debug(f"保存媒体内容，数量: {len(media_info)}")

        # 对于时间线推文，需要特殊处理账号ID
        # 时间线推文的account_id应该保持为"timeline"，但要保存原始作者信息
        final_account_id = account_id
        original_poster_name = None
        if hasattr(post, 'source_type') and post.source_type == "timeline":
            # 时间线推文：account_id保持为"timeline"，原始作者信息保存在poster_name中
            final_account_id = "timeline"
            if hasattr(post, 'account_id'):
                original_poster_name = post.account_id  # 保存原始作者用户名

        # 确保在应用上下文中执行数据库操作
        with app.app_context():
            # 检查是否已存在相同的记录（使用处理后的账号ID）
            existing_result = AnalysisResult.query.filter_by(
                social_network=account_type,
                account_id=final_account_id,
                post_id=post.id
            ).first()

            if existing_result:
                logger.info(f"已存在相同的分析结果记录，跳过保存: {existing_result.id}")

                # 如果需要更新现有记录的某些字段，可以在这里添加代码
                # 例如，如果新的置信度更高，可以更新现有记录
                if hasattr(existing_result, 'confidence') and confidence > existing_result.confidence:
                    logger.info(f"更新现有记录的置信度: {existing_result.confidence} -> {confidence}")
                    existing_result.confidence = confidence
                    existing_result.is_relevant = is_relevant
                    existing_result.analysis = summary
                    existing_result.reason = reason

                    # 更新AI提供商信息（如果有）
                    if hasattr(existing_result, 'ai_provider') and ai_provider:
                        existing_result.ai_provider = str(ai_provider)
                    if hasattr(existing_result, 'ai_model') and ai_model:
                        existing_result.ai_model = ai_model

                    db.session.commit()
                    logger.debug("已更新现有分析结果记录")

                return True

            # 获取头像URL（如果有）
            poster_avatar_url = getattr(post, 'poster_avatar_url', None)

            # 获取发布者真实用户名（如果有）
            poster_name = getattr(post, 'poster_name', None)
            if not poster_name:
                # 如果没有poster_name，尝试从其他字段获取
                poster_name = getattr(post, 'original_author', None) or original_poster_name or account_id

            # 创建基本的分析结果对象
            db_result = AnalysisResult(
                social_network=account_type,
                account_id=final_account_id,  # 使用处理后的账号ID
                post_id=post.id,
                post_time=post_time,
                content=content,
                analysis=summary,
                is_relevant=is_relevant,
                confidence=confidence,
                reason=reason,
                poster_avatar_url=poster_avatar_url,
                poster_name=poster_name
            )

            # 添加媒体内容（如果有）
            if hasattr(db_result, 'has_media'):
                db_result.has_media = has_media
            if hasattr(db_result, 'media_content') and media_content:
                db_result.media_content = media_content

            # 添加AI提供商信息（如果有）
            if hasattr(db_result, 'ai_provider') and ai_provider:
                db_result.ai_provider = str(ai_provider)
            if hasattr(db_result, 'ai_model') and ai_model:
                db_result.ai_model = ai_model

            db.session.add(db_result)
            db.session.commit()
            logger.debug("分析结果已保存到数据库")
            return True
    except Exception as e:
        logger.error(f"保存分析结果到数据库时出错: {str(e)}")
        try:
            # 确保db和app都在当前上下文中可用
            if 'db' in locals() and 'app' in locals() and hasattr(db, 'session'):
                # 使用安全的方式回滚事务
                try:
                    with app.app_context():
                        db.session.rollback()
                except RuntimeError:
                    # 如果应用上下文不可用，记录错误但不中断程序
                    logger.error("无法在应用上下文外回滚事务，跳过回滚操作")
            else:
                logger.warning("数据库会话不可用，跳过回滚操作")
        except Exception as rollback_error:
            logger.error(f"回滚事务时出错: {str(rollback_error)}")
        return False

# 从环境变量获取配置
try:
    # LLM处理最大重试次数
    LLM_PROCESS_MAX_RETRIED = int(os.getenv("LLM_PROCESS_MAX_RETRIED", "3"))
    logger.debug(f"设置LLM处理最大重试次数为: {LLM_PROCESS_MAX_RETRIED}")

    # 是否使用缓存
    USE_LLM_CACHE = os.getenv("USE_LLM_CACHE", "true").lower() == "true"
    logger.debug(f"LLM缓存状态: {'启用' if USE_LLM_CACHE else '禁用'}")

    # 并行处理的最大线程数
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
    logger.debug(f"最大并行处理线程数: {MAX_WORKERS}")

    # 批处理大小
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
    logger.debug(f"批处理大小: {BATCH_SIZE}")

except (ValueError, TypeError) as e:
    logger.warning(f"加载配置时出错: {str(e)}，使用默认值")
    LLM_PROCESS_MAX_RETRIED = 3
    USE_LLM_CACHE = True
    MAX_WORKERS = 4
    BATCH_SIZE = 10

# JSON处理辅助函数
def parse_llm_response(response_text: str) -> Dict[str, Any]:
    """
    解析LLM响应，提取JSON对象或关键字段

    Args:
        response_text (str): LLM响应文本

    Returns:
        Dict[str, Any]: 解析结果，包含should_push, confidence, reason, summary等字段
    """
    if not response_text:
        logger.warning("LLM响应为空")
        return None

    # 记录原始响应，用于调试
    logger.debug(f"解析LLM响应: {response_text[:100]}...")

    # 尝试直接解析JSON
    try:
        # 尝试提取JSON对象
        json_match = re.search(r'({.*})', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)

            # 移除可能的markdown代码块标记
            json_str = re.sub(r'^```(json)?|```$', '', json_str, flags=re.MULTILINE)

            # 尝试解析JSON
            try:
                result = json.loads(json_str)
                logger.info("成功解析JSON对象")
                return result
            except json.JSONDecodeError:
                # 如果解析失败，尝试修复常见问题
                logger.debug("直接解析JSON失败，尝试修复")

                # 修复常见问题
                # 1. 修复缺少双引号的键
                json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)

                # 2. 修复布尔值和null值的格式
                json_str = re.sub(r':\s*True\b', r':true', json_str, flags=re.IGNORECASE)
                json_str = re.sub(r':\s*False\b', r':false', json_str, flags=re.IGNORECASE)
                json_str = re.sub(r':\s*None\b', r':null', json_str, flags=re.IGNORECASE)

                # 3. 修复单引号替换为双引号
                json_str = json_str.replace("'", '"')

                # 4. 修复尾随逗号
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)

                # 尝试解析修复后的JSON
                try:
                    result = json.loads(json_str)
                    logger.info("成功解析修复后的JSON对象")
                    return result
                except json.JSONDecodeError:
                    logger.warning("修复后仍无法解析JSON，尝试提取关键字段")
    except Exception as e:
        logger.warning(f"提取JSON对象时出错: {e}")

    # 如果无法解析JSON，尝试提取关键字段
    try:
        # 提取should_push字段
        should_push = False
        should_push_match = re.search(r'"?should_?push"?[\s:]+\s*(true|false|yes|no|1|0)', response_text, re.IGNORECASE)
        if should_push_match:
            value = should_push_match.group(1).lower()
            should_push = value in ('true', 'yes', '1')
        else:
            # 从文本中推断
            lower_text = response_text.lower()
            positive_keywords = ['relevant', 'important', 'significant', 'noteworthy', 'push', 'notify', 'yes', 'true', '1']
            negative_keywords = ['irrelevant', 'unimportant', 'trivial', 'ignore', 'skip', "don't push", 'no', 'false', '0']

            # 计算关键词出现次数
            positive_count = sum(1 for keyword in positive_keywords if keyword in lower_text)
            negative_count = sum(1 for keyword in negative_keywords if keyword in lower_text)

            should_push = positive_count > negative_count

        # 提取confidence字段
        confidence = 50 if should_push else 30
        confidence_match = re.search(r'"?confidence"?[\s:]+\s*([0-9]+)', response_text, re.IGNORECASE)
        if confidence_match:
            confidence = int(confidence_match.group(1))

        # 提取reason字段
        reason = "符合预设主题" if should_push else "不符合预设主题"
        reason_match = re.search(r'"?reason"?[\s:]+\s*["\']?([^"\']*)["\']?', response_text, re.IGNORECASE)
        if reason_match:
            reason = reason_match.group(1).strip()
        else:
            # 尝试匹配理由相关段落
            reason_paragraphs = re.findall(r'(?:理由|原因|推送理由|reason)[:：]?\s*([^\n.。]+)[.。]?', response_text, re.IGNORECASE)
            if reason_paragraphs:
                reason = reason_paragraphs[0].strip()

        # 提取summary字段
        summary = ""
        summary_match = re.search(r'"?summary"?[\s:]+\s*["\']?([^"\']*)["\']?', response_text, re.IGNORECASE)
        if summary_match:
            summary = summary_match.group(1).strip()
        else:
            # 尝试匹配analytical_briefing字段（旧格式）
            analytical_match = re.search(r'"?analytical_briefing"?[\s:]+\s*["\']?([^"\']*)["\']?', response_text, re.IGNORECASE)
            if analytical_match:
                summary = analytical_match.group(1).strip()
            else:
                # 尝试匹配摘要相关段落
                summary_paragraphs = re.findall(r'(?:摘要|总结|分析|summary|analysis)[:：]?\s*([^\n]+)', response_text, re.IGNORECASE)
                if summary_paragraphs:
                    summary = summary_paragraphs[0].strip()
                else:
                    # 使用文本的前200个字符作为摘要
                    summary = response_text[:200] + "..." if len(response_text) > 200 else response_text

        # 构建结果对象
        result = {
            "should_push": should_push,
            "confidence": confidence,
            "reason": reason,
            "summary": summary
        }

        # 尝试提取impact_areas或tech_areas字段
        areas_match = re.search(r'"?(impact_?areas|tech_?areas)"?[\s:]+\s*\[(.*?)\]', response_text, re.DOTALL | re.IGNORECASE)
        if areas_match:
            area_type = areas_match.group(1).lower().replace('areas', '_areas')
            if area_type == 'impact_areas' or area_type == 'tech_areas':
                areas_text = areas_match.group(2)
                areas = re.findall(r'["\']?([^"\',]+)["\']?', areas_text)
                if areas:
                    result[area_type] = areas

        logger.info(f"成功提取关键字段: should_push={should_push}, confidence={confidence}")
        return result
    except Exception as e:
        logger.error(f"提取关键字段时出错: {e}")

        # 创建默认结果
        return {
            "should_push": False,
            "confidence": 0,
            "reason": "解析LLM响应失败",
            "summary": "无法从LLM响应中提取有效信息"
        }


def process_post(post: Any, account: Dict[str, Any], enable_auto_reply: bool = False, auto_reply_prompt: str = "", save_to_db: bool = False) -> Dict[str, Any]:
    """
    处理单个帖子 (async)

    Args:
        post: 帖子对象
        account: 账号配置
        enable_auto_reply: 是否启用自动回复
        auto_reply_prompt: 自动回复提示词
        save_to_db: 是否保存到数据库

    Returns:
        dict: 处理结果
    """
    # Ensure cli_app is initialized before potential DB operations in process_post
    _init_cli_app()

    account_id = account['socialNetworkId']
    account_type = account['type']
    content = post.content
    tag = account.get('tag', 'all')

    # 检查是否绕过AI判断直接推送
    bypass_ai = account.get('bypass_ai', False)

    # 记录基本信息
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"处理来自 {account_id} 的帖子: {post.id}")
        logger.debug(f"帖子内容: {content[:100]}..." if len(content) > 100 else content)

    if bypass_ai:
        logger.info(f"账号 {account_id} 设置为绕过AI判断，将直接推送新内容")

    # 初始化结果对象
    result = {
        "success": False,
        "should_push": False,
        "post": post,
        "account": account
    }

    try:
        # 获取帖子时间
        post_time = post.get_local_time()

        # 如果设置了绕过AI判断，直接推送内容
        if bypass_ai:
            # 设置默认值
            should_push = True
            is_relevant = True
            confidence = 100
            reason = "账号设置为绕过AI判断直接推送"
            summary = content[:200] + "..." if len(content) > 200 else content

            # 更新结果
            result["success"] = True
            result["should_push"] = should_push
            result["is_relevant"] = is_relevant
            result["post_time"] = post_time
            result["confidence"] = confidence
            result["reason"] = reason
            result["summary"] = summary

            # 发送推送通知
            send_push_notification(
                post=post,
                summary=summary,
                reason=reason,
                tag=tag,
                is_ai_decision=False  # 这是直接推送，不是AI决定
            )

            # 保存到数据库
            save_analysis_to_db(
                post=post,
                account_type=account_type,
                account_id=account_id,
                summary=summary,
                is_relevant=True,
                confidence=confidence,
                reason=reason,
                save_to_db=save_to_db,
                ai_provider="direct_push",  # 直接推送，不是AI决定
                ai_model="none"
            )

            return result

        # 如果不绕过AI判断，使用正常流程
        # 获取提示词
        prompt = get_prompt_for_account(account, content, tag)
        # is_old_format = 'is_relevant' in prompt # No longer needed due to Pydantic model

        # 调用LLM并解析响应 (async)
        llm_analysis_response: Optional[LLMAnalysisResponse] = await call_llm_with_retry(prompt, account_type, account_id)

        # 如果LLM调用失败
        if llm_analysis_response is None:
            logger.error(
                f"在 {account_type}:{account_id} 上处理内容时，LLM调用或解析失败，已达到最大重试次数或发生不可恢复错误")
            save_analysis_to_db(
                post=post, account_type=account_type, account_id=account_id,
                summary="LLM分析失败，无法获取分析结果", is_relevant=False, confidence=0,
                reason="LLM API调用或解析失败", save_to_db=save_to_db,
                ai_provider="error", ai_model="error"
            )
            return result # result['success'] is False

        # 处理LLM结果 using Pydantic object
        should_push, confidence, reason, summary = process_llm_result(llm_analysis_response, False, content, tag) # is_old_format is False

        is_relevant = should_push # Compatibility

        result["success"] = True
        result["should_push"] = should_push
        result["is_relevant"] = is_relevant
        result["format_result"] = llm_analysis_response.model_dump() # Store as dict
        result["post_time"] = post_time
        result["confidence"] = confidence
        result["reason"] = reason
        result["summary"] = summary

        ai_provider_used = llm_analysis_response.ai_provider_id
        ai_model_used = llm_analysis_response.ai_model

        if not should_push:
            logger.info(
                f"在 {account_type}:{account_id} 上发现更新内容，但AI决定不推送 (置信度: {confidence}%)")
            # ... (logging as before)
            save_analysis_to_db(
                post=post, account_type=account_type, account_id=account_id,
                summary=summary, is_relevant=False, confidence=confidence, reason=reason,
                save_to_db=save_to_db, ai_provider=ai_provider_used, ai_model=ai_model_used
            )
            return result

        logger.info(f"在 {account_type}:{account_id} 上发现内容，AI决定推送 (置信度: {confidence}%)")
        # ... (logging as before)

        send_push_notification(post=post, summary=summary, reason=reason, tag=tag, is_ai_decision=True)
        
        account_auto_reply = account.get('enable_auto_reply', account.get('enableAutoReply', False))
        if enable_auto_reply and account_auto_reply:
            try:
                logger.info(f"尝试自动回复帖子 {post.id}")
                # Assuming auto_reply can be awaited if it becomes async
                # For now, if auto_reply is sync, it will block here.
                # This might need to be run in a separate thread if it's long-running.
                reply_result = await auto_reply(post, enable_auto_reply, auto_reply_prompt) if inspect.iscoroutinefunction(auto_reply) else auto_reply(post, enable_auto_reply, auto_reply_prompt)
                if reply_result: logger.info("自动回复成功")
                else: logger.info("自动回复未执行或失败")
            except Exception as e:
                logger.error(f"自动回复时出错: {str(e)}")

        save_analysis_to_db(
            post=post, account_type=account_type, account_id=account_id,
            summary=summary, is_relevant=True, confidence=confidence, reason=reason,
            save_to_db=save_to_db, ai_provider=ai_provider_used, ai_model=ai_model_used
        )
        return result
    except Exception as e:
        logger.error(f"处理帖子时发生错误: {str(e)}", exc_info=True)
        return result # result['success'] will be False

async def process_posts_for_account(posts: List[Any], account: Dict[str, Any], enable_auto_reply: bool = False, auto_reply_prompt: str = "", save_to_db: bool = False) -> Tuple[int, int]:
    """
    处理已抓取的推文列表（用于定时任务）

    Args:
        posts: 已抓取的推文列表
        account: 账号配置（数据库模型对象）
        enable_auto_reply: 是否启用自动回复
        auto_reply_prompt: 自动回复提示词
        save_to_db: 是否保存到数据库

    Returns:
        tuple: (总帖子数, 相关帖子数)
    """
    # 将数据库模型对象转换为字典格式
    account_dict = {
        'socialNetworkId': account.account_id,
        'type': account.type,
        'tag': account.tag,
        'enableAutoReply': account.enable_auto_reply,
        'prompt': account.prompt_template or '',
        'bypass_ai': getattr(account, 'bypass_ai', False)
    }

    account_id = account_dict['socialNetworkId']
    account_type = account_dict['type']
    logger.info(f"开始处理 {account_type} 账号: {account_id} 的 {len(posts)} 条推文")

    # 添加处理间隔配置，默认1秒
    process_interval = float(os.getenv("PROCESS_INTERVAL", "1.0"))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"设置处理间隔为 {process_interval} 秒")

    # 初始化计数器
    total = len(posts)
    relevant = 0
    processed_count = 0
    error_count = 0

    try:
        # 如果没有推文，直接返回
        if not posts:
            logger.info(f"在 {account_type}: {account_id} 上未发现有更新的内容")
            return (0, 0)

        # 创建处理队列
        post_queue = list(posts)  # 创建一个列表副本，这样我们可以安全地修改它

        # 逐条处理帖子 (async)
        for i, post_item in enumerate(post_queue): # Use enumerate for logging progress
            try:
                logger.info(f"处理第 {i + 1}/{total} 条帖子，ID: {post_item.id}")
                result = await process_post(post_item, account_dict, enable_auto_reply, auto_reply_prompt, save_to_db)
                
                processed_count += 1
                if result["success"] and result.get("is_relevant", False):
                    relevant += 1
            except Exception as e:
                logger.error(f"处理帖子 {post_item.id} 时出错: {str(e)}", exc_info=True)
                error_count += 1

            if i < total - 1 and process_interval > 0 : # Check if it's not the last post
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"等待 {process_interval} 秒后处理下一条帖子")
                await asyncio.sleep(process_interval) # Use asyncio.sleep

        logger.info(f"账号 {account_id} 处理完成，成功: {processed_count}，失败: {error_count}，相关: {relevant}")
        return (total, relevant)
    except Exception as e:
        logger.error(f"处理账号 {account_id} 的帖子时发生错误: {str(e)}", exc_info=True)
        return (0, 0)

async def process_account_posts(account: Dict[str, Any], enable_auto_reply: bool = False, auto_reply_prompt: str = "", save_to_db: bool = False) -> Tuple[int, int]:
    """
    处理账号的所有帖子

    Args:
        account: 账号配置
        enable_auto_reply: 是否启用自动回复
        auto_reply_prompt: 自动回复提示词
        save_to_db: 是否保存到数据库

    Returns:
        tuple: (总帖子数, 相关帖子数)
    """
    account_id = account['socialNetworkId']
    account_type = account['type']
    logger.info(f"开始处理 {account_type} 账号: {account_id}")

    # 添加处理间隔配置，默认1秒
    process_interval = float(os.getenv("PROCESS_INTERVAL", "1.0"))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"设置处理间隔为 {process_interval} 秒")

    # 初始化计数器
    total = 0
    relevant = 0
    processed_count = 0
    error_count = 0

    try:
        # 获取帖子 - 使用智能抓取
        posts = []
        if account_type == 'twitter':
            posts = asyncio.run(fetch_twitter_posts_smart(account_id, None, "account"))
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"从 Twitter 账号 {account_id} 智能抓取到 {len(posts)} 条新帖子")

        # 如果没有新帖子，直接返回
        if not posts:
            logger.info(f"在 {account_type}: {account_id} 上未发现有更新的内容")
            return (0, 0)

        total = len(posts)

        # 创建处理队列
        post_queue = list(posts)  # 创建一个列表副本，这样我们可以安全地修改它

        # 逐条处理帖子 (async)
        for i, post_item in enumerate(post_queue): # Use enumerate for logging progress
            try:
                logger.info(f"处理第 {i + 1}/{total} 条帖子，ID: {post_item.id}")
                # process_post is now async
                result = await process_post(post_item, account, enable_auto_reply, auto_reply_prompt, save_to_db)

                processed_count += 1
                if result["success"] and result.get("is_relevant", False):
                    relevant += 1
            except Exception as e:
                logger.error(f"处理帖子 {post_item.id} 时出错: {str(e)}", exc_info=True)
                error_count += 1
            
            if i < total - 1 and process_interval > 0: # Check if it's not the last post
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"等待 {process_interval} 秒后处理下一条帖子")
                await asyncio.sleep(process_interval) # Use asyncio.sleep

        logger.info(f"账号 {account_id} 处理完成，成功: {processed_count}，失败: {error_count}，相关: {relevant}")
        return (total, relevant)
    except Exception as e:
        logger.error(f"处理账号 {account_id} 的帖子时发生错误: {str(e)}", exc_info=True)
        return (0, 0)

async def process_timeline_posts(enable_auto_reply: bool = False, auto_reply_prompt: str = "", save_to_db: bool = False) -> Tuple[int, int]:
    """
    处理时间线（关注账号）的最新推文

    Args:
        enable_auto_reply: 是否启用自动回复
        auto_reply_prompt: 自动回复提示词
        save_to_db: 是否保存到数据库

    Returns:
        tuple: (总帖子数, 相关帖子数)
    """
    logger.info("开始处理时间线（关注账号）的最新推文")

    # 添加处理间隔配置，默认1秒
    process_interval = float(os.getenv("PROCESS_INTERVAL", "1.0"))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"设置处理间隔为 {process_interval} 秒")

    # 初始化计数器
    total = 0
    relevant = 0
    processed_count = 0
    error_count = 0

    # 确保环境变量已设置
    ensure_env_vars()

    try:
        # 获取时间线推文 - 使用智能抓取
        logger.info("正在使用智能抓取获取时间线推文...")

        # 导入新的智能抓取接口
        from modules.socialmedia.smart_fetch import fetch_twitter_posts_smart
        from modules.socialmedia.async_utils import safe_asyncio_run
        from utils.yaml_utils import load_config_with_env
        from services.config_service import get_config

        # 获取时间线抓取数量配置
        timeline_limit = int(get_config('TIMELINE_FETCH_LIMIT', '50'))
        logger.info(f"时间线抓取限制: {timeline_limit} 条")

        posts = safe_asyncio_run(fetch_twitter_posts_smart(None, timeline_limit, "timeline"))
        logger.info(f"智能抓取返回结果：{len(posts) if posts else 0} 条推文")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"从时间线获取到 {len(posts)} 条推文")

        # 如果没有新推文，直接返回
        if not posts:
            logger.warning("⚠️ 时间线上未发现有更新的内容")
            logger.warning("可能的原因：")
            logger.warning("1. Twitter账号未关注任何人")
            logger.warning("2. 关注的账号最近没有发推文")
            logger.warning("3. Twitter客户端认证失败")
            logger.warning("4. 网络连接或代理问题")
            logger.warning("5. Twitter API限制或账号被限制")
            return (0, 0)

        total = len(posts)

        # 读取 social-networks.yml 配置，查找 timeline 账号
        config = load_config_with_env('config/social-networks.yml')
        timeline_account = None
        if config and 'social_networks' in config:
            for acc in config['social_networks']:
                if acc.get('socialNetworkId') == 'timeline' and acc.get('type') == 'twitter':
                    timeline_account = acc
                    break
        if not timeline_account:
            # 没有配置则用默认
            timeline_account = {
                'type': 'twitter',
                'socialNetworkId': 'timeline',
                'tag': 'general',
                'enableAutoReply': False,
                'prompt': ''
            }

        # 创建处理队列
        post_queue = list(posts)  # 创建一个列表副本，这样我们可以安全地修改它

        # 逐条处理推文 (async)
        for i, post_item in enumerate(post_queue): # Use enumerate for logging progress
            try:
                author_info = f"作者: {post_item.poster_name}" if hasattr(post_item, 'poster_name') else ""
                logger.info(f"处理第 {i + 1}/{total} 条时间线推文，ID: {post_item.id} {author_info}")
                # process_post is now async
                result = await process_post(post_item, timeline_account, enable_auto_reply, auto_reply_prompt, save_to_db)

                processed_count += 1
                if result["success"] and result.get("is_relevant", False):
                    relevant += 1
            except Exception as e:
                logger.error(f"处理时间线推文 {post_item.id} 时出错: {str(e)}", exc_info=True)
                error_count += 1

            if i < total - 1 and process_interval > 0: # Check if it's not the last post
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"等待 {process_interval} 秒后处理下一条推文")
                await asyncio.sleep(process_interval) # Use asyncio.sleep

        logger.info(f"时间线处理完成，成功: {processed_count}，失败: {error_count}，相关: {relevant}")
        return (total, relevant)
    except Exception as e:
        logger.error(f"处理时间线推文时发生错误: {str(e)}", exc_info=True)
        return (0, 0)


async def main() -> None: # Changed to async def
    """
    主函数，执行社交媒体监控任务
    """
    start_time = time.time()
    logger.info("开始执行社交媒体监控任务")

    try:
        # 确保配置已初始化
        init_config()

        # 确保环境变量已设置
        ensure_env_vars()

        # 加载配置
        config = load_config_with_env('config/social-networks.yml')
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"成功加载配置文件，包含 {len(config.get('social_networks', []))} 个社交媒体账号")

        # 处理socialNetworkId为数组的情况
        new_social_networks = process_social_network_ids(config.get('social_networks', []))

        # 用新的配置替换原配置
        config['social_networks'] = new_social_networks
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"处理后的社交媒体账号数量: {len(new_social_networks)}")

        # 获取自动回复设置
        enable_auto_reply = os.getenv("ENABLE_AUTO_REPLY", "false").lower() == "true"
        auto_reply_prompt = os.getenv("AUTO_REPLY_PROMPT", "")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"自动回复功能状态: {'启用' if enable_auto_reply else '禁用'}")

        # 检查数据库连接
        save_to_db = check_database_connection()

        # 处理所有账号
        total_posts, relevant_posts = process_all_accounts(
            config['social_networks'],
            enable_auto_reply,
            auto_reply_prompt,
            save_to_db
        )

        # 计算执行时间
        execution_time = time.time() - start_time
        logger.info(f"社交媒体监控任务完成，处理了 {total_posts} 条帖子，其中 {relevant_posts} 条相关内容，耗时 {execution_time:.2f} 秒")

    except Exception as e:
        logger.error(f"执行社交媒体监控任务时出错: {str(e)}", exc_info=True)


def process_social_network_ids(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    处理socialNetworkId为数组的情况

    Args:
        accounts: 账号配置列表

    Returns:
        List[Dict[str, Any]]: 处理后的账号配置列表
    """
    new_social_networks = []

    for account in accounts:
        if isinstance(account.get('socialNetworkId'), list):
            # 如果socialNetworkId是数组,为每个ID创建一个新的配置
            for social_id in account['socialNetworkId']:
                if not social_id:  # 跳过空ID
                    continue

                new_account = account.copy()
                new_account['socialNetworkId'] = social_id
                new_social_networks.append(new_account)
        else:
            # 如果不是数组直接添加原配置
            new_social_networks.append(account)

    return new_social_networks


def check_database_connection() -> bool:
    """
    检查数据库连接

    Returns:
        bool: 是否可以保存到数据库
    """
    if 'cli_app' not in globals() or cli_app is None:
        logger.error("cli_app not initialized. Cannot check database connection.")
        _init_cli_app() # Attempt to initialize if not already
        if 'cli_app' not in globals() or cli_app is None: # Check again
             logger.error("cli_app still not initialized after attempt. DB check failed.")
             return False


    try:
        with cli_app.app_context():
            # A simple query to check connectivity
            # For SQLAlchemy, connecting and closing is a good test.
            # For a more thorough check, you might execute a simple query like "SELECT 1".
            connection = main_db.engine.connect()
            connection.close()
            logger.info("数据库连接成功 (via cli_app)")
            return True
    except Exception as e:
        logger.error(f"数据库连接失败 (via cli_app): {str(e)}")
        logger.warning("由于数据库连接错误，不会保存分析结果")
        return False


def process_all_accounts(
    accounts: List[Dict[str, Any]],
    enable_auto_reply: bool,
    auto_reply_prompt: str,
    save_to_db: bool
) -> Tuple[int, int]:
    """
    处理所有账号

    Args:
        accounts: 账号配置列表
        enable_auto_reply: 是否启用自动回复
        auto_reply_prompt: 自动回复提示词
        save_to_db: 是否保存到数据库

    Returns:
        Tuple[int, int]: (总帖子数, 相关帖子数)
    """
    total_posts = 0
    relevant_posts = 0

    # 添加账号处理间隔配置，默认5秒
    account_interval = float(os.getenv("ACCOUNT_INTERVAL", "5.0"))

    # 使用线程池并行处理账号 (adjusting for async process_account_posts)
    use_threads = main_get_config("USE_THREADS", "false").lower() == "true" # Use main_get_config
    max_workers = int(main_get_config("MAX_WORKERS", "4")) # Use main_get_config

    if use_threads:
        logger.info(f"使用线程池并行处理异步账号任务，最大线程数: {max_workers}")
        
        # Helper to run async function in a thread
        def run_async_in_thread(acc):
            return asyncio.run(process_account_posts(acc, enable_auto_reply, auto_reply_prompt, save_to_db))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_account = {
                executor.submit(run_async_in_thread, account): account for account in accounts
            }
            for future in concurrent.futures.as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    posts, relevant = future.result()
                    total_posts += posts
                    relevant_posts += relevant
                except Exception as e:
                    logger.error(f"处理账号 {account.get('socialNetworkId', 'unknown')} 的异步任务时发生错误: {str(e)}", exc_info=True)
    else:
        # 顺序处理账号 (async)
        for i, account in enumerate(accounts):
            try:
                logger.info(f"顺序处理第 {i+1}/{len(accounts)} 个账号 (async)")
                posts, relevant = await process_account_posts(account, enable_auto_reply, auto_reply_prompt, save_to_db)
                total_posts += posts
                relevant_posts += relevant

                if i < len(accounts) - 1 and account_interval > 0:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"等待 {account_interval} 秒后处理下一个账号")
                    await asyncio.sleep(account_interval) # Use asyncio.sleep
            except Exception as e:
                logger.error(f"处理账号 {account.get('socialNetworkId', 'unknown')} 时发生错误: {str(e)}", exc_info=True)
    return total_posts, relevant_posts


if __name__ == "__main__":
    # Ensure the CLI app is initialized before running main logic
    _init_cli_app() # Initialize Flask app for DB context
    asyncio.run(main()) # Run the async main function
