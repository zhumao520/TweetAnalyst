import os
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, cast, Date
from werkzeug.security import generate_password_hash, check_password_hash
from utils.yaml import load_config_with_env, replace_env_vars
from utils.logger import get_logger
import yaml

# 创建日志记录器
logger = get_logger('web_app')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev_key_please_change')

# 获取数据库路径
db_path = os.getenv('DATABASE_PATH', 'instance/tweetanalyst.db')
# 确保路径是绝对路径
if not os.path.isabs(db_path):
    db_path = os.path.join(os.getcwd(), db_path)
# 确保目录存在
os.makedirs(os.path.dirname(db_path), exist_ok=True)
# 设置数据库URI
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

logger.info(f"数据库路径: {db_path}")

db = SQLAlchemy(app)

# 数据模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class AnalysisResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    social_network = db.Column(db.String(50), nullable=False, index=True)
    account_id = db.Column(db.String(100), nullable=False, index=True)
    post_id = db.Column(db.String(100), nullable=False, index=True)
    post_time = db.Column(db.DateTime, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    analysis = db.Column(db.Text, nullable=False)
    is_relevant = db.Column(db.Boolean, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # 添加复合索引
    __table_args__ = (
        db.Index('idx_account_relevant', 'account_id', 'is_relevant'),
        db.Index('idx_network_account', 'social_network', 'account_id'),
        db.Index('idx_time_relevant', 'post_time', 'is_relevant'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'social_network': self.social_network,
            'account_id': self.account_id,
            'post_id': self.post_id,
            'post_time': self.post_time.isoformat(),
            'content': self.content,
            'analysis': self.analysis,
            'is_relevant': self.is_relevant,
            'created_at': self.created_at.isoformat()
        }

class SocialAccount(db.Model):
    """社交媒体账号模型"""
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False, index=True)  # 平台类型，如twitter
    account_id = db.Column(db.String(100), nullable=False, index=True)  # 账号ID
    tag = db.Column(db.String(50), default='all', index=True)  # 标签，用于分组
    enable_auto_reply = db.Column(db.Boolean, default=False, index=True)  # 是否启用自动回复
    prompt_template = db.Column(db.Text)  # 分析提示词模板
    auto_reply_template = db.Column(db.Text)  # 自动回复提示词模板
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 添加唯一约束和复合索引
    __table_args__ = (
        db.UniqueConstraint('type', 'account_id', name='uix_type_account'),
        db.Index('idx_type_tag', 'type', 'tag'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'account_id': self.account_id,
            'tag': self.tag,
            'enable_auto_reply': self.enable_auto_reply,
            'prompt_template': self.prompt_template,
            'auto_reply_template': self.auto_reply_template,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class SystemConfig(db.Model):
    """系统配置模型"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)  # 配置键
    value = db.Column(db.Text, nullable=True)  # 配置值
    is_secret = db.Column(db.Boolean, default=False)  # 是否为敏感信息
    description = db.Column(db.String(255), nullable=True)  # 配置描述
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class SystemState(db.Model):
    """系统状态模型，用于替代Redis存储状态信息"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False, index=True)  # 状态键
    value = db.Column(db.Text, nullable=True)  # 状态值
    expires_at = db.Column(db.DateTime, nullable=True, index=True)  # 过期时间
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @classmethod
    def cleanup_expired(cls):
        """清理过期的状态数据"""
        try:
            now = datetime.now(timezone.utc)
            expired = cls.query.filter(cls.expires_at < now).all()
            for item in expired:
                db.session.delete(item)
            db.session.commit()
            return len(expired)
        except Exception as e:
            logger.error(f"清理过期状态数据时出错: {str(e)}")
            db.session.rollback()
            return 0

# 辅助函数

# 系统配置管理函数
def get_config(key, default=None):
    """获取系统配置"""
    config = SystemConfig.query.filter_by(key=key).first()
    if config:
        return config.value
    return os.getenv(key, default)

def set_config(key, value, is_secret=False, description=None, update_env=True):
    """设置系统配置"""
    config = SystemConfig.query.filter_by(key=key).first()

    if config:
        config.value = value
        if description:
            config.description = description
        if is_secret is not None:
            config.is_secret = is_secret
    else:
        config = SystemConfig(
            key=key,
            value=value,
            is_secret=is_secret,
            description=description
        )
        db.session.add(config)

    db.session.commit()

    # 更新环境变量
    if update_env:
        os.environ[key] = value

        # 更新.env文件
        try:
            env_file = os.path.join(os.path.dirname(os.environ.get('DATABASE_PATH', '.')), '.env')
            env_lines = []

            # 读取现有.env文件
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    env_lines = f.readlines()

            # 更新或添加环境变量
            key_found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f"{key}="):
                    env_lines[i] = f"{key}={value}\n"
                    key_found = True
                    break

            if not key_found:
                env_lines.append(f"{key}={value}\n")

            # 写回.env文件
            with open(env_file, 'w') as f:
                f.writelines(env_lines)
        except Exception as e:
            logger.error(f"更新环境变量文件时出错: {str(e)}")

    return config

def is_system_initialized():
    """检查系统是否已初始化"""
    # 检查是否有管理员用户
    admin_exists = User.query.first() is not None

    # 检查是否有LLM API密钥
    llm_api_key = get_config('LLM_API_KEY')

    return admin_exists and llm_api_key

def create_default_admin():
    """创建默认管理员用户（如果不存在）"""
    with app.app_context():
        # 检查是否已存在用户
        if User.query.first() is not None:
            logger.debug("已存在用户，不创建默认管理员")
            return False

        # 创建默认管理员用户
        try:
            admin = User(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            logger.info("已创建默认管理员用户: admin/admin123")
            return True
        except Exception as e:
            logger.error(f"创建默认管理员用户时出错: {str(e)}")
            db.session.rollback()
            return False

def save_llm_config(api_key=None, api_model=None, api_base=None):
    """保存LLM配置"""
    if api_key:
        set_config('LLM_API_KEY', api_key, is_secret=True, description='LLM API密钥')

    if api_model:
        set_config('LLM_API_MODEL', api_model, description='LLM API模型')

    if api_base:
        set_config('LLM_API_BASE', api_base, description='LLM API基础URL')

def save_twitter_config(username=None, password=None, session=None):
    """保存Twitter配置"""
    if username:
        set_config('TWITTER_USERNAME', username, description='Twitter用户名')

    if password:
        set_config('TWITTER_PASSWORD', password, is_secret=True, description='Twitter密码')

    if session:
        set_config('TWITTER_SESSION', session, is_secret=True, description='Twitter会话数据')

def save_scheduler_config(interval_minutes=None):
    """保存定时任务配置"""
    if interval_minutes:
        set_config('SCHEDULER_INTERVAL_MINUTES', str(interval_minutes), description='定时任务执行间隔（分钟）')

def get_system_config():
    """获取所有系统配置"""
    configs = SystemConfig.query.all()
    result = {}

    for config in configs:
        if config.is_secret:
            # 对于敏感信息，只返回是否已设置
            result[config.key] = '******' if config.value else ''
        else:
            result[config.key] = config.value

    # 添加环境变量中的配置
    for key in ['LLM_API_KEY', 'LLM_API_MODEL', 'LLM_API_BASE',
                'TWITTER_USERNAME', 'TWITTER_PASSWORD', 'TWITTER_SESSION',
                'SCHEDULER_INTERVAL_MINUTES', 'HTTP_PROXY', 'APPRISE_URLS']:
        if key not in result:
            value = os.getenv(key, '')
            if key in ['LLM_API_KEY', 'TWITTER_PASSWORD', 'TWITTER_SESSION'] and value:
                result[key] = '******'
            else:
                result[key] = value

    return result

# 状态存储管理函数（替代Redis）
class DBStateStore:
    def __init__(self, auto_cleanup=True, cleanup_interval=3600):
        """
        初始化状态存储

        Args:
            auto_cleanup: 是否自动清理过期数据
            cleanup_interval: 清理间隔（秒）
        """
        self.auto_cleanup = auto_cleanup
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = datetime.now(timezone.utc)

    def get(self, key):
        """获取状态值"""
        # 尝试自动清理
        self._try_cleanup()

        state = SystemState.query.filter_by(key=key).first()
        if state and (state.expires_at is None or state.expires_at > datetime.now(timezone.utc)):
            return state.value
        return None

    def set(self, key, value, expire=None):
        """设置状态值"""
        # 尝试自动清理
        self._try_cleanup()

        state = SystemState.query.filter_by(key=key).first()
        expires_at = None
        if expire:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expire)

        if state:
            state.value = value
            state.expires_at = expires_at
            state.updated_at = datetime.now(timezone.utc)
        else:
            state = SystemState(key=key, value=value, expires_at=expires_at)
            db.session.add(state)

        try:
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"设置状态值时出错: {str(e)}")
            db.session.rollback()
            return False

    def expire(self, key, seconds):
        """设置过期时间"""
        state = SystemState.query.filter_by(key=key).first()
        if state:
            state.expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            try:
                db.session.commit()
                return True
            except Exception as e:
                logger.error(f"设置过期时间时出错: {str(e)}")
                db.session.rollback()
        return False

    def delete(self, key):
        """删除状态值"""
        state = SystemState.query.filter_by(key=key).first()
        if state:
            try:
                db.session.delete(state)
                db.session.commit()
                return True
            except Exception as e:
                logger.error(f"删除状态值时出错: {str(e)}")
                db.session.rollback()
        return False

    def cleanup(self):
        """清理过期数据"""
        count = SystemState.cleanup_expired()
        self.last_cleanup = datetime.now(timezone.utc)
        return count

    def _try_cleanup(self):
        """尝试自动清理"""
        if not self.auto_cleanup:
            return

        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
            self.cleanup()

# 创建Redis替代适配器
redis_client = DBStateStore()

def sync_accounts_to_yaml():
    """将数据库中的账号同步到YAML配置文件"""
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

def get_default_prompt_template(account_type):
    """获取默认提示词模板"""
    if account_type == 'twitter':
        return """你现在是一名专业分析师，请对以下社交媒体内容进行分析，并给按我指定的格式返回分析结果。

这是你需要分析的内容：{content}

这是输出格式的说明：
{
    "is_relevant": "是否与相关主题相关，只需要返回1或0这两个值之一即可",
    "analytical_briefing": "分析简报"
}

其中analytical_briefing的值是一个字符串，它是针对内容所做的分析简报，仅在is_relevant为1时会返回这个值。

analytical_briefing的内容是markdown格式的，它需要符合下面的规范：

原始正文，仅当需要分析的内容不是为中文时，这部分内容才会保留，否则这部分的内容为原始的正文

翻译后的内容，仅当需要分析的内容为英文时，才会有这部分的内容。

## Summarize

这部分需要用非常简明扼要的文字对内容进行总结。"""
    else:
        return """你现在是一名专业分析师，请对以下内容进行分析，并给按我指定的格式返回分析结果。

这是你需要分析的内容：{content}

这是输出格式的说明：
{
    "is_relevant": "是否与相关主题相关，只需要返回1或0这两个值之一即可",
    "analytical_briefing": "分析简报"
}

其中analytical_briefing的值是一个字符串，它是针对内容所做的分析简报，仅在is_relevant为1时会返回这个值。"""

def import_accounts_from_yaml():
    """从YAML配置文件导入账号到数据库"""
    try:
        config_path = os.path.join(os.getcwd(), 'config/social-networks.yml')

        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return False

        # 读取配置文件
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not config_data or 'social_networks' not in config_data:
            logger.warning("配置文件中没有找到social_networks节点")
            return False

        # 导入账号
        count = 0
        for account_data in config_data['social_networks']:
            # 检查账号是否已存在
            account_id = account_data.get('socialNetworkId')
            account_type = account_data.get('type')

            if not account_id or not account_type:
                continue

            # 如果是数组，需要分别处理
            if isinstance(account_id, list):
                for single_id in account_id:
                    if not single_id:
                        continue

                    existing = SocialAccount.query.filter_by(
                        type=account_type,
                        account_id=single_id
                    ).first()

                    if not existing:
                        new_account = SocialAccount(
                            type=account_type,
                            account_id=single_id,
                            tag=account_data.get('tag', 'all'),
                            enable_auto_reply=account_data.get('enableAutoReply', False),
                            prompt_template=account_data.get('prompt', '')
                        )
                        db.session.add(new_account)
                        count += 1
            else:
                existing = SocialAccount.query.filter_by(
                    type=account_type,
                    account_id=account_id
                ).first()

                if not existing:
                    new_account = SocialAccount(
                        type=account_type,
                        account_id=account_id,
                        tag=account_data.get('tag', 'all'),
                        enable_auto_reply=account_data.get('enableAutoReply', False),
                        prompt_template=account_data.get('prompt', '')
                    )
                    db.session.add(new_account)
                    count += 1

        db.session.commit()
        logger.info(f"成功从配置文件导入 {count} 个账号")
        return True
    except Exception as e:
        logger.error(f"从配置文件导入账号时出错: {str(e)}")
        db.session.rollback()
        return False

# 路由
@app.route('/')
def index():
    # 检查是否是首次登录
    is_first_login = os.getenv('FIRST_LOGIN', 'true').lower() == 'true'

    # 如果是首次登录，强制进行初始化
    if is_first_login:
        # 设置环境变量，标记已经不是首次登录
        os.environ['FIRST_LOGIN'] = 'false'
        # 尝试更新 .env 文件
        try:
            env_file = os.path.join(os.path.dirname(os.environ.get('DATABASE_PATH', '.')), '.env')
            env_lines = []

            # 读取现有.env文件
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    env_lines = f.readlines()

            # 更新或添加环境变量
            key_found = False
            for i, line in enumerate(env_lines):
                if line.startswith("FIRST_LOGIN="):
                    env_lines[i] = "FIRST_LOGIN=false\n"
                    key_found = True
                    break

            if not key_found:
                env_lines.append("FIRST_LOGIN=false\n")

            # 写回.env文件
            with open(env_file, 'w') as f:
                f.writelines(env_lines)
        except Exception as e:
            logger.error(f"更新环境变量文件时出错: {str(e)}")

        return redirect(url_for('setup'))

    # 检查系统是否已初始化
    if not is_system_initialized():
        return redirect(url_for('setup'))

    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 获取统计数据
    account_count = SocialAccount.query.count()
    result_count = AnalysisResult.query.count()
    relevant_count = AnalysisResult.query.filter_by(is_relevant=True).count()

    return render_template('index.html',
                          account_count=account_count,
                          result_count=result_count,
                          relevant_count=relevant_count)

@app.route('/test')
def test_page():
    """测试功能页面"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 获取系统状态
    from utils.test_utils import check_system_status
    system_status = check_system_status()

    return render_template('test.html', system_status=system_status)

@app.route('/analytics')
def analytics_page():
    """数据分析页面"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('analytics.html')

@app.route('/api/test/twitter', methods=['POST'])
def test_twitter_api():
    """测试Twitter API连接"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取请求参数
    data = request.get_json() or {}
    account_id = data.get('account_id', '')

    # 执行测试
    from utils.test_utils import test_twitter_connection
    result = test_twitter_connection(account_id)

    return jsonify(result)

@app.route('/api/test/llm', methods=['POST'])
def test_llm_api():
    """测试LLM API连接"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取请求参数
    data = request.get_json() or {}
    prompt = data.get('prompt', '')

    # 执行测试
    from utils.test_utils import test_llm_connection
    result = test_llm_connection(prompt)

    return jsonify(result)

@app.route('/api/test/proxy', methods=['POST'])
def test_proxy_connection():
    """测试代理连接"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取请求参数
    data = request.get_json() or {}
    test_url = data.get('url', '')

    # 执行测试
    from utils.test_utils import test_proxy_connection
    result = test_proxy_connection(test_url)

    return jsonify(result)

@app.route('/api/system/status')
def get_system_status():
    """获取系统状态"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取系统状态
    from utils.test_utils import check_system_status
    system_status = check_system_status()

    return jsonify({"success": True, "data": system_status})

@app.route('/api/notifications')
def get_notifications():
    """获取最新通知"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取最近24小时内的相关结果作为通知
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        notifications = AnalysisResult.query.filter(
            AnalysisResult.is_relevant == True,
            AnalysisResult.created_at >= one_day_ago
        ).order_by(AnalysisResult.created_at.desc()).limit(10).all()

        # 转换为JSON格式
        result = []
        for notification in notifications:
            result.append({
                'id': notification.id,
                'title': f'来自 {notification.social_network}: {notification.account_id} 的更新',
                'content': notification.content[:100] + ('...' if len(notification.content) > 100 else ''),
                'time': notification.created_at.isoformat(),
                'read': False,  # 默认未读
                'url': url_for('results', _external=True) + f'?id={notification.id}'
            })

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"获取通知时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"获取通知失败: {str(e)}"}), 500

@app.route('/api/analytics/summary')
def get_analytics_summary():
    """获取分析数据摘要"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取总体统计数据
        total_posts = AnalysisResult.query.count()
        relevant_posts = AnalysisResult.query.filter_by(is_relevant=True).count()

        # 获取按社交媒体平台分组的统计数据
        platform_stats = db.session.query(
            AnalysisResult.social_network,
            db.func.count(AnalysisResult.id).label('total'),
            db.func.sum(db.case([(AnalysisResult.is_relevant, 1)], else_=0)).label('relevant')
        ).group_by(AnalysisResult.social_network).all()

        platform_data = [
            {
                'platform': item[0],
                'total': item[1],
                'relevant': item[2] or 0,
                'relevance_rate': round((item[2] or 0) / item[1] * 100, 2) if item[1] > 0 else 0
            }
            for item in platform_stats
        ]

        # 获取按账号分组的统计数据
        account_stats = db.session.query(
            AnalysisResult.social_network,
            AnalysisResult.account_id,
            db.func.count(AnalysisResult.id).label('total'),
            db.func.sum(db.case([(AnalysisResult.is_relevant, 1)], else_=0)).label('relevant')
        ).group_by(AnalysisResult.social_network, AnalysisResult.account_id).all()

        account_data = [
            {
                'platform': item[0],
                'account_id': item[1],
                'total': item[2],
                'relevant': item[3] or 0,
                'relevance_rate': round((item[3] or 0) / item[2] * 100, 2) if item[2] > 0 else 0
            }
            for item in account_stats
        ]

        # 获取时间趋势数据（按天统计）

        # 获取最近30天的数据
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        time_stats = db.session.query(
            cast(AnalysisResult.post_time, Date).label('date'),
            db.func.count(AnalysisResult.id).label('total'),
            db.func.sum(db.case([(AnalysisResult.is_relevant, 1)], else_=0)).label('relevant')
        ).filter(AnalysisResult.post_time >= thirty_days_ago)\
         .group_by(cast(AnalysisResult.post_time, Date))\
         .order_by(cast(AnalysisResult.post_time, Date)).all()

        time_data = [
            {
                'date': item[0].isoformat(),
                'total': item[1],
                'relevant': item[2] or 0,
                'relevance_rate': round((item[2] or 0) / item[1] * 100, 2) if item[1] > 0 else 0
            }
            for item in time_stats
        ]

        return jsonify({
            "success": True,
            "data": {
                "summary": {
                    "total_posts": total_posts,
                    "relevant_posts": relevant_posts,
                    "relevance_rate": round(relevant_posts / total_posts * 100, 2) if total_posts > 0 else 0
                },
                "platforms": platform_data,
                "accounts": account_data,
                "time_trend": time_data
            }
        })
    except Exception as e:
        logger.error(f"获取分析数据摘要时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"获取数据失败: {str(e)}"}), 500

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """系统初始化设置页面"""
    # 检查系统是否已初始化
    if is_system_initialized():
        flash('系统已初始化')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 创建管理员账号
        admin_username = request.form.get('admin_username', 'admin')
        admin_password = request.form.get('admin_password')

        if not admin_password or len(admin_password) < 6:
            flash('管理员密码不能为空且长度不能少于6个字符')
            return render_template('setup.html')

        # 保存LLM配置
        llm_api_key = request.form.get('llm_api_key')
        llm_api_model = request.form.get('llm_api_model', 'gpt-3.5-turbo')
        llm_api_base = request.form.get('llm_api_base', 'https://api.openai.com/v1')

        if not llm_api_key:
            flash('LLM API密钥不能为空')
            return render_template('setup.html')

        try:
            # 创建管理员用户
            user = User(username=admin_username)
            user.set_password(admin_password)
            db.session.add(user)

            # 保存LLM配置
            save_llm_config(
                api_key=llm_api_key,
                api_model=llm_api_model,
                api_base=llm_api_base
            )

            db.session.commit()
            logger.info("系统初始化成功")

            flash('系统初始化成功，请使用创建的管理员账号登录')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"系统初始化失败: {str(e)}")
            flash(f'系统初始化失败: {str(e)}')

    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 检查系统是否已初始化
    if not is_system_initialized():
        return redirect(url_for('setup'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            logger.info(f"用户 {username} 登录成功")
            return redirect(url_for('index'))

        logger.warning(f"用户 {username} 登录失败")
        flash('用户名或密码错误')

    return render_template('login.html')

@app.route('/logout')
def logout():
    username = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            username = user.username

    session.pop('user_id', None)

    if username:
        logger.info(f"用户 {username} 已登出")

    return redirect(url_for('login'))

@app.route('/config', methods=['GET', 'POST'])
def config():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    config_path = 'config/social-networks.yml'

    if request.method == 'POST':
        try:
            config_data = yaml.safe_load(request.form.get('config'))
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, allow_unicode=True)
            logger.info("配置文件已保存")
            flash('配置已成功保存')

            # 导入账号到数据库
            import_accounts_from_yaml()
        except Exception as e:
            logger.error(f"保存配置文件时出错: {str(e)}")
            flash(f'保存配置时出错: {str(e)}')

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()
    except Exception as e:
        logger.error(f"读取配置文件时出错: {str(e)}")
        config_content = f"# 读取配置文件时出错: {str(e)}"

    return render_template('config.html', config=config_content)

@app.route('/results')
def results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    per_page = 20

    # 过滤条件
    account_id = request.args.get('account_id')
    is_relevant = request.args.get('is_relevant')

    query = AnalysisResult.query

    if account_id:
        query = query.filter_by(account_id=account_id)

    if is_relevant is not None:
        is_relevant_bool = is_relevant.lower() == 'true'
        query = query.filter_by(is_relevant=is_relevant_bool)

    results = query.order_by(AnalysisResult.created_at.desc()).paginate(page=page, per_page=per_page)

    # 获取所有账号，用于过滤
    accounts = SocialAccount.query.all()

    return render_template('results.html', results=results, accounts=accounts)

@app.route('/api/results')
def api_results():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    # 获取特定ID的结果
    result_id = request.args.get('id')
    if result_id:
        result = AnalysisResult.query.get(result_id)
        if result:
            return jsonify([result.to_dict()])
        else:
            return jsonify([])

    # 过滤条件
    account_id = request.args.get('account_id')
    is_relevant = request.args.get('is_relevant')

    query = AnalysisResult.query

    if account_id:
        query = query.filter_by(account_id=account_id)

    if is_relevant is not None:
        is_relevant_bool = is_relevant.lower() == 'true'
        query = query.filter_by(is_relevant=is_relevant_bool)

    results = query.order_by(AnalysisResult.created_at.desc()).limit(100).all()
    return jsonify([result.to_dict() for result in results])

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_password':
            # 更新密码
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            user = User.query.get(session['user_id'])

            if not user.check_password(current_password):
                flash('当前密码不正确')
            elif new_password != confirm_password:
                flash('新密码和确认密码不匹配')
            elif len(new_password) < 6:
                flash('新密码长度不能少于6个字符')
            else:
                user.set_password(new_password)
                db.session.commit()
                logger.info(f"用户 {user.username} 已更新密码")
                flash('密码已成功更新')

        elif action == 'update_apprise':
            # 更新Apprise设置
            apprise_urls = request.form.get('apprise_urls')
            set_config('APPRISE_URLS', apprise_urls, description='Apprise推送URLs')
            logger.info("Apprise URLs已更新")
            flash('推送设置已更新')

        elif action == 'update_auto_reply':
            # 更新自动回复设置
            enable_auto_reply = request.form.get('enable_auto_reply') == 'on'
            auto_reply_prompt = request.form.get('auto_reply_prompt')

            set_config('ENABLE_AUTO_REPLY', 'true' if enable_auto_reply else 'false', description='是否启用自动回复')
            if auto_reply_prompt:
                set_config('AUTO_REPLY_PROMPT', auto_reply_prompt, description='自动回复提示词模板')

            logger.info("自动回复设置已更新")
            flash('自动回复设置已更新')

        elif action == 'update_proxy':
            # 更新代理设置
            http_proxy = request.form.get('http_proxy')
            set_config('HTTP_PROXY', http_proxy, description='HTTP代理')
            logger.info("代理设置已更新")
            flash('代理设置已更新')

    # 获取系统配置
    config = get_system_config()

    return render_template('settings.html',
                          apprise_urls=config.get('APPRISE_URLS', ''),
                          enable_auto_reply=config.get('ENABLE_AUTO_REPLY', 'false').lower() == 'true',
                          auto_reply_prompt=config.get('AUTO_REPLY_PROMPT', ''),
                          http_proxy=config.get('HTTP_PROXY', ''))

@app.route('/system_config', methods=['GET', 'POST'])
def system_config():
    """系统配置管理页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # 更新LLM配置
        llm_api_key = request.form.get('llm_api_key')
        llm_api_model = request.form.get('llm_api_model')
        llm_api_base = request.form.get('llm_api_base')

        # 如果提供了新的API密钥（不是占位符），则更新
        if llm_api_key and not llm_api_key.startswith('******'):
            set_config('LLM_API_KEY', llm_api_key, is_secret=True, description='LLM API密钥')

        if llm_api_model:
            set_config('LLM_API_MODEL', llm_api_model, description='LLM API模型')

        if llm_api_base:
            set_config('LLM_API_BASE', llm_api_base, description='LLM API基础URL')

        # 更新Twitter配置
        twitter_username = request.form.get('twitter_username')
        twitter_password = request.form.get('twitter_password')
        twitter_session = request.form.get('twitter_session')

        if twitter_username:
            set_config('TWITTER_USERNAME', twitter_username, description='Twitter用户名')

        # 如果提供了新的密码（不是占位符），则更新
        if twitter_password and not twitter_password.startswith('******'):
            set_config('TWITTER_PASSWORD', twitter_password, is_secret=True, description='Twitter密码')

        # 如果提供了新的会话数据（不是占位符），则更新
        if twitter_session and not twitter_session.startswith('******'):
            set_config('TWITTER_SESSION', twitter_session, is_secret=True, description='Twitter会话数据')

        # 更新定时任务配置
        scheduler_interval = request.form.get('scheduler_interval')
        if scheduler_interval:
            set_config('SCHEDULER_INTERVAL_MINUTES', scheduler_interval, description='定时任务执行间隔（分钟）')

        logger.info("系统配置已更新")
        flash('系统配置已更新')
        return redirect(url_for('system_config'))

    # 获取当前配置
    config = get_system_config()

    return render_template('system_config.html', config=config)

# 账号管理路由
@app.route('/accounts')
def accounts():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    accounts = SocialAccount.query.all()
    return render_template('accounts.html', accounts=accounts)

@app.route('/accounts/add', methods=['GET', 'POST'])
def add_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        account_type = request.form.get('type')
        account_id = request.form.get('account_id')
        tag = request.form.get('tag', 'all')
        enable_auto_reply = request.form.get('enable_auto_reply') == 'on'
        prompt_template = request.form.get('prompt_template')
        auto_reply_template = request.form.get('auto_reply_template')

        if not account_type or not account_id:
            flash('平台类型和账号ID不能为空')
            return redirect(url_for('add_account'))

        # 检查账号是否已存在
        existing = SocialAccount.query.filter_by(
            type=account_type,
            account_id=account_id
        ).first()

        if existing:
            flash('该账号已存在')
            return redirect(url_for('add_account'))

        # 创建新账号
        new_account = SocialAccount(
            type=account_type,
            account_id=account_id,
            tag=tag,
            enable_auto_reply=enable_auto_reply,
            prompt_template=prompt_template,
            auto_reply_template=auto_reply_template
        )

        db.session.add(new_account)
        db.session.commit()

        # 同步到配置文件
        sync_accounts_to_yaml()

        logger.info(f"已添加新账号: {account_type}:{account_id}")
        flash('账号已成功添加')
        return redirect(url_for('accounts'))

    # 获取默认提示词模板
    default_prompt = get_default_prompt_template('twitter')

    return render_template('account_form.html',
                          account=None,
                          default_prompt=default_prompt,
                          action='add')

@app.route('/accounts/edit/<int:id>', methods=['GET', 'POST'])
def edit_account(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    account = SocialAccount.query.get_or_404(id)

    if request.method == 'POST':
        account.type = request.form.get('type')
        account.account_id = request.form.get('account_id')
        account.tag = request.form.get('tag', 'all')
        account.enable_auto_reply = request.form.get('enable_auto_reply') == 'on'
        account.prompt_template = request.form.get('prompt_template')
        account.auto_reply_template = request.form.get('auto_reply_template')

        db.session.commit()

        # 同步到配置文件
        sync_accounts_to_yaml()

        logger.info(f"已更新账号: {account.type}:{account.account_id}")
        flash('账号已成功更新')
        return redirect(url_for('accounts'))

    # 获取默认提示词模板
    default_prompt = get_default_prompt_template(account.type)

    return render_template('account_form.html',
                          account=account,
                          default_prompt=default_prompt,
                          action='edit')

@app.route('/accounts/delete/<int:id>', methods=['POST'])
def delete_account(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    account = SocialAccount.query.get_or_404(id)

    db.session.delete(account)
    db.session.commit()

    # 同步到配置文件
    sync_accounts_to_yaml()

    logger.info(f"已删除账号: {account.type}:{account.account_id}")
    flash('账号已成功删除')
    return redirect(url_for('accounts'))

@app.route('/api/accounts')
def api_accounts():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    accounts = SocialAccount.query.all()
    return jsonify([account.to_dict() for account in accounts])

# 初始化数据库
def init_db():
    """
    初始化数据库，创建表结构，导入配置
    """
    logger.info("开始初始化数据库...")

    with app.app_context():
        # 创建所有表
        try:
            db.create_all()
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"创建数据库表时出错: {str(e)}")
            raise

        # 确保配置目录存在
        config_dir = os.path.join(os.getcwd(), 'config')
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir)
                logger.info(f"创建配置目录: {config_dir}")
            except Exception as e:
                logger.error(f"创建配置目录时出错: {str(e)}")

        # 确保配置文件存在
        config_file = os.path.join(config_dir, 'social-networks.yml')
        if not os.path.exists(config_file):
            try:
                # 创建默认配置文件
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write("""social_networks:
  - type: twitter
    socialNetworkId: elonmusk
    prompt: |
      请分析以下推文内容，判断是否与科技、创新或太空探索相关。

      内容: {content}

      请以JSON格式返回分析结果，包含以下字段：
      1. is_relevant: 是否相关 (1表示相关，0表示不相关)
      2. analytical_briefing: 如果相关，请提供简要分析（不超过200字）；如果不相关，请简述原因
    tag: tech
    enableAutoReply: false
""")
                logger.info(f"创建默认配置文件: {config_file}")
            except Exception as e:
                logger.error(f"创建默认配置文件时出错: {str(e)}")

        # 导入配置文件中的账号
        try:
            import_accounts_from_yaml()
            logger.info("从配置文件导入账号成功")
        except Exception as e:
            logger.error(f"导入账号时出错: {str(e)}")

        # 从环境变量导入系统配置
        try:
            # 导入LLM配置
            llm_api_key = os.getenv('LLM_API_KEY')
            if llm_api_key:
                set_config('LLM_API_KEY', llm_api_key, is_secret=True, description='LLM API密钥', update_env=False)

            llm_api_model = os.getenv('LLM_API_MODEL')
            if llm_api_model:
                set_config('LLM_API_MODEL', llm_api_model, description='LLM API模型', update_env=False)

            llm_api_base = os.getenv('LLM_API_BASE')
            if llm_api_base:
                set_config('LLM_API_BASE', llm_api_base, description='LLM API基础URL', update_env=False)

            # 导入Twitter配置
            twitter_username = os.getenv('TWITTER_USERNAME')
            if twitter_username:
                set_config('TWITTER_USERNAME', twitter_username, description='Twitter用户名', update_env=False)

            twitter_password = os.getenv('TWITTER_PASSWORD')
            if twitter_password:
                set_config('TWITTER_PASSWORD', twitter_password, is_secret=True, description='Twitter密码', update_env=False)

            twitter_session = os.getenv('TWITTER_SESSION')
            if twitter_session:
                set_config('TWITTER_SESSION', twitter_session, is_secret=True, description='Twitter会话数据', update_env=False)

            # 导入其他配置
            scheduler_interval = os.getenv('SCHEDULER_INTERVAL_MINUTES')
            if scheduler_interval:
                set_config('SCHEDULER_INTERVAL_MINUTES', scheduler_interval, description='定时任务执行间隔（分钟）', update_env=False)

            http_proxy = os.getenv('HTTP_PROXY')
            if http_proxy:
                set_config('HTTP_PROXY', http_proxy, description='HTTP代理', update_env=False)

            apprise_urls = os.getenv('APPRISE_URLS')
            if apprise_urls:
                set_config('APPRISE_URLS', apprise_urls, description='Apprise推送URLs', update_env=False)

            enable_auto_reply = os.getenv('ENABLE_AUTO_REPLY')
            if enable_auto_reply:
                set_config('ENABLE_AUTO_REPLY', enable_auto_reply, description='是否启用自动回复', update_env=False)

            auto_reply_prompt = os.getenv('AUTO_REPLY_PROMPT')
            if auto_reply_prompt:
                set_config('AUTO_REPLY_PROMPT', auto_reply_prompt, description='自动回复提示词模板', update_env=False)

            logger.info("从环境变量导入系统配置成功")
        except Exception as e:
            logger.error(f"导入系统配置时出错: {str(e)}")

        # 创建默认管理员用户
        try:
            if create_default_admin():
                logger.info("创建默认管理员用户成功")
            else:
                logger.debug("未创建默认管理员用户")
        except Exception as e:
            logger.error(f"创建默认管理员用户时出错: {str(e)}")

    logger.info("数据库初始化完成")

# API用于保存分析结果
@app.route('/api/save_result', methods=['POST'])
def save_result():
    data = request.json

    try:
        result = AnalysisResult(
            social_network=data['social_network'],
            account_id=data['account_id'],
            post_id=data['post_id'],
            post_time=datetime.fromisoformat(data['post_time']),
            content=data['content'],
            analysis=data['analysis'],
            is_relevant=data['is_relevant']
        )

        db.session.add(result)
        db.session.commit()

        return jsonify({'success': True, 'id': result.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 数据导出功能
@app.route('/export_data')
def export_data():
    """导出所有数据为JSON文件"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        # 导出监控的账号数据（这是最重要的配置）
        accounts = SocialAccount.query.all()
        account_data = [account.to_dict() for account in accounts]

        # 导出关键系统配置
        # 1. 获取所有配置
        all_configs = SystemConfig.query.all()

        # 2. 分类配置
        llm_configs = []
        twitter_configs = []
        notification_configs = []
        other_configs = []

        for config in all_configs:
            # 创建配置项基本信息
            config_item = {
                'key': config.key,
                'description': config.description
            }

            # 对敏感信息进行特殊处理
            if config.is_secret:
                # 标记敏感信息已设置，但不导出实际值
                config_item['value'] = '******' if config.value else ''
                config_item['is_set'] = bool(config.value)
            else:
                config_item['value'] = config.value

            # 根据配置类型分类
            if config.key.startswith('LLM_'):
                llm_configs.append(config_item)
            elif config.key.startswith('TWITTER_'):
                twitter_configs.append(config_item)
            elif config.key in ['APPRISE_URLS', 'ENABLE_AUTO_REPLY', 'AUTO_REPLY_PROMPT']:
                notification_configs.append(config_item)
            else:
                other_configs.append(config_item)

        # 获取通知服务配置
        notification_services = []
        apprise_urls = get_config('APPRISE_URLS', '')
        if apprise_urls:
            for url in apprise_urls.split(','):
                url = url.strip()
                if url:
                    # 提取通知服务类型和基本信息
                    parts = url.split('://')
                    if len(parts) > 1:
                        service_type = parts[0]
                        # 提取服务的基本信息，但隐藏敏感细节
                        service_info = parts[1].split('/')[0] if '/' in parts[1] else '***'
                        notification_services.append({
                            'type': service_type,
                            'info': service_info,
                            'full_url': f"{service_type}://***"
                        })

        # 创建导出数据，专注于关键配置
        export_data = {
            'accounts': account_data,  # 监控的账号数据
            'configs': {
                'llm': llm_configs,  # LLM API 配置
                'twitter': twitter_configs,  # Twitter 账号配置
                'notification': notification_configs,  # 通知系统配置
                'other': other_configs  # 其他配置
            },
            'notification_services': notification_services,  # 通知服务详情
            'export_time': datetime.now(timezone.utc).isoformat(),
            'version': '1.1',  # 更新版本号
            'export_type': 'essential'  # 标记为核心配置导出
        }

        # 创建响应
        response = jsonify(export_data)
        response.headers['Content-Disposition'] = f'attachment; filename=tweetanalyst_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        return response
    except Exception as e:
        logger.error(f"导出数据时出错: {str(e)}")
        flash(f"导出数据失败: {str(e)}", 'danger')
        return redirect(url_for('index'))

# 数据导入功能
@app.route('/import_data', methods=['GET', 'POST'])
def import_data():
    """导入数据"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # 检查是否有文件上传
        if 'import_file' not in request.files:
            flash('没有选择文件', 'danger')
            return redirect(request.url)

        file = request.files['import_file']

        # 检查文件名
        if file.filename == '':
            flash('没有选择文件', 'danger')
            return redirect(request.url)

        # 检查文件类型
        if not file.filename.endswith('.json'):
            flash('只支持导入JSON文件', 'danger')
            return redirect(request.url)

        try:
            # 读取并解析JSON数据
            import_data = json.loads(file.read().decode('utf-8'))

            # 验证数据格式
            if 'accounts' not in import_data or 'version' not in import_data:
                flash('导入文件格式不正确，缺少必要的数据字段', 'danger')
                return redirect(request.url)

            # 检测导出文件版本
            version = import_data.get('version', '1.0')
            is_essential_export = import_data.get('export_type') == 'essential'

            logger.info(f"导入数据版本: {version}, 类型: {'核心配置' if is_essential_export else '完整数据'}")

            # 导入账号数据
            if request.form.get('import_accounts') == 'on':
                imported_accounts = 0
                for account_data in import_data['accounts']:
                    # 检查账号是否已存在
                    existing = SocialAccount.query.filter_by(
                        type=account_data['type'],
                        account_id=account_data['account_id']
                    ).first()

                    if not existing:
                        # 创建新账号
                        new_account = SocialAccount(
                            type=account_data['type'],
                            account_id=account_data['account_id'],
                            tag=account_data.get('tag', 'all'),
                            enable_auto_reply=account_data.get('enable_auto_reply', False),
                            prompt_template=account_data.get('prompt_template', '')
                        )
                        db.session.add(new_account)
                        imported_accounts += 1

                if imported_accounts > 0:
                    db.session.commit()
                    # 同步到配置文件
                    sync_accounts_to_yaml()
                    flash(f'成功导入 {imported_accounts} 个账号', 'success')

            # 导入分析结果数据
            if request.form.get('import_results') == 'on':
                imported_results = 0
                for result_data in import_data['results']:
                    # 检查结果是否已存在
                    existing = AnalysisResult.query.filter_by(
                        social_network=result_data['social_network'],
                        account_id=result_data['account_id'],
                        post_id=result_data['post_id']
                    ).first()

                    if not existing:
                        # 创建新结果
                        new_result = AnalysisResult(
                            social_network=result_data['social_network'],
                            account_id=result_data['account_id'],
                            post_id=result_data['post_id'],
                            post_time=datetime.fromisoformat(result_data['post_time']),
                            content=result_data['content'],
                            analysis=result_data['analysis'],
                            is_relevant=result_data['is_relevant']
                        )
                        db.session.add(new_result)
                        imported_results += 1

                if imported_results > 0:
                    db.session.commit()
                    flash(f'成功导入 {imported_results} 条分析结果', 'success')

            # 导入系统配置数据
            if request.form.get('import_configs') == 'on':
                imported_configs = 0

                # 处理不同版本的配置格式
                if is_essential_export:
                    # 新版本格式（分类配置）
                    config_categories = import_data['configs']

                    # 导入LLM配置
                    for config in config_categories.get('llm', []):
                        if not config.get('is_set', False) and config.get('value', '') == '******':
                            # 跳过敏感信息，这些信息在导出时被屏蔽
                            continue

                        set_config(
                            config['key'],
                            config['value'],
                            is_secret=config.get('value') == '******',
                            description=config.get('description', ''),
                            update_env=False
                        )
                        imported_configs += 1

                    # 导入Twitter配置
                    for config in config_categories.get('twitter', []):
                        if not config.get('is_set', False) and config.get('value', '') == '******':
                            # 跳过敏感信息，这些信息在导出时被屏蔽
                            continue

                        set_config(
                            config['key'],
                            config['value'],
                            is_secret=config.get('value') == '******',
                            description=config.get('description', ''),
                            update_env=False
                        )
                        imported_configs += 1

                    # 导入通知配置
                    for config in config_categories.get('notification', []):
                        if not config.get('is_set', False) and config.get('value', '') == '******':
                            # 跳过敏感信息，这些信息在导出时被屏蔽
                            continue

                        set_config(
                            config['key'],
                            config['value'],
                            is_secret=config.get('value') == '******',
                            description=config.get('description', ''),
                            update_env=False
                        )
                        imported_configs += 1

                    # 导入其他配置
                    for config in config_categories.get('other', []):
                        if not config.get('is_set', False) and config.get('value', '') == '******':
                            # 跳过敏感信息，这些信息在导出时被屏蔽
                            continue

                        set_config(
                            config['key'],
                            config['value'],
                            is_secret=config.get('value') == '******',
                            description=config.get('description', ''),
                            update_env=False
                        )
                        imported_configs += 1
                else:
                    # 旧版本格式（平铺配置）
                    for config_data in import_data.get('configs', []):
                        # 设置配置
                        set_config(
                            config_data['key'],
                            config_data['value'],
                            is_secret=False,
                            description=config_data.get('description', ''),
                            update_env=False
                        )
                        imported_configs += 1

                if imported_configs > 0:
                    flash(f'成功导入 {imported_configs} 项系统配置', 'success')

            # 导入通知配置（如果存在）
            if request.form.get('import_notifications') == 'on':
                notification_imported = False

                # 处理不同版本的通知配置
                if is_essential_export:
                    # 新版本格式
                    if 'notification_services' in import_data:
                        # 注意：通知URL在导出时已被屏蔽，这里只提示用户
                        service_types = [service['type'] for service in import_data['notification_services']]
                        if service_types:
                            flash(f'检测到通知服务配置: {", ".join(service_types)}。请在系统配置中手动设置完整的通知URL。', 'info')
                            notification_imported = True
                else:
                    # 旧版本格式
                    if 'notifications' in import_data:
                        # 旧版本通知配置处理
                        notification_imported = True

                # 导入自动回复配置（适用于所有版本）
                auto_reply_imported = False

                # 新版本格式
                if is_essential_export:
                    # 从分类配置中查找自动回复设置
                    config_categories = import_data['configs']
                    for config in config_categories.get('notification', []):
                        if config['key'] == 'ENABLE_AUTO_REPLY':
                            set_config(
                                'ENABLE_AUTO_REPLY',
                                config['value'],
                                description='是否启用自动回复',
                                update_env=False
                            )
                            auto_reply_imported = True
                # 旧版本格式
                elif 'auto_reply' in import_data:
                    auto_reply = import_data['auto_reply']
                    if 'enabled' in auto_reply:
                        set_config(
                            'ENABLE_AUTO_REPLY',
                            'true' if auto_reply['enabled'] else 'false',
                            description='是否启用自动回复',
                            update_env=False
                        )
                        auto_reply_imported = True

                if notification_imported or auto_reply_imported:
                    flash('成功导入通知和自动回复配置', 'success')

            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"导入数据时出错: {str(e)}")
            flash(f"导入数据失败: {str(e)}", 'danger')
            return redirect(request.url)

    # GET 请求，显示导入表单
    return render_template('import_data.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
