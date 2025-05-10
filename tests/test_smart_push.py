"""
测试AI自主决策推送功能
"""

import os
import sys
import unittest
import json
from datetime import datetime, timezone

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import process_post
from templates.default_prompts import get_default_prompt
from modules.socialmedia.twitter import Post

# 模拟LLM响应
def mock_llm_response(prompt, use_cache=True):
    """模拟LLM响应"""
    # 检查提示词类型
    if 'is_relevant' in prompt:
        # 旧格式
        return json.dumps({
            "is_relevant": "1",
            "analytical_briefing": "这是一个测试分析"
        })
    else:
        # 新格式
        return json.dumps({
            "should_push": True,
            "confidence": 85,
            "reason": "内容包含重要信息",
            "summary": "这是一个测试摘要"
        })

# 替换LLM响应函数
import modules.langchain.llm
modules.langchain.llm.get_llm_response_with_cache = mock_llm_response

class TestSmartPush(unittest.TestCase):
    """测试AI自主决策推送功能"""
    
    def setUp(self):
        """测试前准备"""
        # 创建测试帖子
        self.post = Post(
            id="123456",
            content="这是一个测试帖子",
            poster_name="测试用户",
            poster_url="https://example.com/user",
            url="https://example.com/post/123456",
            created_at=datetime.now(timezone.utc)
        )
        
    def test_old_format_prompt(self):
        """测试旧格式提示词"""
        # 创建旧格式账号配置
        account = {
            'socialNetworkId': 'test_user',
            'type': 'twitter',
            'prompt': '你现在是一名专家，请分析以下内容：{content}。返回格式：{"is_relevant": "是否相关，1或0", "analytical_briefing": "分析简报"}',
            'tag': 'test'
        }
        
        # 处理帖子
        result = process_post(self.post, account)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertTrue(result['is_relevant'])
        self.assertTrue(result['should_push'])
        self.assertEqual(result['confidence'], 100)
        self.assertEqual(result['reason'], "符合预设主题")
        
    def test_new_format_prompt(self):
        """测试新格式提示词"""
        # 创建新格式账号配置
        account = {
            'socialNetworkId': 'test_user',
            'type': 'twitter',
            'prompt': get_default_prompt(),
            'tag': 'test'
        }
        
        # 处理帖子
        result = process_post(self.post, account)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertTrue(result['is_relevant'])
        self.assertTrue(result['should_push'])
        self.assertEqual(result['confidence'], 85)
        self.assertEqual(result['reason'], "内容包含重要信息")
        self.assertEqual(result['summary'], "这是一个测试摘要")
        
    def test_default_prompt(self):
        """测试默认提示词"""
        # 创建没有提示词的账号配置
        account = {
            'socialNetworkId': 'test_user',
            'type': 'twitter',
            'tag': 'test'
        }
        
        # 处理帖子
        result = process_post(self.post, account)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertTrue(result['is_relevant'])
        self.assertTrue(result['should_push'])
        self.assertEqual(result['confidence'], 85)
        self.assertEqual(result['reason'], "内容包含重要信息")
        
if __name__ == '__main__':
    unittest.main()
