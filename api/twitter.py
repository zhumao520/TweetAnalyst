"""
Twitter API模块
处理所有Twitter相关的API请求
"""

import logging
from flask import Blueprint, jsonify, session
from api.utils import api_response, handle_api_exception, login_required

# 创建日志记录器
logger = logging.getLogger('api.twitter')

# 创建Blueprint
twitter_api = Blueprint('twitter_api', __name__, url_prefix='/twitter')

@twitter_api.route('/current_library', methods=['GET'])
@login_required
@handle_api_exception
def get_current_twitter_library():
    """获取当前使用的Twitter库信息"""
    logger.info("获取当前使用的Twitter库信息")

    try:
        # 获取Twitter客户端管理器
        from modules.socialmedia.twitter_client_manager import get_twitter_manager
        twitter_manager = get_twitter_manager()

        # 获取当前库和可用库信息
        current_library = twitter_manager.current_library if twitter_manager.initialized else 'none'
        available_libraries = twitter_manager.get_available_libraries()

        # 获取配置的偏好设置
        from services.config_service import get_config
        library_preference = get_config('TWITTER_LIBRARY', 'auto')

        return api_response(
            success=True,
            message="获取Twitter库信息成功",
            current_library=current_library,
            available_libraries=available_libraries,
            library_preference=library_preference,
            initialized=twitter_manager.initialized
        )
    except Exception as e:
        logger.error(f"获取Twitter库信息时出错: {str(e)}")
        return api_response(
            success=False,
            message=f"获取Twitter库信息失败: {str(e)}"
        ), 500

@twitter_api.route('/switch_library', methods=['POST'])
@login_required
@handle_api_exception
def switch_twitter_library():
    """切换Twitter库"""
    logger.info("切换Twitter库")

    try:
        from flask import request
        data = request.get_json() or {}
        target_library = data.get('library', '').strip().lower()

        if target_library not in ['tweety', 'twikit']:
            return api_response(
                success=False,
                message="不支持的Twitter库，仅支持 'tweety' 或 'twikit'"
            ), 400

        # 获取Twitter客户端管理器
        from modules.socialmedia.twitter_client_manager import get_twitter_manager
        twitter_manager = get_twitter_manager()

        # 检查目标库是否可用
        available_libraries = twitter_manager.get_available_libraries()
        if target_library not in available_libraries:
            return api_response(
                success=False,
                message=f"Twitter库 '{target_library}' 不可用，可用库: {', '.join(available_libraries)}"
            ), 400

        # 尝试切换库
        success = twitter_manager.switch_library(target_library)

        if success:
            # 更新配置
            from services.config_service import set_config
            set_config('TWITTER_LIBRARY', target_library, description=f'Twitter库偏好设置')

            return api_response(
                success=True,
                message=f"成功切换到 {target_library} 库",
                current_library=twitter_manager.current_library,
                initialized=twitter_manager.initialized
            )
        else:
            return api_response(
                success=False,
                message=f"切换到 {target_library} 库失败"
            ), 500

    except Exception as e:
        logger.error(f"切换Twitter库时出错: {str(e)}")
        return api_response(
            success=False,
            message=f"切换Twitter库失败: {str(e)}"
        ), 500

@twitter_api.route('/reinitialize', methods=['POST'])
@login_required
@handle_api_exception
def reinitialize_twitter():
    """重新初始化Twitter客户端"""
    logger.info("重新初始化Twitter客户端")

    try:
        # 获取Twitter客户端管理器
        from modules.socialmedia.twitter_client_manager import get_twitter_manager
        twitter_manager = get_twitter_manager()

        # 获取配置的偏好设置
        from services.config_service import get_config
        library_preference = get_config('TWITTER_LIBRARY', 'auto')

        # 重新初始化
        if library_preference == 'auto':
            success = twitter_manager.auto_initialize()
        else:
            success = twitter_manager.switch_library(library_preference)

        if success:
            return api_response(
                success=True,
                message="Twitter客户端重新初始化成功",
                current_library=twitter_manager.current_library,
                initialized=twitter_manager.initialized
            )
        else:
            return api_response(
                success=False,
                message="Twitter客户端重新初始化失败"
            ), 500

    except Exception as e:
        logger.error(f"重新初始化Twitter客户端时出错: {str(e)}")
        return api_response(
            success=False,
            message=f"重新初始化Twitter客户端失败: {str(e)}"
        ), 500

@twitter_api.route('/reset_client', methods=['POST'])
@login_required
@handle_api_exception
def reset_twitter_client():
    """重置并重新初始化Twitter客户端"""
    try:
        logger.info("用户请求重置Twitter客户端")

        # 获取Twitter客户端管理器
        from modules.socialmedia.twitter_client_manager import get_twitter_manager
        twitter_manager = get_twitter_manager()

        # 完全重置客户端状态
        twitter_manager.tweety_client = None
        twitter_manager.tweety_async_client = None
        twitter_manager.twikit_client = None
        twitter_manager.current_library = None
        twitter_manager.initialized = False

        # 清除全局变量缓存
        try:
            from modules.socialmedia import twitter
            twitter.app = None
            twitter.async_app = None
            logger.info("已清除Twitter全局变量缓存")
        except Exception as e:
            logger.warning(f"清除Twitter全局变量缓存时出错: {str(e)}")

        # 清除会话文件
        import os
        session_files = ['session.tw_session', 'session', '.tw_session']
        for session_file in session_files:
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                    logger.info(f"已删除旧的会话文件: {session_file}")
                except Exception as e:
                    logger.warning(f"删除会话文件 {session_file} 失败: {str(e)}")

        # 清除相关缓存
        try:
            from utils.redisClient import redis_client
            # 清除Twitter相关的缓存
            cache_keys = redis_client.keys("twitter:*")
            for key in cache_keys:
                redis_client.delete(key)
            logger.info(f"已清除 {len(cache_keys)} 个Twitter相关缓存")
        except Exception as cache_error:
            logger.warning(f"清除缓存时出错: {str(cache_error)}")

        # 获取配置的偏好设置
        from services.config_service import get_config
        library_preference = get_config('TWITTER_LIBRARY', 'auto')

        # 重新初始化
        if library_preference == 'auto':
            success = twitter_manager.auto_initialize()
        else:
            success = twitter_manager.switch_library(library_preference)

        if success:
            return api_response(
                success=True,
                message="Twitter客户端已重置并重新初始化成功",
                current_library=twitter_manager.current_library,
                initialized=twitter_manager.initialized
            )
        else:
            return api_response(
                success=False,
                message="Twitter客户端重置成功，但重新初始化失败"
            ), 500

    except Exception as e:
        logger.error(f"重置Twitter客户端时出错: {str(e)}")
        return api_response(
            success=False,
            message=f"重置失败: {str(e)}"
        ), 500
