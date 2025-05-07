# 修改版主程序，不使用 Redis
import os
import sys
import logging
from modules.socialmedia.twitter import fetch as fetchTwitter, auto_reply

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("开始抓取 Twitter 账号...")
        fetchTwitter()
        logger.info("Twitter 抓取完成")
        
        if os.environ.get('ENABLE_AUTO_REPLY', 'false').lower() == 'true':
            logger.info("开始处理自动回复...")
            auto_reply()
            logger.info("自动回复处理完成")
    except Exception as e:
        logger.error(f"执行过程中出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
