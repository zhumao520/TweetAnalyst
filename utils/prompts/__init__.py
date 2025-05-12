"""
提示词模块
包含各种用于AI分析的提示词模板
"""

from .default_prompts import (
    get_default_prompt,
    get_available_tags,
    register_prompt_template,
    PROMPT_TEMPLATES
)

__all__ = [
    'get_default_prompt',
    'get_available_tags',
    'register_prompt_template',
    'PROMPT_TEMPLATES'
]
