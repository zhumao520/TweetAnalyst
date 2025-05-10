import json
import os
import time
import concurrent.futures
from datetime import datetime
from modules.socialmedia.twitter import fetch as fetchTwitter, auto_reply
from modules.langchain.llm import get_llm_response_with_cache, LLMAPIError, LLMRateLimitError
from modules.bots.apprise_adapter import send_notification
from utils.yaml import load_config_with_env
from utils.logger import get_logger
from dotenv import load_dotenv

# 创建日志记录器
logger = get_logger('main')

load_dotenv()

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


def process_post(post, account, enable_auto_reply=False, auto_reply_prompt="", save_to_db=False):
    """
    处理单个帖子

    Args:
        post: 帖子对象
        account: 账号配置
        enable_auto_reply: 是否启用自动回复
        auto_reply_prompt: 自动回复提示词
        save_to_db: 是否保存到数据库

    Returns:
        dict: 处理结果
    """
    account_id = account['socialNetworkId']
    account_type = account['type']
    content = post.content
    tag = account.get('tag', 'all')

    logger.debug(f"处理来自 {account_id} 的帖子: {post.id}")
    logger.debug(f"帖子内容: {content[:100]}..." if len(content) > 100 else content)

    result = {
        "success": False,
        "should_push": False,
        "post": post,
        "account": account
    }

    try:
        # 使用账号配置的提示词，如果没有则使用默认提示词
        # 兼容两种字段名：prompt_template（数据库字段）和prompt（YAML配置字段）
        if 'prompt_template' in account and account['prompt_template']:
            prompt = account['prompt_template'].format(content=content)
            # 检查是否是旧格式的提示词（使用is_relevant）
            is_old_format = 'is_relevant' in prompt
        elif 'prompt' in account and account['prompt']:
            prompt = account['prompt'].format(content=content)
            # 检查是否是旧格式的提示词（使用is_relevant）
            is_old_format = 'is_relevant' in prompt
        else:
            # 导入默认提示词模板
            from templates.default_prompts import get_default_prompt
            prompt = get_default_prompt(tag).format(content=content)
            is_old_format = False

        format_result = None
        rawData = ''

        # 在某些情况下，LLM会返回一些非法的json字符串，所以这里需要循环尝试，直到解析成功为止
        retry_count = 0
        while format_result is None and retry_count < LLM_PROCESS_MAX_RETRIED:
            try:
                if len(rawData) > 0:
                    logger.warning(f"LLM返回的JSON格式无效，尝试重试 ({retry_count+1}/{LLM_PROCESS_MAX_RETRIED})")
                    prompt += f"""
你前次基于上面的内容提供给我的json是{rawData}，然而这个json内容有语法错误，无法在python中被解析。针对这个问题重新检查我的要求，按指定要求和格式回答。
"""
                logger.debug("调用LLM进行内容分析")

                # 使用带缓存的LLM响应获取
                rawData = get_llm_response_with_cache(prompt, use_cache=USE_LLM_CACHE).replace('\n', '\\n')

                try:
                    format_result = json.loads(rawData)
                    logger.debug("成功解析LLM返回的JSON")
                except json.JSONDecodeError as e:
                    logger.error(f"解析JSON时出错: {e}")
                    logger.debug(f"LLM返回内容: {rawData}")
                    format_result = None
                    retry_count += 1
            except LLMRateLimitError as e:
                # 限流错误，等待一段时间后重试
                wait_time = (retry_count + 1) * 5  # 递增等待时间
                logger.warning(f"LLM API限流，等待 {wait_time} 秒后重试: {str(e)}")
                time.sleep(wait_time)
                retry_count += 1
            except LLMAPIError as e:
                # 其他API错误
                logger.error(f"LLM API调用错误: {str(e)}")
                retry_count += 1
            except Exception as e:
                # 未预期的错误
                logger.error(f"处理内容时发生未预期的错误: {str(e)}", exc_info=True)
                retry_count += 1

        if format_result is None:
            logger.error(
                f"在 {account_type}: {account_id} 上处理内容时，LLM返回的JSON格式始终无法解析，已达到最大重试次数 {LLM_PROCESS_MAX_RETRIED}")
            return result

        post_time = post.get_local_time()

        # 处理新旧两种格式
        if is_old_format:
            # 旧格式使用is_relevant字段
            should_push = format_result['is_relevant'] == '1'
            analysis_content = format_result.get('analytical_briefing', '')
            confidence = 100 if should_push else 0
            reason = "符合预设主题" if should_push else "不符合预设主题"
            summary = analysis_content
        else:
            # 新格式使用should_push字段
            should_push = format_result.get('should_push', False)
            confidence = format_result.get('confidence', 50)
            reason = format_result.get('reason', '')
            summary = format_result.get('summary', '')

            # 处理特定领域的额外信息
            if tag == 'finance' and 'impact_areas' in format_result:
                impact_areas = format_result.get('impact_areas', [])
                if impact_areas:
                    summary += f"\n\n**影响领域**: {', '.join(impact_areas)}"
            elif tag == 'ai' and 'tech_areas' in format_result:
                tech_areas = format_result.get('tech_areas', [])
                if tech_areas:
                    summary += f"\n\n**技术领域**: {', '.join(tech_areas)}"

        # 兼容旧代码，保留is_relevant字段
        is_relevant = should_push

        result["success"] = True
        result["should_push"] = should_push
        result["is_relevant"] = is_relevant  # 兼容旧代码
        result["format_result"] = format_result
        result["post_time"] = post_time
        result["confidence"] = confidence
        result["reason"] = reason
        result["summary"] = summary

        if not should_push:
            logger.info(
                f"在 {account_type}: {account_id} 上发现有更新的内容，但AI决定不推送 (置信度: {confidence}%)")
            logger.debug(f"不推送原因: {reason}")
            logger.debug(f"内容: {content[:100]}..." if len(content) > 100 else content)

            # 即使不推送，也保存到数据库
            if save_to_db:
                try:
                    from web_app import AnalysisResult, db
                    logger.debug("保存分析结果到数据库")
                    db_result = AnalysisResult(
                        social_network=account_type,
                        account_id=account_id,
                        post_id=post.id,
                        post_time=post_time,
                        content=content,
                        analysis=summary,
                        is_relevant=False,  # 不推送的内容标记为不相关
                        confidence=confidence,
                        reason=reason
                    )
                    db.session.add(db_result)
                    db.session.commit()
                    logger.debug("分析结果已保存到数据库")
                except Exception as e:
                    logger.error(f"保存分析结果到数据库时出错: {str(e)}")
                    if 'db' in locals() and hasattr(db, 'session'):
                        db.session.rollback()

            return result

        logger.info(f"在 {account_type}: {account_id} 上发现内容，AI决定推送 (置信度: {confidence}%)")
        logger.debug(f"推送原因: {reason}")

        # 构建通知消息
        markdown_msg = f"""# [{post.poster_name}]({post.poster_url}) {post_time.strftime('%Y-%m-%d %H:%M:%S')}

{summary}

**AI推送理由**: {reason}

origin: [{post.url}]({post.url})"""

        # 使用Apprise发送通知
        try:
            logger.debug(f"发送通知，标签: {tag}")
            # 确保tag是字符串
            tag_str = str(tag) if tag is not None else 'all'
            notification_result = send_notification(
                message=markdown_msg,
                title=f"来自 {post.poster_name} 的更新",
                tag=tag_str
            )
            if notification_result:
                logger.info("通知发送成功")
            else:
                logger.warning("通知发送失败")
        except Exception as e:
            logger.error(f"发送通知时出错: {str(e)}")

        # 如果启用了自动回复，尝试回复
        # 兼容两种字段名：enable_auto_reply（数据库字段）和enableAutoReply（YAML配置字段）
        account_auto_reply = account.get('enable_auto_reply', account.get('enableAutoReply', False))
        if enable_auto_reply and account_auto_reply:
            try:
                logger.info(f"尝试自动回复帖子 {post.id}")
                reply_result = auto_reply(post, enable_auto_reply, auto_reply_prompt)
                if reply_result:
                    logger.info("自动回复成功")
                else:
                    logger.info("自动回复未执行或失败")
            except Exception as e:
                logger.error(f"自动回复时出错: {str(e)}")

        # 保存分析结果到数据库
        if save_to_db:
            try:
                from web_app import AnalysisResult, db
                logger.debug("保存分析结果到数据库")
                db_result = AnalysisResult(
                    social_network=account_type,
                    account_id=account_id,
                    post_id=post.id,
                    post_time=post_time,
                    content=content,
                    analysis=summary,
                    is_relevant=True,  # 推送的内容标记为相关
                    confidence=confidence,
                    reason=reason
                )
                db.session.add(db_result)
                db.session.commit()
                logger.debug("分析结果已保存到数据库")
            except Exception as e:
                logger.error(f"保存分析结果到数据库时出错: {str(e)}")
                if 'db' in locals() and hasattr(db, 'session'):
                    db.session.rollback()

        return result
    except Exception as e:
        logger.error(f"处理帖子时发生错误: {str(e)}", exc_info=True)
        return result

