import os
import json
from datetime import datetime, timedelta, timezone

# 先导入基础模块
from utils.logger import get_logger
import yaml

# 创建日志记录器
logger = get_logger('web_app')

# 在导入其他模块之前应用SSL修复
try:
    from utils.ssl_fix import apply_ssl_fixes
    apply_ssl_fixes()
    logger.info("✅ Web应用SSL连接修复已应用")
except Exception as e:
    logger.warning(f"⚠️ Web应用SSL修复应用失败: {str(e)}")

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, cast, Date

# 导入模型和服务
from models import db
from models.user import User
from models.social_account import SocialAccount
from models.analysis_result import AnalysisResult
from models.system_config import SystemConfig
from models.system_state import SystemState
from models.ai_provider import AIProvider
from services.config_service import (
    get_config, set_config, get_system_config,
    load_configs_to_env, get_default_prompt_template,
    init_config as service_init_config
)
from services.state_service import DBStateStore
from services.test_service import check_system_status
from utils.yaml_utils import sync_accounts_to_yaml, import_accounts_from_yaml

# 导入API模块 - 延迟导入，避免循环导入问题
# from api import api_blueprint

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev_key_please_change')

# 初始化CSRF保护
csrf = CSRFProtect(app)

# 简单粗暴：直接从环境变量获取数据库路径，Docker环境已强制设置
db_path = os.getenv('DATABASE_PATH', '/data/tweetAnalyst.db')
# 确保路径是绝对路径
if not os.path.isabs(db_path):
    db_path = os.path.join(os.getcwd(), db_path)
# 确保目录存在
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Docker启动脚本已经处理了数据库文件清理，这里直接使用环境变量指定的路径

# 设置数据库URI
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

logger.info(f"数据库路径: {db_path}")

# 初始化数据库
db.init_app(app)

# 添加模板过滤器
@app.template_filter('format_number')
def format_number(num):
    """格式化数字显示"""
    if num is None or num == 0:
        return '0'

    try:
        num = int(num)
        if num < 1000:
            return str(num)
        elif num < 10000:
            return f"{num/1000:.1f}K"
        elif num < 1000000:
            return f"{num/10000:.1f}万"
        else:
            return f"{num/1000000:.1f}M"
    except (ValueError, TypeError):
        return str(num)

# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 延迟导入API模块，避免循环导入问题
from api import api_blueprint
# 注册API蓝图
app.register_blueprint(api_blueprint)

# 导入推送通知路由
try:
    from routes.push_notifications import push_notifications_bp
    # 注册推送通知蓝图
    app.register_blueprint(push_notifications_bp)
    logger.info("已注册推送通知蓝图")
except ImportError as e:
    logger.warning(f"导入推送通知蓝图失败: {str(e)}")
except Exception as e:
    logger.error(f"注册推送通知蓝图时出错: {str(e)}")

# 导入AI设置路由
try:
    from routes.ai_settings import ai_settings_bp
    # 注册AI设置蓝图
    app.register_blueprint(ai_settings_bp)
    logger.info("已注册AI设置蓝图")
except ImportError as e:
    logger.warning(f"导入AI设置蓝图失败: {str(e)}")
except Exception as e:
    logger.error(f"注册AI设置蓝图时出错: {str(e)}")



# 初始化AI轮询服务
try:
    from services.ai_polling_service import ai_polling_service
    # 启动AI轮询服务
    ai_polling_enabled = get_config('AI_POLLING_ENABLED', 'true').lower() == 'true'
    if ai_polling_enabled:
        if ai_polling_service.start():
            logger.info("已启动AI轮询服务")
        else:
            logger.info("AI轮询服务启动失败或已在运行")
    else:
        logger.info("AI轮询服务已禁用")
except ImportError as e:
    logger.warning(f"导入AI轮询服务失败: {str(e)}")
except Exception as e:
    logger.error(f"初始化AI轮询服务时出错: {str(e)}")

# 添加响应头，防止缓存
@app.after_request
def add_header(response):
    """添加响应头，防止缓存"""
    # 对所有响应添加禁止缓存的头信息
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'

    # 对API响应特别处理
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

    return response

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
            # 不设置is_admin字段，使用默认值
            db.session.add(admin)
            db.session.commit()
            logger.info("已创建默认管理员用户: admin/admin123")
            return True
        except Exception as e:
            logger.error(f"创建默认管理员用户时出错: {str(e)}")
            db.session.rollback()
            return False

