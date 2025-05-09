import os
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from sqlalchemy import func, cast, Date
from utils.logger import get_logger
import yaml

# 导入模型和服务
from models import db
from models.user import User
from models.social_account import SocialAccount
from models.analysis_result import AnalysisResult
from models.system_config import SystemConfig
from models.system_state import SystemState
from services.config_service import get_config, set_config, get_system_config, load_configs_to_env, get_default_prompt_template
from services.state_service import DBStateStore
from services.test_service import check_system_status
from utils.yaml_utils import sync_accounts_to_yaml, import_accounts_from_yaml

# 导入API模块
from api import api_blueprint

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

# 初始化数据库
db.init_app(app)

# 注册API蓝图
app.register_blueprint(api_blueprint)

# 创建Redis替代适配器
redis_client = DBStateStore()

# 辅助函数

# 系统初始化和配置函数

def is_system_initialized():
    """检查系统是否已初始化"""
    try:
        logger.info("检查系统是否已初始化")

        # 检查是否有管理员用户
        try:
            admin_exists = User.query.first() is not None
            logger.info(f"管理员用户存在: {admin_exists}")
        except Exception as e:
            logger.error(f"检查管理员用户时出错: {str(e)}")
            admin_exists = False

        # 检查是否有LLM API密钥
        try:
            llm_api_key = get_config('LLM_API_KEY')
            logger.info(f"LLM API密钥存在: {bool(llm_api_key)}")
        except Exception as e:
            logger.error(f"检查LLM API密钥时出错: {str(e)}")
            llm_api_key = None

        initialized = admin_exists and llm_api_key
        logger.info(f"系统初始化状态: {initialized}")
        return initialized
    except Exception as e:
        logger.error(f"检查系统初始化状态时出错: {str(e)}")
        return False

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

# 配置辅助函数已移动到services/config_service.py

# 状态存储类已移动到services/state_service.py

# 创建Redis替代适配器
redis_client = DBStateStore()

# 账号和提示词模板函数已移动到utils/yaml_utils.py和services/config_service.py

# 导入账号函数已移动到utils/yaml_utils.py

# 路由
@app.route('/')
def index():
    try:
        logger.info("访问首页，检查初始化状态")

        # 检查是否是首次登录
        is_first_login = os.getenv('FIRST_LOGIN', 'true').lower() == 'true'
        logger.info(f"FIRST_LOGIN 环境变量值: {is_first_login}")

        # 如果是首次登录，强制进行初始化
        if is_first_login:
            logger.info("检测到首次登录，准备初始化系统")

            # 初始化数据库
            try:
                logger.info("开始初始化数据库")
                init_db()
                logger.info("数据库初始化成功")
            except Exception as e:
                logger.error(f"数据库初始化失败: {str(e)}")
                # 继续执行，让用户通过Web界面完成初始化

            # 设置环境变量，标记已经不是首次登录
            os.environ['FIRST_LOGIN'] = 'false'
            logger.info("已将 FIRST_LOGIN 环境变量设置为 false")

            # 尝试更新 .env 文件
            try:
                db_path = os.environ.get('DATABASE_PATH', 'instance/tweetanalyst.db')
                env_dir = os.path.dirname(db_path)
                env_file = os.path.join(env_dir, '.env')

                logger.info(f"尝试更新环境变量文件: {env_file}")

                # 确保目录存在
                os.makedirs(env_dir, exist_ok=True)

                env_lines = []

                # 读取现有.env文件
                if os.path.exists(env_file):
                    with open(env_file, 'r') as f:
                        env_lines = f.readlines()
                    logger.info(f"已读取现有.env文件，包含 {len(env_lines)} 行")
                else:
                    logger.info(".env文件不存在，将创建新文件")

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
                logger.info("已成功更新.env文件")
            except Exception as e:
                logger.error(f"更新环境变量文件时出错: {str(e)}")
                # 继续执行，不影响初始化流程

            logger.info("重定向到初始化页面")
            return redirect(url_for('setup'))

        # 检查系统是否已初始化
        initialized = is_system_initialized()
        logger.info(f"系统初始化状态: {initialized}")

        if not initialized:
            logger.info("系统未初始化，重定向到初始化页面")
            return redirect(url_for('setup'))

        if 'user_id' not in session:
            logger.info("用户未登录，重定向到登录页面")
            return redirect(url_for('login'))

        logger.info("用户已登录，显示首页")
        # 继续正常的首页逻辑
    except Exception as e:
        logger.error(f"首页处理过程中出错: {str(e)}")
        # 出现错误时，尝试重定向到初始化页面
        return redirect(url_for('setup'))

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

# 测试API端点已移动到api/test.py

