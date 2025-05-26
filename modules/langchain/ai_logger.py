"""
AI分析日志模块
用于记录AI分析相关的日志信息，包括分析请求、响应、性能指标等
"""

import os
import time
import json
import logging
from datetime import datetime
from utils.logger import get_logger

# 创建AI分析专用日志记录器
logger = get_logger('llm')

class AIAnalysisLogger:
    """
    AI分析日志记录器
    用于记录AI分析相关的详细信息，包括：
    - 分析请求和响应
    - 性能指标（响应时间、token使用量等）
    - 错误和异常情况
    - 缓存命中情况
    """

    def __init__(self):
        """初始化AI分析日志记录器"""
        self.logger = logger
        self.start_time = None
        self.request_id = None

    def start_request(self, prompt, provider_id=None, model=None):
        """
        记录分析请求开始
        
        Args:
            prompt (str): 提示词内容
            provider_id (str, optional): AI提供商ID
            model (str, optional): 使用的模型名称
        
        Returns:
            str: 请求ID
        """
        self.start_time = time.time()
        self.request_id = f"{int(self.start_time * 1000)}"
        
        # 记录请求信息
        request_info = {
            "request_id": self.request_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "provider_id": provider_id or "未指定",
            "model": model or "未指定",
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt
        }
        
        self.logger.info(f"AI分析请求开始 [ID:{self.request_id}] 提供商:{request_info['provider_id']} 模型:{request_info['model']}")
        self.logger.debug(f"AI分析请求详情: {json.dumps(request_info, ensure_ascii=False)}")
        
        return self.request_id
    
    def end_request(self, response, success=True, error=None, token_usage=None, cached=False):
        """
        记录分析请求结束
        
        Args:
            response (str): AI响应内容
            success (bool): 请求是否成功
            error (Exception, optional): 错误信息
            token_usage (dict, optional): Token使用情况
            cached (bool): 是否命中缓存
        """
        if not self.start_time:
            self.logger.warning("尝试结束未开始的AI分析请求")
            return
        
        # 计算响应时间
        end_time = time.time()
        response_time = end_time - self.start_time
        
        # 记录响应信息
        response_info = {
            "request_id": self.request_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "success": success,
            "response_time": f"{response_time:.2f}秒",
            "cached": cached,
            "response_length": len(response) if response else 0,
            "response_preview": (response[:100] + "..." if response and len(response) > 100 else response) if success else None,
            "error": str(error) if error else None
        }
        
        # 添加token使用情况
        if token_usage:
            response_info["token_usage"] = token_usage
        
        # 根据请求结果记录不同级别的日志
        if success:
            if cached:
                self.logger.info(f"AI分析请求完成 [ID:{self.request_id}] 响应时间:{response_time:.2f}秒 (缓存命中)")
            else:
                self.logger.info(f"AI分析请求完成 [ID:{self.request_id}] 响应时间:{response_time:.2f}秒")
                
            if token_usage:
                self.logger.info(f"Token使用情况 [ID:{self.request_id}] 输入:{token_usage.get('prompt_tokens', 0)} 输出:{token_usage.get('completion_tokens', 0)} 总计:{token_usage.get('total_tokens', 0)}")
        else:
            self.logger.error(f"AI分析请求失败 [ID:{self.request_id}] 响应时间:{response_time:.2f}秒 错误:{str(error)}")
        
        self.logger.debug(f"AI分析响应详情: {json.dumps(response_info, ensure_ascii=False)}")
        
        # 重置计时器
        self.start_time = None
        self.request_id = None
    
    def log_analysis_result(self, post_id, account_id, is_relevant, confidence, reason, summary=None):
        """
        记录分析结果
        
        Args:
            post_id (str): 帖子ID
            account_id (str): 账号ID
            is_relevant (bool): 是否相关
            confidence (float): 置信度
            reason (str): 原因
            summary (str, optional): 摘要
        """
        result_info = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "post_id": post_id,
            "account_id": account_id,
            "is_relevant": is_relevant,
            "confidence": confidence,
            "reason_preview": reason[:100] + "..." if reason and len(reason) > 100 else reason,
            "summary_preview": summary[:100] + "..." if summary and len(summary) > 100 else summary
        }
        
        if is_relevant:
            self.logger.info(f"内容相关 [帖子:{post_id}] [账号:{account_id}] 置信度:{confidence}% 原因:{result_info['reason_preview']}")
        else:
            self.logger.info(f"内容不相关 [帖子:{post_id}] [账号:{account_id}] 置信度:{confidence}% 原因:{result_info['reason_preview']}")
        
        self.logger.debug(f"分析结果详情: {json.dumps(result_info, ensure_ascii=False)}")
    
    def log_provider_selection(self, provider_id, model, reason=None):
        """
        记录AI提供商选择
        
        Args:
            provider_id (str): 提供商ID
            model (str): 模型名称
            reason (str, optional): 选择原因
        """
        self.logger.info(f"选择AI提供商: {provider_id} 模型: {model}" + (f" 原因: {reason}" if reason else ""))
    
    def log_provider_error(self, provider_id, error, retry_count=None):
        """
        记录AI提供商错误
        
        Args:
            provider_id (str): 提供商ID
            error (Exception): 错误信息
            retry_count (int, optional): 重试次数
        """
        error_msg = f"AI提供商错误: {provider_id} 错误: {str(error)}"
        if retry_count is not None:
            error_msg += f" 重试次数: {retry_count}"
        self.logger.error(error_msg)
    
    def log_cache_operation(self, operation, key, success=True, error=None):
        """
        记录缓存操作
        
        Args:
            operation (str): 操作类型（读取/写入）
            key (str): 缓存键
            success (bool): 操作是否成功
            error (Exception, optional): 错误信息
        """
        if success:
            self.logger.debug(f"缓存{operation}成功: {key[:8]}...")
        else:
            self.logger.warning(f"缓存{operation}失败: {key[:8]}... 错误: {str(error)}")

# 创建全局AI分析日志记录器实例
ai_logger = AIAnalysisLogger()
