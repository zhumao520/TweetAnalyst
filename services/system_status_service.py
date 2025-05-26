"""
系统状态服务
提供系统各组件状态检查功能
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any

# 创建日志记录器
logger = logging.getLogger('services.system_status')


def get_system_status() -> Dict[str, Any]:
    """
    获取系统状态信息
    
    Returns:
        Dict[str, Any]: 系统状态信息
    """
    status = {
        'timestamp': datetime.now().isoformat(),
        'database': check_database_status(),
        'ai_service': check_ai_service_status(),
        'notification': check_notification_status(),
        'proxy': check_proxy_status(),
        'twitter': check_twitter_status(),
        'core_scraping': check_core_scraping_status()
    }
    
    logger.info("系统状态检查完成")
    return status


def check_database_status() -> Dict[str, Any]:
    """检查数据库状态"""
    try:
        from web_app import AnalysisResult, SocialAccount, db, app
        
        with app.app_context():
            # 检查数据库连接
            result_count = AnalysisResult.query.count()
            account_count = SocialAccount.query.count()
            
            # 检查数据库文件大小
            db_path = os.getenv('DATABASE_PATH', 'instance/tweetAnalyst.db')
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.getcwd(), db_path)
            
            db_size = 0
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
            
            return {
                'status': 'normal',
                'message': '数据库连接正常',
                'details': {
                    'result_count': result_count,
                    'account_count': account_count,
                    'db_size_mb': round(db_size / (1024 * 1024), 2),
                    'db_path': db_path
                }
            }
            
    except Exception as e:
        logger.error(f"数据库状态检查失败: {str(e)}")
        return {
            'status': 'error',
            'message': f'数据库连接失败: {str(e)}',
            'details': {}
        }


def check_ai_service_status() -> Dict[str, Any]:
    """检查AI服务状态"""
    try:
        from services.config_service import get_config
        
        # 检查API密钥配置
        llm_api_key = get_config('LLM_API_KEY')
        llm_api_base = get_config('LLM_API_BASE')
        llm_model = get_config('LLM_MODEL')
        
        if not llm_api_key:
            return {
                'status': 'warning',
                'message': 'AI API密钥未配置',
                'details': {
                    'api_key_configured': False,
                    'api_base': llm_api_base or '未配置',
                    'model': llm_model or '未配置'
                }
            }
        
        # 尝试加载AI模块
        try:
            from modules.langchain.llm import get_llm_response_with_cache
            return {
                'status': 'normal',
                'message': 'AI服务正常',
                'details': {
                    'api_key_configured': True,
                    'api_base': llm_api_base or '默认',
                    'model': llm_model or '默认',
                    'module_loaded': True
                }
            }
        except Exception as module_error:
            return {
                'status': 'warning',
                'message': f'AI模块加载异常: {str(module_error)}',
                'details': {
                    'api_key_configured': True,
                    'api_base': llm_api_base or '默认',
                    'model': llm_model or '默认',
                    'module_loaded': False
                }
            }
            
    except Exception as e:
        logger.error(f"AI服务状态检查失败: {str(e)}")
        return {
            'status': 'error',
            'message': f'AI服务检查失败: {str(e)}',
            'details': {}
        }


def check_notification_status() -> Dict[str, Any]:
    """检查推送服务状态"""
    try:
        from services.config_service import get_config
        
        # 检查推送配置
        push_enabled = get_config('PUSH_ENABLED', 'false').lower() == 'true'
        push_url = get_config('PUSH_URL')
        
        if not push_enabled:
            return {
                'status': 'disabled',
                'message': '推送服务已禁用',
                'details': {
                    'enabled': False,
                    'url_configured': bool(push_url)
                }
            }
        
        if not push_url:
            return {
                'status': 'warning',
                'message': '推送URL未配置',
                'details': {
                    'enabled': True,
                    'url_configured': False
                }
            }
        
        return {
            'status': 'normal',
            'message': '推送服务配置正常',
            'details': {
                'enabled': True,
                'url_configured': True,
                'push_url': push_url
            }
        }
        
    except Exception as e:
        logger.error(f"推送服务状态检查失败: {str(e)}")
        return {
            'status': 'error',
            'message': f'推送服务检查失败: {str(e)}',
            'details': {}
        }


def check_proxy_status() -> Dict[str, Any]:
    """检查代理服务状态"""
    try:
        from services.config_service import get_config
        
        # 检查代理配置
        proxy_enabled = get_config('PROXY_ENABLED', 'false').lower() == 'true'
        proxy_host = get_config('PROXY_HOST')
        proxy_port = get_config('PROXY_PORT')
        
        if not proxy_enabled:
            return {
                'status': 'disabled',
                'message': '代理服务已禁用',
                'details': {
                    'enabled': False,
                    'host': proxy_host or '未配置',
                    'port': proxy_port or '未配置'
                }
            }
        
        if not proxy_host or not proxy_port:
            return {
                'status': 'warning',
                'message': '代理配置不完整',
                'details': {
                    'enabled': True,
                    'host': proxy_host or '未配置',
                    'port': proxy_port or '未配置'
                }
            }
        
        return {
            'status': 'normal',
            'message': '代理服务配置正常',
            'details': {
                'enabled': True,
                'host': proxy_host,
                'port': proxy_port
            }
        }
        
    except Exception as e:
        logger.error(f"代理服务状态检查失败: {str(e)}")
        return {
            'status': 'error',
            'message': f'代理服务检查失败: {str(e)}',
            'details': {}
        }


def check_twitter_status() -> Dict[str, Any]:
    """检查Twitter服务状态"""
    try:
        from services.config_service import get_config
        
        # 检查Twitter配置
        twitter_username = get_config('TWITTER_USERNAME')
        twitter_password = get_config('TWITTER_PASSWORD')
        twitter_library = get_config('TWITTER_LIBRARY', 'auto')
        
        # 检查库可用性
        tweety_available = False
        twikit_available = False
        
        try:
            from modules.socialmedia import twitter
            tweety_available = True
        except ImportError:
            pass
        
        try:
            from modules.socialmedia import twitter_twikit
            twikit_available = True
        except ImportError:
            pass
        
        if not twitter_username or not twitter_password:
            return {
                'status': 'warning',
                'message': 'Twitter凭据未完整配置',
                'details': {
                    'username_configured': bool(twitter_username),
                    'password_configured': bool(twitter_password),
                    'library_preference': twitter_library,
                    'tweety_available': tweety_available,
                    'twikit_available': twikit_available
                }
            }
        
        return {
            'status': 'normal',
            'message': 'Twitter服务配置正常',
            'details': {
                'username_configured': True,
                'password_configured': True,
                'library_preference': twitter_library,
                'tweety_available': tweety_available,
                'twikit_available': twikit_available
            }
        }
        
    except Exception as e:
        logger.error(f"Twitter服务状态检查失败: {str(e)}")
        return {
            'status': 'error',
            'message': f'Twitter服务检查失败: {str(e)}',
            'details': {}
        }


def check_core_scraping_status() -> Dict[str, Any]:
    """检查核心抓取组件状态"""
    try:
        # 检查主要模块是否可以导入
        modules_status = {}
        
        try:
            import main
            modules_status['main'] = True
        except ImportError as e:
            modules_status['main'] = False
            logger.warning(f"主模块导入失败: {str(e)}")
        
        try:
            from modules.socialmedia.post import Post
            modules_status['post'] = True
        except ImportError as e:
            modules_status['post'] = False
            logger.warning(f"Post模块导入失败: {str(e)}")
        
        try:
            from modules.socialmedia.twitter_utils import extract_media_info
            modules_status['twitter_utils'] = True
        except ImportError as e:
            modules_status['twitter_utils'] = False
            logger.warning(f"Twitter工具模块导入失败: {str(e)}")
        
        all_modules_ok = all(modules_status.values())
        
        return {
            'status': 'normal' if all_modules_ok else 'warning',
            'message': '核心抓取组件正常' if all_modules_ok else '部分核心组件异常',
            'details': modules_status
        }
        
    except Exception as e:
        logger.error(f"核心抓取组件状态检查失败: {str(e)}")
        return {
            'status': 'error',
            'message': f'核心抓取组件检查失败: {str(e)}',
            'details': {}
        }