# 通知和分析API端点已移动到api/analytics.py

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """系统初始化设置页面"""
    try:
        logger.info("访问初始化页面")

        # 确保数据库已初始化
        try:
            logger.info("确保数据库已初始化")
            # 检查数据库连接 - 使用SQLAlchemy 2.0兼容的方式
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1")).fetchall()
            logger.info("数据库连接正常")
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            # 尝试初始化数据库
            try:
                logger.info("尝试初始化数据库")
                init_db()
                logger.info("数据库初始化成功")
            except Exception as e:
                logger.error(f"数据库初始化失败: {str(e)}")
                error_msg = f"数据库初始化失败: {str(e)}"
                return render_template('setup.html', error=error_msg)

        # 检查系统是否已初始化
        initialized = is_system_initialized()
        logger.info(f"系统初始化状态: {initialized}")

        if initialized and request.method == 'GET':
            logger.info("系统已初始化，重定向到首页")
            flash('系统已初始化', 'info')
            return redirect(url_for('index'))

        if request.method == 'POST':
            logger.info("处理初始化表单提交")

            try:
                # 创建管理员账号
                admin_username = request.form.get('admin_username', 'admin')
                admin_password = request.form.get('admin_password')

                logger.info(f"创建管理员用户: {admin_username}")

                if not admin_password or len(admin_password) < 6:
                    logger.warning("管理员密码不能为空且长度不能少于6个字符")
                    flash('管理员密码不能为空且长度不能少于6个字符', 'danger')
                    return render_template('setup.html')

                # 保存LLM配置
                llm_api_key = request.form.get('llm_api_key')
                llm_api_model = request.form.get('llm_api_model', 'grok-2-latest')
                llm_api_base = request.form.get('llm_api_base', 'https://api.x.ai/v1')

                if not llm_api_key:
                    logger.warning("LLM API密钥不能为空")
                    flash('LLM API密钥不能为空', 'danger')
                    return render_template('setup.html')

                # 创建管理员用户
                user = User(username=admin_username)
                user.set_password(admin_password)
                db.session.add(user)
                logger.info(f"已创建用户: {admin_username}")

                # 保存LLM配置
                logger.info("保存LLM配置")
                set_config('LLM_API_KEY', llm_api_key, is_secret=True, description='LLM API密钥')
                set_config('LLM_API_MODEL', llm_api_model, description='LLM API模型')
                set_config('LLM_API_BASE', llm_api_base, description='LLM API基础URL')

                # 设置环境变量，标记已经不是首次登录
                os.environ['FIRST_LOGIN'] = 'false'
                logger.info("已将 FIRST_LOGIN 环境变量设置为 false")

                # 提交更改
                db.session.commit()
                logger.info("系统初始化成功")

                flash('系统初始化成功，请使用创建的管理员账号登录', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                logger.error(f"系统初始化失败: {str(e)}")
                flash(f'系统初始化失败: {str(e)}', 'danger')
                return render_template('setup.html', error=str(e))

        logger.info("显示初始化页面")
        return render_template('setup.html')
    except Exception as e:
        logger.error(f"初始化页面处理过程中出错: {str(e)}")
        return render_template('setup.html', error=str(e))

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

# 分析结果API端点已移动到api/analytics.py

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """旧的设置页面，重定向到新的统一设置页面"""
    # 记录重定向日志，帮助跟踪旧路由的使用情况
    logger.info("访问旧的设置页面，重定向到统一设置中心")
    return redirect(url_for('unified_settings'))

@app.route('/unified_settings')
def unified_settings():
    """统一设置页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 获取系统配置
    config = get_system_config()

    return render_template('unified_settings.html',
                          config=config,
                          apprise_urls=config.get('APPRISE_URLS', ''),
                          enable_auto_reply=config.get('ENABLE_AUTO_REPLY', 'false').lower() == 'true',
                          auto_reply_prompt=config.get('AUTO_REPLY_PROMPT', ''),
                          http_proxy=config.get('HTTP_PROXY', ''))

@app.route('/system_config', methods=['GET', 'POST'])
def system_config():
    """旧的系统配置页面，重定向到新的统一设置页面"""
    # 记录重定向日志，帮助跟踪旧路由的使用情况
    logger.info("访问旧的系统配置页面，重定向到统一设置中心")

    # 如果是POST请求，记录日志并提示用户
    if request.method == 'POST':
        logger.warning("尝试通过旧的系统配置页面提交表单，已重定向到统一设置中心")
        flash('系统已升级，请使用新的统一设置中心进行配置', 'warning')

    # 重定向到新的统一设置页面
    return redirect(url_for('unified_settings'))

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

# 账号API端点已移动到api/accounts.py

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

# 保存分析结果的API端点已移动到api/analytics.py

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
    # 加载数据库中的配置到环境变量
    load_configs_to_env()
    app.run(debug=True, host='0.0.0.0', port=5000)