def process_account_posts(account, enable_auto_reply=False, auto_reply_prompt="", save_to_db=False):
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

    total = 0
    relevant = 0

    try:
        # 获取帖子
        posts = []
        if account_type == 'twitter':
            posts = fetchTwitter(account_id)
            logger.debug(f"从 Twitter 账号 {account_id} 获取到 {len(posts)} 条新帖子")

        if not posts:
            logger.info(f"在 {account_type}: {account_id} 上未发现有更新的内容")
            return (0, 0)

        total = len(posts)

        # 分批处理帖子
        for i in range(0, len(posts), BATCH_SIZE):
            batch = posts[i:i+BATCH_SIZE]
            logger.debug(f"处理批次 {i//BATCH_SIZE + 1}/{(len(posts)-1)//BATCH_SIZE + 1}, 包含 {len(batch)} 条帖子")

            # 使用线程池并行处理
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batch))) as executor:
                # 提交任务
                future_to_post = {
                    executor.submit(
                        process_post,
                        post,
                        account,
                        enable_auto_reply,
                        auto_reply_prompt,
                        save_to_db
                    ): post for post in batch
                }

                # 获取结果
                for future in concurrent.futures.as_completed(future_to_post):
                    post = future_to_post[future]
                    try:
                        result = future.result()
                        if result["success"] and result["is_relevant"]:
                            relevant += 1
                    except Exception as e:
                        logger.error(f"处理帖子 {post.id} 时发生错误: {str(e)}")

        return (total, relevant)
    except Exception as e:
        logger.error(f"处理账号 {account_id} 的帖子时发生错误: {str(e)}", exc_info=True)
        return (0, 0)

