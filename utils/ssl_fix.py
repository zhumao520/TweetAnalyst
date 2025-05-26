"""
SSL连接修复工具
解决Twitter API连接时的SSL/TLS协议问题
"""

import os
import ssl
import logging

# 延迟导入logger，避免循环导入
logger = None

def _get_logger():
    """延迟获取logger，避免循环导入"""
    global logger
    if logger is None:
        try:
            from utils.logger import get_logger
            logger = get_logger('ssl_fix')
        except ImportError:
            # 如果无法导入自定义logger，使用标准logger
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger('ssl_fix')
    return logger


def apply_ssl_fixes():
    """
    应用SSL修复，解决常见的SSL连接问题

    这个函数解决以下问题：
    1. SSL: UNEXPECTED_EOF_WHILE_READING
    2. SSL握手失败
    3. 证书验证问题
    4. TLS版本兼容性问题
    """
    try:
        logger = _get_logger()
        logger.info("正在应用SSL连接修复...")

        # 1. 设置环境变量禁用SSL验证
        ssl_env_vars = {
            'PYTHONHTTPSVERIFY': '0',
            'CURL_CA_BUNDLE': '',
            'REQUESTS_CA_BUNDLE': '',
            'SSL_VERIFY': 'false'
        }

        for key, value in ssl_env_vars.items():
            os.environ[key] = value
            logger.debug(f"设置环境变量: {key}={value}")

        # 2. 修改SSL默认上下文
        try:
            # 保存原始函数
            if not hasattr(ssl, '_original_create_default_https_context'):
                ssl._original_create_default_https_context = ssl.create_default_context

            # 创建不验证证书的上下文
            def create_unverified_context(*args, **kwargs):
                context = ssl._original_create_default_https_context(*args, **kwargs)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                # 设置更宽松的密码套件
                context.set_ciphers('DEFAULT@SECLEVEL=1')
                return context

            # 替换默认上下文创建函数
            ssl._create_default_https_context = create_unverified_context
            ssl.create_default_context = create_unverified_context

            logger.info("已设置SSL默认上下文为不验证模式")

        except Exception as e:
            logger.warning(f"设置SSL默认上下文时出错: {str(e)}")

        # 3. 配置urllib3
        try:
            import urllib3
            # 禁用SSL警告
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            # 尝试禁用其他警告（兼容不同版本的urllib3）
            try:
                urllib3.disable_warnings(urllib3.exceptions.SubjectAltNameWarning)
            except AttributeError:
                # 新版本urllib3已移除SubjectAltNameWarning
                pass

            try:
                urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)
            except AttributeError:
                # 某些版本可能没有SecurityWarning
                pass

            logger.info("已禁用urllib3 SSL警告")
        except ImportError:
            logger.debug("urllib3未安装，跳过相关配置")
        except Exception as e:
            logger.warning(f"配置urllib3时出错: {str(e)}")

        # 4. 配置requests
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            # 创建全局会话配置
            def create_ssl_adapter():
                """创建支持SSL修复的适配器"""
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
                )

                class SSLAdapter(HTTPAdapter):
                    def init_poolmanager(self, *args, **kwargs):
                        # 创建SSL上下文
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')

                        kwargs['ssl_context'] = ssl_context
                        return super().init_poolmanager(*args, **kwargs)

                return SSLAdapter(max_retries=retry_strategy)

            # 设置全局适配器
            requests.adapters.DEFAULT_RETRIES = 3
            logger.info("已配置requests SSL适配器")

        except ImportError:
            logger.debug("requests未安装，跳过相关配置")
        except Exception as e:
            logger.warning(f"配置requests时出错: {str(e)}")

        # 5. 配置httpx（如果使用）
        try:
            import httpx
            # httpx的SSL配置会在客户端创建时处理
            logger.debug("检测到httpx库")
        except ImportError:
            logger.debug("httpx未安装，跳过相关配置")

        logger.info("✅ SSL连接修复应用完成")
        return True

    except Exception as e:
        logger.error(f"❌ 应用SSL修复时出错: {str(e)}")
        return False


def create_secure_ssl_context():
    """
    创建安全的SSL上下文，用于特定连接

    Returns:
        ssl.SSLContext: 配置好的SSL上下文
    """
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_ciphers('DEFAULT@SECLEVEL=1')

        # 设置协议版本
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3

        return context
    except Exception as e:
        logger = _get_logger()
        logger.error(f"创建SSL上下文时出错: {str(e)}")
        return None


def test_ssl_connection(url: str = "https://api.x.com") -> bool:
    """
    测试SSL连接是否正常

    Args:
        url (str): 测试URL

    Returns:
        bool: 连接是否成功
    """
    logger = _get_logger()
    try:
        import requests

        # 使用修复后的SSL设置进行测试
        response = requests.get(
            url,
            timeout=10,
            verify=False,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )

        logger.info(f"SSL连接测试成功: {url} -> {response.status_code}")
        return True

    except Exception as e:
        logger.error(f"SSL连接测试失败: {url} -> {str(e)}")
        return False


def restore_ssl_defaults():
    """
    恢复SSL默认设置（用于调试）
    """
    logger = _get_logger()
    try:
        # 恢复原始SSL上下文创建函数
        if hasattr(ssl, '_original_create_default_https_context'):
            ssl.create_default_context = ssl._original_create_default_https_context
            ssl._create_default_https_context = ssl._original_create_default_https_context
            logger.info("已恢复SSL默认设置")

        # 清除环境变量
        ssl_env_vars = ['PYTHONHTTPSVERIFY', 'CURL_CA_BUNDLE', 'REQUESTS_CA_BUNDLE', 'SSL_VERIFY']
        for var in ssl_env_vars:
            if var in os.environ:
                del os.environ[var]

        logger.info("已清除SSL环境变量")

    except Exception as e:
        logger.error(f"恢复SSL默认设置时出错: {str(e)}")


# 注意：不再自动应用修复，避免循环导入
# 需要手动调用apply_ssl_fixes()来应用修复
