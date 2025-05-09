"""
YAML工具函数
处理YAML配置文件的读写操作
"""

import os
import yaml
import logging
from models import db, SocialAccount
from utils.config import get_default_prompt_template, get_config

# 创建日志记录器
logger = logging.getLogger('utils.yaml')

def load_config_with_env(config_path):
    """
    加载YAML配置文件，并替换环境变量
    
    Args:
        config_path: YAML配置文件路径
        
    Returns:
        dict: 配置数据
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 替换环境变量
        config = replace_env_vars(config)
        
        return config
    except Exception as e:
        logger.error(f"加载YAML配置文件时出错: {str(e)}")
        return {}

def replace_env_vars(obj):
    """
    递归替换对象中的环境变量引用
    
    Args:
        obj: 要处理的对象
        
    Returns:
        处理后的对象
    """
    if isinstance(obj, dict):
        return {k: replace_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_env_vars(item) for item in obj]
    elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
        env_var = obj[2:-1]
        return os.environ.get(env_var, '')
    else:
        return obj

def sync_accounts_to_yaml():
    """
    将数据库中的账号同步到YAML配置文件
    
    Returns:
        bool: 是否成功
    """
    try:
        accounts = SocialAccount.query.all()

        # 构建配置数据
        config_data = {'social_networks': []}

        for account in accounts:
            # 获取默认提示词模板
            default_prompt = get_default_prompt_template(account.type)

            account_data = {
                'type': account.type,
                'socialNetworkId': account.account_id,
                'tag': account.tag,
                'enableAutoReply': account.enable_auto_reply,
                'prompt': account.prompt_template or default_prompt
            }

            config_data['social_networks'].append(account_data)

        # 写入配置文件
        config_path = 'config/social-networks.yml'
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        logger.info(f"成功将 {len(accounts)} 个账号同步到配置文件")
        return True
    except Exception as e:
        logger.error(f"同步账号到配置文件时出错: {str(e)}")
        return False

def import_accounts_from_yaml():
    """
    从YAML配置文件导入账号到数据库
    
    Returns:
        tuple: (成功导入数量, 总数量)
    """
    try:
        config_path = 'config/social-networks.yml'
        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return 0, 0
        
        # 加载配置文件
        config = load_config_with_env(config_path)
        if not config or 'social_networks' not in config:
            logger.warning("配置文件中没有social_networks节点")
            return 0, 0
        
        social_networks = config['social_networks']
        success_count = 0
        
        for network in social_networks:
            try:
                # 检查必要字段
                if 'type' not in network or 'socialNetworkId' not in network:
                    logger.warning(f"配置项缺少必要字段: {network}")
                    continue
                
                # 检查账号是否已存在
                account_type = network['type']
                account_id = network['socialNetworkId']
                
                existing = SocialAccount.query.filter_by(
                    type=account_type,
                    account_id=account_id
                ).first()
                
                if existing:
                    # 更新现有账号
                    existing.tag = network.get('tag', 'all')
                    existing.enable_auto_reply = network.get('enableAutoReply', False)
                    existing.prompt_template = network.get('prompt')
                    db.session.commit()
                    logger.info(f"更新账号: {account_type}:{account_id}")
                else:
                    # 创建新账号
                    new_account = SocialAccount(
                        type=account_type,
                        account_id=account_id,
                        tag=network.get('tag', 'all'),
                        enable_auto_reply=network.get('enableAutoReply', False),
                        prompt_template=network.get('prompt')
                    )
                    db.session.add(new_account)
                    db.session.commit()
                    logger.info(f"创建账号: {account_type}:{account_id}")
                
                success_count += 1
            except Exception as e:
                db.session.rollback()
                logger.error(f"导入账号时出错: {str(e)}")
        
        return success_count, len(social_networks)
    except Exception as e:
        logger.error(f"从配置文件导入账号时出错: {str(e)}")
        return 0, 0