def main():
    start_time = time.time()
    logger.info("开始执行社交媒体监控任务")

    try:
        config = load_config_with_env('config/social-networks.yml')
        logger.debug(f"成功加载配置文件，包含 {len(config.get('social_networks', []))} 个社交媒体账号")

        # 处理socialNetworkId为数组的情况
        new_social_networks = []
        for account in config['social_networks']:
            if isinstance(account['socialNetworkId'], list):
                # 如果socialNetworkId是数组,为每个ID创建一个新的配置
                for social_id in account['socialNetworkId']:
                    if len(social_id) == 0:
                        continue

                    new_account = account.copy()
                    new_account['socialNetworkId'] = social_id
                    new_social_networks.append(new_account)
            else:
                # 如果不是数组直接添加原配置
                new_social_networks.append(account)

        # 用新的配置替换原配置
        config['social_networks'] = new_social_networks
        logger.debug(f"处理后的社交媒体账号数量: {len(new_social_networks)}")

        # 获取自动回复设置
        enable_auto_reply = os.getenv("ENABLE_AUTO_REPLY", "false").lower() == "true"
        auto_reply_prompt = os.getenv("AUTO_REPLY_PROMPT", "")
        logger.debug(f"自动回复功能状态: {'启用' if enable_auto_reply else '禁用'}")

        # 获取代理设置
        proxy = os.getenv("HTTP_PROXY", "")
        if proxy:
            logger.debug(f"使用代理: {proxy}")
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy

        # 保存分析结果到数据库
        try:
            from web_app import AnalysisResult, db
            save_to_db = True
            logger.debug("已连接到数据库，将保存分析结果")
        except ImportError:
            save_to_db = False
            logger.debug("未找到数据库模块，不会保存分析结果")

        total_posts = 0
        relevant_posts = 0

        # 处理所有账号
        for account in config['social_networks']:
            account_total, account_relevant = process_account_posts(
                account,
                enable_auto_reply,
                auto_reply_prompt,
                save_to_db
            )
            total_posts += account_total
            relevant_posts += account_relevant

        execution_time = time.time() - start_time
        logger.info(f"社交媒体监控任务完成，处理了 {total_posts} 条帖子，其中 {relevant_posts} 条相关内容，耗时 {execution_time:.2f} 秒")

    except Exception as e:
        logger.error(f"执行社交媒体监控任务时出错: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