def create_default_ai_providers():
    """创建默认AI提供商（如果不存在）"""
    try:
        # 确保在应用上下文中运行
        with app.app_context():
            # 检查是否已存在AI提供商
            if AIProvider.query.first() is not None:
                logger.debug("已存在AI提供商，不创建默认提供商")
                return False

            # 从配置中获取API密钥和基础URL
            # 优先从环境变量获取，避免循环依赖
            api_key = os.environ.get('LLM_API_KEY', '')
            api_base = os.environ.get('LLM_API_BASE', 'https://api.openai.com/v1')
            api_model = os.environ.get('LLM_API_MODEL', 'gpt-4')

            # 如果环境变量中没有，尝试从配置服务获取
            if not api_key:
                try:
                    api_key = get_config('LLM_API_KEY', '')
                except:
                    pass

            if not api_base:
                try:
                    api_base = get_config('LLM_API_BASE', 'https://api.openai.com/v1')
                except:
                    pass

            if not api_model:
                try:
                    api_model = get_config('LLM_API_MODEL', 'gpt-4')
                except:
                    pass

            # 创建默认AI提供商
            default_provider = AIProvider(
                name="默认提供商",
                model=api_model,
                api_key=api_key,
                api_base=api_base,
                priority=0,
                is_active=True,
                supports_text=True,
                supports_image=False,
                supports_video=False,
                supports_gif=False
            )

            # 创建多模态AI提供商
            multimodal_provider = AIProvider(
                name="多模态提供商",
                model="gpt-4-vision-preview",
                api_key=api_key,
                api_base=api_base,
                priority=1,
                is_active=True,
                supports_text=True,
                supports_image=True,
                supports_video=False,
                supports_gif=True
            )

            db.session.add(default_provider)
            db.session.add(multimodal_provider)
            db.session.commit()

            logger.info("已创建默认AI提供商")
            return True
    except Exception as e:
        logger.error(f"创建默认AI提供商时出错: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return False

# 配置辅助函数已移动到services/config_service.py

# 状态存储类已移动到services/state_service.py

# 账号和提示词模板函数已移动到utils/yaml_utils.py和services/config_service.py

# 导入账号函数已移动到utils/yaml_utils.py

# 路由
@app.route('/')
def index():
    try:
        logger.info("访问首页，检查初始化状态")

        # 检查是否是首次登录
        first_login_env = os.getenv('FIRST_LOGIN', 'auto').lower()
        logger.info(f"FIRST_LOGIN 环境变量值: {first_login_env}")

        # 自动检测模式：检查数据库文件是否存在
        if first_login_env == 'auto':
            db_path = os.getenv('DATABASE_PATH', 'instance/tweetAnalyst.db')
            is_first_login = not os.path.exists(db_path) or os.path.getsize(db_path) == 0
            logger.info(f"自动检测首次登录状态: {is_first_login} (数据库路径: {db_path})")
        else:
            # 显式设置模式
            is_first_login = first_login_env == 'true'
            logger.info(f"使用环境变量设置的首次登录状态: {is_first_login}")

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

            # 尝试更新所有可能的.env文件位置
            try:
                # 1. 尝试更新项目根目录的.env文件
                root_env_file = os.path.join(os.getcwd(), '.env')

                # 2. 尝试更新数据目录的.env文件
                db_path = os.environ.get('DATABASE_PATH', 'instance/tweetAnalyst.db')
                data_dir = os.path.dirname(db_path)
                data_env_file = os.path.join(data_dir, '.env')

                # 更新所有可能的.env文件
                for env_file in [root_env_file, data_env_file]:
                    try:
                        # 确保目录存在
                        os.makedirs(os.path.dirname(env_file), exist_ok=True)

                        env_lines = []

                        # 读取现有.env文件
                        if os.path.exists(env_file):
                            with open(env_file, 'r') as f:
                                env_lines = f.readlines()
                            logger.info(f"已读取现有.env文件 {env_file}，包含 {len(env_lines)} 行")
                        else:
                            logger.info(f".env文件 {env_file} 不存在，将创建新文件")

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
                        logger.info(f"已成功更新.env文件: {env_file}")
                    except Exception as e:
                        logger.error(f"更新环境变量文件 {env_file} 时出错: {str(e)}")
                        # 继续尝试其他文件
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

@app.route('/system_status')
def system_status_page():
    """系统状态页面"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 获取系统状态信息
    from services.system_status_service import get_system_status
    system_status = get_system_status()

    return render_template('system_status.html', system_status=system_status)

@app.route('/test')
def test_page():
    """测试功能页面 - 重定向到系统状态页面"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 重定向到新的系统状态页面
    return redirect(url_for('system_status_page'))

@app.route('/test_timeline_debug')
def test_timeline_debug():
    """时间线任务调试测试页面"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('test_timeline_debug.html')

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
                # 不设置is_admin字段，使用默认值
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
            login_user(user)
            session['user_id'] = user.id
            session['username'] = user.username
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

    logout_user()
    session.pop('user_id', None)
    session.pop('username', None)

    if username:
        logger.info(f"用户 {username} 已登出")

    return redirect(url_for('login'))

@app.route('/config', methods=['GET', 'POST'])
def config():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    config_path = 'config/social-networks.yml'
    templates_path = 'config/prompt-templates.yml'

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

    # 读取模板配置文件
    try:
        if os.path.exists(templates_path):
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates_content = f.read()
                templates_data = yaml.safe_load(templates_content)
        else:
            # 创建默认模板配置
            templates_data = {
                'templates': {
                    'finance': get_default_prompt_template('finance'),
                    'tech': get_default_prompt_template('tech'),
                    'general': get_default_prompt_template('general')
                }
            }
            # 保存默认模板配置
            with open(templates_path, 'w', encoding='utf-8') as f:
                yaml.dump(templates_data, f, allow_unicode=True)
    except Exception as e:
        logger.error(f"读取或创建模板配置文件时出错: {str(e)}")
        templates_data = {
            'templates': {
                'finance': get_default_prompt_template('finance'),
                'tech': get_default_prompt_template('tech'),
                'general': get_default_prompt_template('general')
            }
        }

    # 获取所有账号信息，包括头像URL
    accounts = SocialAccount.query.all()

    # 创建账号字典，方便在模板中查找账号信息
    accounts_dict = {}
    for account in accounts:
        accounts_dict[account.account_id] = {
            'id': account.id,
            'type': account.type,
            'avatar_url': account.avatar_url,
            'display_name': account.display_name,
            'bio': account.bio,
            'verified': account.verified,
            'followers_count': account.followers_count,
            'following_count': account.following_count
        }

    return render_template('config.html',
                          config=config_content,
                          templates=templates_data.get('templates', {}),
                          accounts=accounts,
                          accounts_dict=accounts_dict)

@app.route('/api/save_templates', methods=['POST'])
def save_templates():
    """保存提示词模板配置"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    templates_path = 'config/prompt-templates.yml'

    try:
        # 获取请求数据
        data = request.json
        logger.info(f"收到保存模板请求，数据类型: {type(data)}")

        if not data or 'templates' not in data:
            logger.error(f"无效的请求数据: {data}")
            return jsonify({'success': False, 'message': '无效的请求数据'}), 400

        templates = data['templates']
        logger.info(f"接收到的模板数据: finance长度={len(templates.get('finance', ''))}, tech长度={len(templates.get('tech', ''))}, general长度={len(templates.get('general', ''))}")

        # 验证模板数据
        required_templates = ['finance', 'tech', 'general']
        for template_name in required_templates:
            if template_name not in templates:
                logger.warning(f"模板 {template_name} 缺失，使用默认模板")
                templates[template_name] = get_default_prompt_template(template_name)

        # 确保目录存在
        os.makedirs(os.path.dirname(templates_path), exist_ok=True)

        # 保存到配置文件
        templates_data = {'templates': templates}
        with open(templates_path, 'w', encoding='utf-8') as f:
            yaml.dump(templates_data, f, allow_unicode=True)

        logger.info(f"提示词模板配置已保存到 {templates_path}")

        # 验证保存是否成功
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                saved_data = yaml.safe_load(f)
                saved_templates = saved_data.get('templates', {})
                logger.info(f"验证保存结果: finance长度={len(saved_templates.get('finance', ''))}, tech长度={len(saved_templates.get('tech', ''))}, general长度={len(saved_templates.get('general', ''))}")
        except Exception as verify_error:
            logger.error(f"验证保存结果时出错: {verify_error}")

        return jsonify({'success': True, 'message': '提示词模板已保存'})
    except Exception as e:
        logger.error(f"保存提示词模板配置时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500

@app.route('/api/settings/templates', methods=['GET'])
def get_templates():
    """获取提示词模板配置"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    templates_path = 'config/prompt-templates.yml'

    try:
        # 读取模板配置文件
        if os.path.exists(templates_path):
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates_content = f.read()
                templates_data = yaml.safe_load(templates_content)
                templates = templates_data.get('templates', {})
        else:
            # 创建默认模板配置
            templates = {
                'finance': get_default_prompt_template('finance'),
                'tech': get_default_prompt_template('tech'),
                'general': get_default_prompt_template('general')
            }

            # 保存默认模板配置
            templates_data = {'templates': templates}
            with open(templates_path, 'w', encoding='utf-8') as f:
                yaml.dump(templates_data, f, allow_unicode=True)

        logger.info("提示词模板配置已获取")
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        logger.error(f"获取提示词模板配置时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'获取失败: {str(e)}'}), 500

@app.route('/results')
def results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    per_page = 20

    # 获取筛选参数
    account_id = request.args.get('account_id')
    platform = request.args.get('platform')
    relevance = request.args.get('relevance')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    sort = request.args.get('sort', 'time-desc')
    search = request.args.get('search')

    # 构建查询
    query = AnalysisResult.query

    # 应用筛选条件
    # 1. 账号ID筛选
    if account_id and account_id.lower() != 'undefined':
        logger.info(f"按账号ID筛选结果: {account_id}")
        query = query.filter_by(account_id=account_id)
    elif account_id == 'undefined':
        logger.warning("收到无效的account_id参数: 'undefined'，忽略此筛选条件")

    # 2. 平台筛选
    if platform:
        logger.info(f"按平台筛选结果: {platform}")
        query = query.filter_by(social_network=platform)

    # 3. 相关性筛选
    if relevance:
        if relevance == 'relevant':
            logger.info("筛选相关结果")
            query = query.filter_by(is_relevant=True)
        elif relevance == 'irrelevant':
            logger.info("筛选不相关结果")
            query = query.filter_by(is_relevant=False)

    # 4. 日期范围筛选
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            logger.info(f"筛选从 {from_date} 开始的结果")
            query = query.filter(AnalysisResult.post_time >= from_date)
        except ValueError as e:
            logger.warning(f"无效的日期格式 date_from={date_from}: {e}")

    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            logger.info(f"筛选到 {to_date} 结束的结果")
            query = query.filter(AnalysisResult.post_time <= to_date)
        except ValueError as e:
            logger.warning(f"无效的日期格式 date_to={date_to}: {e}")

    # 5. 搜索功能
    if search:
        search_term = f"%{search}%"
        logger.info(f"搜索关键词: {search}")
        query = query.filter(
            db.or_(
                AnalysisResult.content.ilike(search_term),
                AnalysisResult.account_id.ilike(search_term),
                AnalysisResult.social_network.ilike(search_term),
                AnalysisResult.analysis.ilike(search_term)
            )
        )

    # 应用排序
    if sort == 'time-asc':
        logger.info("按时间升序排序")
        query = query.order_by(AnalysisResult.post_time.asc())
    elif sort == 'confidence-desc':
        logger.info("按置信度降序排序")
        query = query.order_by(AnalysisResult.confidence.desc())
    elif sort == 'confidence-asc':
        logger.info("按置信度升序排序")
        query = query.order_by(AnalysisResult.confidence.asc())
    elif sort == 'platform':
        logger.info("按平台排序")
        query = query.order_by(AnalysisResult.social_network.asc(), AnalysisResult.post_time.desc())
    elif sort == 'account':
        logger.info("按账号排序")
        query = query.order_by(AnalysisResult.account_id.asc(), AnalysisResult.post_time.desc())
    else:  # 默认按时间降序排序
        logger.info("按时间降序排序")
        query = query.order_by(AnalysisResult.post_time.desc())

    # 分页
    results = query.paginate(page=page, per_page=per_page)

    # 获取所有账号，用于过滤
    accounts = SocialAccount.query.all()

    # 创建时间线虚拟账号对象
    class TimelineAccount:
        def __init__(self):
            self.id = 'timeline'
            self.account_id = 'timeline'
            self.type = 'twitter'
            self.display_name = '时间线 (关注账号)'
            self.avatar_url = None

    # 将时间线账号添加到账号列表中
    timeline_account = TimelineAccount()
    accounts = list(accounts) + [timeline_account]

    # 创建账号字典，方便在模板中查找账号信息
    accounts_dict = {}
    for account in accounts:
        # 处理时间线虚拟账号和普通账号
        if hasattr(account, 'display_name'):
            # 时间线虚拟账号
            accounts_dict[account.account_id] = {
                'id': account.id,
                'type': account.type,
                'avatar_url': account.avatar_url,
                'display_name': account.display_name
            }
        else:
            # 普通数据库账号
            accounts_dict[account.account_id] = {
                'id': account.id,
                'type': account.type,
                'avatar_url': account.avatar_url,
                'display_name': getattr(account, 'display_name', account.account_id)
            }

    return render_template('results.html', results=results, accounts=accounts, accounts_dict=accounts_dict)

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
@app.route('/logs')
def logs_page():
    """系统日志页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    logger.info("访问系统日志页面")
    return render_template('logs.html')

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
        bypass_ai = request.form.get('bypass_ai') == 'on'
        prompt_template = request.form.get('prompt_template')
        auto_reply_template = request.form.get('auto_reply_template')

        # AI提供商相关字段
        ai_provider_id = request.form.get('ai_provider_id')
        text_provider_id = request.form.get('text_provider_id')
        image_provider_id = request.form.get('image_provider_id')
        video_provider_id = request.form.get('video_provider_id')
        gif_provider_id = request.form.get('gif_provider_id')

        # 转换为整数或None
        ai_provider_id = int(ai_provider_id) if ai_provider_id and ai_provider_id.isdigit() else None
        text_provider_id = int(text_provider_id) if text_provider_id and text_provider_id.isdigit() else None
        image_provider_id = int(image_provider_id) if image_provider_id and image_provider_id.isdigit() else None
        video_provider_id = int(video_provider_id) if video_provider_id and video_provider_id.isdigit() else None
        gif_provider_id = int(gif_provider_id) if gif_provider_id and gif_provider_id.isdigit() else None

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
            bypass_ai=bypass_ai,
            prompt_template=prompt_template,
            auto_reply_template=auto_reply_template,
            ai_provider_id=ai_provider_id,
            text_provider_id=text_provider_id,
            image_provider_id=image_provider_id,
            video_provider_id=video_provider_id,
            gif_provider_id=gif_provider_id
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

    # 获取默认自动回复模板
    default_reply_prompt = """请根据以下社交媒体内容和分析结果，生成一个友好、专业的回复。
回复应该简洁、有礼貌，并且与原内容相关。如果内容与AI相关，可以提供一些见解或提问。

原始内容：
{content}

分析结果：
{analysis}

回复要求：
1. 称呼用户为 @{username}
2. 回复长度控制在280字符以内
3. 语气友好专业
4. 不要使用过多表情符号
5. 如果内容与AI无关，回复应该简短礼貌

请直接给出回复内容，不要包含其他说明。"""

    return render_template('account_form.html',
                          account=None,
                          default_prompt=default_prompt,
                          default_reply_prompt=default_reply_prompt,
                          action='add')

@app.route('/accounts/edit/<account_id>', methods=['GET', 'POST'])
def edit_account(account_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 尝试将account_id转换为整数（兼容旧版本的路由）
    try:
        id_as_int = int(account_id)
        account = SocialAccount.query.get(id_as_int)
        if account:
            logger.info(f"通过ID查找账号: {id_as_int}")
        else:
            # 如果找不到，尝试通过account_id查找
            account = SocialAccount.query.filter_by(account_id=account_id).first()
            if account:
                logger.info(f"通过account_id查找账号: {account_id}")
            else:
                logger.error(f"未找到账号: {account_id}")
                flash(f'未找到ID为 {account_id} 的账号', 'danger')
                return redirect(url_for('accounts'))
    except ValueError:
        # 如果不是整数，直接通过account_id查找
        account = SocialAccount.query.filter_by(account_id=account_id).first()
        if account:
            logger.info(f"通过account_id查找账号: {account_id}")
        else:
            logger.error(f"未找到账号: {account_id}")
            flash(f'未找到ID为 {account_id} 的账号', 'danger')
            return redirect(url_for('accounts'))

    if request.method == 'POST':
        account.type = request.form.get('type')
        account.account_id = request.form.get('account_id')
        account.tag = request.form.get('tag', 'all')
        account.enable_auto_reply = request.form.get('enable_auto_reply') == 'on'
        account.bypass_ai = request.form.get('bypass_ai') == 'on'
        account.prompt_template = request.form.get('prompt_template')
        account.auto_reply_template = request.form.get('auto_reply_template')

        # AI提供商相关字段
        ai_provider_id = request.form.get('ai_provider_id')
        text_provider_id = request.form.get('text_provider_id')
        image_provider_id = request.form.get('image_provider_id')
        video_provider_id = request.form.get('video_provider_id')
        gif_provider_id = request.form.get('gif_provider_id')

        # 转换为整数或None
        account.ai_provider_id = int(ai_provider_id) if ai_provider_id and ai_provider_id.isdigit() else None
        account.text_provider_id = int(text_provider_id) if text_provider_id and text_provider_id.isdigit() else None
        account.image_provider_id = int(image_provider_id) if image_provider_id and image_provider_id.isdigit() else None
        account.video_provider_id = int(video_provider_id) if video_provider_id and video_provider_id.isdigit() else None
        account.gif_provider_id = int(gif_provider_id) if gif_provider_id and gif_provider_id.isdigit() else None

        db.session.commit()

        # 同步到配置文件
        sync_accounts_to_yaml()

        logger.info(f"已更新账号: {account.type}:{account.account_id}")
        flash('账号已成功更新')
        return redirect(url_for('accounts'))

    # 获取默认提示词模板
    default_prompt = get_default_prompt_template(account.type if account else 'twitter')

    # 获取默认自动回复模板
    default_reply_prompt = """请根据以下社交媒体内容和分析结果，生成一个友好、专业的回复。
回复应该简洁、有礼貌，并且与原内容相关。如果内容与AI相关，可以提供一些见解或提问。

原始内容：
{content}

分析结果：
{analysis}

回复要求：
1. 称呼用户为 @{username}
2. 回复长度控制在280字符以内
3. 语气友好专业
4. 不要使用过多表情符号
5. 如果内容与AI无关，回复应该简短礼貌

请直接给出回复内容，不要包含其他说明。"""

    return render_template('account_form.html',
                          account=account,
                          default_prompt=default_prompt,
                          default_reply_prompt=default_reply_prompt,
                          action='edit')

@app.route('/accounts/delete/<account_id>', methods=['POST'])
def delete_account(account_id):
    if 'user_id' not in session:
        # 检查请求类型，如果是AJAX请求，返回JSON响应
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({"success": False, "message": "未登录"}), 401
        return redirect(url_for('login'))

    # 尝试将account_id转换为整数（兼容旧版本的路由）
    try:
        id_as_int = int(account_id)
        account = SocialAccount.query.get(id_as_int)
        if account:
            logger.info(f"通过ID删除账号: {id_as_int}")
        else:
            # 如果找不到，尝试通过account_id查找
            account = SocialAccount.query.filter_by(account_id=account_id).first_or_404()
            logger.info(f"通过account_id删除账号: {account_id}")
    except ValueError:
        # 如果不是整数，直接通过account_id查找
        account = SocialAccount.query.filter_by(account_id=account_id).first_or_404()
        logger.info(f"通过account_id删除账号: {account_id}")

    try:
        # 记录要删除的账号信息
        account_info = f"{account.type}:{account.account_id}"

        # 删除账号
        db.session.delete(account)
        db.session.commit()

        # 同步到配置文件
        sync_accounts_to_yaml()

        logger.info(f"已删除账号: {account_info}")

        # 检查请求类型，如果是AJAX请求，返回JSON响应
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({"success": True, "message": "账号已成功删除"})

        # 否则，使用传统的重定向方式
        flash('账号已成功删除', 'success')

        # 使用绝对URL进行重定向，避免相对路径问题
        return redirect('/accounts')
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除账号时出错: {str(e)}")

        # 检查请求类型，如果是AJAX请求，返回JSON响应
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({"success": False, "message": f"删除账号失败: {str(e)}"}), 500

        # 否则，使用传统的重定向方式
        flash(f'删除账号失败: {str(e)}', 'danger')

        # 使用绝对URL进行重定向，避免相对路径问题
        return redirect('/accounts')

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
            # 检查数据库是否已存在表
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()

            if existing_tables:
                logger.info(f"数据库已存在表: {existing_tables}，跳过初始化")
                # 只创建不存在的表，保留现有数据
                db.create_all()
                logger.info("已创建缺失的表（如果有）")

                # 字段迁移已由统一的迁移系统处理，无需在此重复处理
            else:
                # 首次创建所有表
                logger.info("数据库为空，创建所有表")
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

        # 创建默认AI提供商
        try:
            if create_default_ai_providers():
                logger.info("创建默认AI提供商成功")
            else:
                logger.debug("未创建默认AI提供商")
        except Exception as e:
            logger.error(f"创建默认AI提供商时出错: {str(e)}")

        # 运行统一数据库迁移脚本
        try:
            from migrations.db_migrations import run_all_migrations
            if run_all_migrations():
                logger.info("数据库迁移成功完成")
            else:
                logger.warning("数据库迁移过程中出现错误，请检查日志")
        except Exception as e:
            logger.error(f"运行数据库迁移脚本时出错: {str(e)}")

    logger.info("数据库初始化完成")

# 保存分析结果的API端点已移动到api/analytics.py

# 数据导出功能
@app.route('/export_data')
def export_data():
    """导出所有数据为JSON文件"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 如果没有参数，重定向到数据迁移页面，并显示导出选项卡
    if not request.args:
        return redirect(url_for('data_transfer', tab='export'))

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

# 数据迁移功能（导入和导出）
@app.route('/data_transfer', methods=['GET'])
def data_transfer():
    """数据迁移页面（导入和导出）"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('data_transfer.html')

# 数据导入功能
@app.route('/import_data', methods=['GET', 'POST'])
def import_data():
    """导入数据"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        # GET请求重定向到数据迁移页面，并显示导入选项卡
        return redirect(url_for('data_transfer'))

    # POST请求处理导入逻辑
    # 检查是否有文件上传
    if 'import_file' not in request.files:
        flash('没有选择文件', 'danger')
        return redirect(url_for('data_transfer'))

    file = request.files['import_file']

    # 检查文件名
    if file.filename == '':
        flash('没有选择文件', 'danger')
        return redirect(url_for('data_transfer'))

    # 检查文件类型
    if not file.filename.endswith('.json'):
        flash('只支持导入JSON文件', 'danger')
        return redirect(url_for('data_transfer'))

    try:
        # 读取并解析JSON数据
        import_data = json.loads(file.read().decode('utf-8'))

        # 验证数据格式
        if 'accounts' not in import_data or 'version' not in import_data:
            flash('导入文件格式不正确，缺少必要的数据字段', 'danger')
            return redirect(url_for('data_transfer'))

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
                        bypass_ai=account_data.get('bypass_ai', False),
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

            # 检查是否包含分析结果数据
            if 'results' in import_data:
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
            else:
                # 新版本导出文件不包含分析结果数据
                if is_essential_export:
                    flash('当前导入的是核心配置文件，不包含分析结果数据。如需导入分析结果，请使用完整数据导出文件。', 'info')
                else:
                    flash('导入文件中未找到分析结果数据', 'warning')

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

                    config_obj, updated = set_config(
                        config['key'],
                        config['value'],
                        is_secret=config.get('value') == '******',
                        description=config.get('description', ''),
                        update_env=False
                    )
                    if updated:
                        imported_configs += 1
                        logger.info(f"导入配置 {config['key']} 成功")
                    else:
                        logger.debug(f"配置 {config['key']} 已存在且值相同，跳过导入")

                # 导入Twitter配置
                for config in config_categories.get('twitter', []):
                    if not config.get('is_set', False) and config.get('value', '') == '******':
                        # 跳过敏感信息，这些信息在导出时被屏蔽
                        continue

                    config_obj, updated = set_config(
                        config['key'],
                        config['value'],
                        is_secret=config.get('value') == '******',
                        description=config.get('description', ''),
                        update_env=False
                    )
                    if updated:
                        imported_configs += 1
                        logger.info(f"导入配置 {config['key']} 成功")
                    else:
                        logger.debug(f"配置 {config['key']} 已存在且值相同，跳过导入")

                # 导入通知配置
                for config in config_categories.get('notification', []):
                    if not config.get('is_set', False) and config.get('value', '') == '******':
                        # 跳过敏感信息，这些信息在导出时被屏蔽
                        continue

                    config_obj, updated = set_config(
                        config['key'],
                        config['value'],
                        is_secret=config.get('value') == '******',
                        description=config.get('description', ''),
                        update_env=False
                    )
                    if updated:
                        imported_configs += 1
                        logger.info(f"导入配置 {config['key']} 成功")
                    else:
                        logger.debug(f"配置 {config['key']} 已存在且值相同，跳过导入")

                # 导入其他配置
                for config in config_categories.get('other', []):
                    if not config.get('is_set', False) and config.get('value', '') == '******':
                        # 跳过敏感信息，这些信息在导出时被屏蔽
                        continue

                    config_obj, updated = set_config(
                        config['key'],
                        config['value'],
                        is_secret=config.get('value') == '******',
                        description=config.get('description', ''),
                        update_env=False
                    )
                    if updated:
                        imported_configs += 1
                        logger.info(f"导入配置 {config['key']} 成功")
                    else:
                        logger.debug(f"配置 {config['key']} 已存在且值相同，跳过导入")
            else:
                # 旧版本格式（平铺配置）
                for config_data in import_data.get('configs', []):
                    # 设置配置
                    config_obj, updated = set_config(
                        config_data['key'],
                        config_data['value'],
                        is_secret=False,
                        description=config_data.get('description', ''),
                        update_env=False
                    )
                    if updated:
                        imported_configs += 1
                        logger.info(f"导入配置 {config_data['key']} 成功")
                    else:
                        logger.debug(f"配置 {config_data['key']} 已存在且值相同，跳过导入")

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
                        config_obj, updated = set_config(
                            'ENABLE_AUTO_REPLY',
                            config['value'],
                            description='是否启用自动回复',
                            update_env=False
                        )
                        if updated:
                            logger.info(f"导入自动回复配置成功")
                            auto_reply_imported = True
                        else:
                            logger.debug(f"自动回复配置已存在且值相同，跳过导入")
            # 旧版本格式
            elif 'auto_reply' in import_data:
                auto_reply = import_data['auto_reply']
                if 'enabled' in auto_reply:
                    config_obj, updated = set_config(
                        'ENABLE_AUTO_REPLY',
                        'true' if auto_reply['enabled'] else 'false',
                        description='是否启用自动回复',
                        update_env=False
                    )
                    if updated:
                        logger.info(f"导入自动回复配置成功")
                        auto_reply_imported = True
                    else:
                        logger.debug(f"自动回复配置已存在且值相同，跳过导入")

            if notification_imported or auto_reply_imported:
                flash('成功导入通知和自动回复配置', 'success')

        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"导入数据时出错: {str(e)}")
        flash(f"导入数据失败: {str(e)}", 'danger')
        return redirect(url_for('data_transfer'))



if __name__ == '__main__':
    try:
        with app.app_context():
            try:
                # 初始化数据库
                init_db()
                logger.info("数据库初始化成功")
            except Exception as db_error:
                logger.critical(f"数据库初始化失败: {str(db_error)}")
                print(f"数据库初始化失败: {str(db_error)}")

            # 使用统一的配置初始化函数
            try:
                # 使用应用上下文初始化配置
                result = service_init_config(force=True, validate=True, app_context=app.app_context())

                if result['success']:
                    logger.info(f"配置初始化成功: {result['message']}")

                    # 检查是否有缺失的关键配置
                    if result['missing_configs']:
                        missing_configs = ', '.join(result['missing_configs'])
                        logger.warning(f"缺少关键配置: {missing_configs}")
                        print(f"警告: 缺少关键配置: {missing_configs}")
                    else:
                        logger.info("所有关键配置都已设置")
                else:
                    logger.warning(f"配置初始化失败: {result['message']}")
                    print(f"警告: 配置初始化失败: {result['message']}")
            except Exception as config_error:
                logger.warning(f"配置初始化失败: {str(config_error)}")
                print(f"警告: 配置初始化失败: {str(config_error)}")

        # 获取调试模式设置
        debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
        logger.info(f"调试模式: {'启用' if debug_mode else '禁用'}")

        # 启动Web服务器
        logger.info("启动Web服务器...")
        app.run(debug=debug_mode, host='0.0.0.0', port=5000)
    except Exception as e:
        logger.critical(f"应用启动失败: {str(e)}")
        print(f"应用启动失败: {str(e)}")
        # 在这里可以添加更多的错误处理逻辑
