#!/usr/bin/env python3
"""
交互式Twitter连接测试和配置工具
"""
import os
import sys
import traceback
import getpass
import importlib.util
import sqlite3
import time

# 配置颜色输出
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_color(text, color):
    """彩色输出"""
    print(f"{color}{text}{Colors.ENDC}")

def clear_screen():
    """清除屏幕"""
    os.system('clear' if os.name != 'nt' else 'cls')

def check_package(module_name):
    """检查包是否已安装"""
    return importlib.util.find_spec(module_name) is not None

def ensure_socks_support():
    """确保系统支持SOCKS代理"""
    if not check_package("socksio"):
        print_color("检测到SOCKS代理，但未安装socksio包，尝试安装...", Colors.YELLOW)
        try:
            import pip
            pip.main(['install', 'httpx[socks]', '--quiet'])
            print_color("成功安装SOCKS代理支持", Colors.GREEN)
            return True
        except Exception as e:
            print_color(f"安装SOCKS代理支持失败: {str(e)}", Colors.RED)
            return False
    return True

def test_twitter_connection(username, password, use_proxy=False, proxy_url=None):
    """测试Twitter连接"""
    print_color("\n正在测试Twitter连接...", Colors.BLUE)
    
    try:
        # 检查tweety库是否已安装
        if not check_package("tweety"):
            print_color("tweety库未安装，尝试安装...", Colors.YELLOW)
            try:
                import pip
                pip.main(['install', 'tweety-ns', '--quiet'])
                print_color("成功安装tweety库", Colors.GREEN)
            except Exception as e:
                print_color(f"安装tweety库失败: {str(e)}", Colors.RED)
                return False
        
        # 设置代理环境变量（如果需要）
        if use_proxy and proxy_url:
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            print_color(f"已设置代理环境变量: {proxy_url}", Colors.GREEN)
            
            # 如果是SOCKS代理，确保安装了支持
            if proxy_url.startswith('socks'):
                if not ensure_socks_support():
                    print_color("SOCKS代理支持安装失败，可能无法正常连接Twitter", Colors.RED)
        
        # 导入tweety库
        from tweety import Twitter
        
        # 初始化Twitter客户端
        print_color("初始化Twitter客户端...", Colors.BLUE)
        twitter = Twitter('test_session')
        
        # 尝试登录
        print_color(f"尝试使用账号 {username} 登录...", Colors.BLUE)
        twitter.sign_in(username, password)
        
        # 检查登录状态
        if hasattr(twitter, 'me') and twitter.me:
            print_color(f"\n✅ 登录成功! 用户: {twitter.me.username}", Colors.GREEN + Colors.BOLD)
            
            # 尝试获取用户信息
            try:
                user = twitter.get_user_info(twitter.me.username)
                print_color(f"用户ID: {user.id if hasattr(user, 'id') else '未知'}", Colors.GREEN)
                print_color(f"关注者数量: {user.followers_count if hasattr(user, 'followers_count') else '未知'}", Colors.GREEN)
                print_color(f"关注数量: {user.following_count if hasattr(user, 'following_count') else '未知'}", Colors.GREEN)
            except Exception as e:
                print_color(f"获取用户详细信息时出错: {str(e)}", Colors.YELLOW)
            
            # 尝试获取一条推文
            print_color("\n尝试获取最新推文...", Colors.BLUE)
            try:
                # 尝试不同的API调用方式
                tweets = None
                try:
                    tweets = twitter.get_tweets(twitter.me.username, limit=1)
                except TypeError:
                    try:
                        tweets = twitter.get_tweets(twitter.me.username, pages=1)
                    except Exception as e:
                        print_color(f"使用pages参数获取推文失败: {str(e)}", Colors.YELLOW)
                        try:
                            tweets = twitter.get_tweets(twitter.me.username)
                        except Exception as e:
                            print_color(f"获取推文失败: {str(e)}", Colors.RED)
                
                if tweets and len(tweets) > 0:
                    print_color(f"✅ 成功获取推文!", Colors.GREEN + Colors.BOLD)
                    tweet = tweets[0]
                    print_color(f"推文内容: {tweet.text[:100] if hasattr(tweet, 'text') else '未知'}...", Colors.GREEN)
                    print_color(f"发布时间: {tweet.created_on if hasattr(tweet, 'created_on') else '未知'}", Colors.GREEN)
                else:
                    print_color("❌ 未获取到推文", Colors.YELLOW)
            except Exception as e:
                print_color(f"❌ 获取推文时出错: {str(e)}", Colors.RED)
                traceback.print_exc()
            
            return True
        else:
            print_color("\n❌ 登录失败: 无法获取用户信息", Colors.RED)
            return False
            
    except Exception as e:
        print_color(f"\n❌ 测试过程中出错: {str(e)}", Colors.RED)
        traceback.print_exc()
        return False

def save_to_database(username, password, proxy=None):
    """将配置保存到数据库"""
    try:
        # 连接到数据库
        conn = sqlite3.connect('/data/tweetanalyst.db')
        cursor = conn.cursor()
        
        # 保存Twitter用户名和密码
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value, is_secret, description) VALUES (?, ?, ?, ?)",
                      ('TWITTER_USERNAME', username, 0, 'Twitter用户名'))
        
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value, is_secret, description) VALUES (?, ?, ?, ?)",
                      ('TWITTER_PASSWORD', password, 1, 'Twitter密码'))
        
        # 如果有代理，也保存代理
        if proxy:
            cursor.execute("INSERT OR REPLACE INTO system_config (key, value, is_secret, description) VALUES (?, ?, ?, ?)",
                          ('HTTP_PROXY', proxy, 0, '代理服务器'))
        
        # 提交更改
        conn.commit()
        conn.close()
        
        print_color("\n✅ 配置已成功保存到数据库", Colors.GREEN + Colors.BOLD)
        return True
    except Exception as e:
        print_color(f"\n❌ 保存配置到数据库时出错: {str(e)}", Colors.RED)
        traceback.print_exc()
        return False

def restart_application():
    """重启应用程序"""
    try:
        print_color("\n正在重启应用程序...", Colors.BLUE)
        
        # 终止当前运行的Python进程
        os.system("pkill -f 'python run_web.py'")
        os.system("pkill -f 'python run_scheduler.py'")
        os.system("pkill -f 'python run_all.py'")
        
        # 等待进程终止
        time.sleep(2)
        
        # 启动应用程序
        os.chdir('/app')
        os.system("python run_all.py &")
        
        print_color("✅ 应用程序已重启", Colors.GREEN + Colors.BOLD)
        return True
    except Exception as e:
        print_color(f"❌ 重启应用程序时出错: {str(e)}", Colors.RED)
        return False

def main():
    """主函数"""
    clear_screen()
    print_color("=" * 60, Colors.BLUE)
    print_color("           Twitter连接测试和配置工具", Colors.BLUE + Colors.BOLD)
    print_color("=" * 60, Colors.BLUE)
    print_color("\n这个工具将帮助您测试Twitter连接并保存配置", Colors.BLUE)
    
    # 获取Twitter账号
    username = input("\n请输入Twitter用户名: ").strip()
    if not username:
        print_color("错误: 用户名不能为空", Colors.RED)
        return
    
    # 获取Twitter密码
    password = getpass.getpass("请输入Twitter密码: ").strip()
    if not password:
        print_color("错误: 密码不能为空", Colors.RED)
        return
    
    # 询问是否使用代理
    use_proxy = input("\n是否需要使用代理? (y/n): ").strip().lower() == 'y'
    proxy_url = None
    
    if use_proxy:
        proxy_url = input("请输入代理URL (例如: http://proxy.example.com:8080): ").strip()
        if not proxy_url:
            print_color("警告: 未提供代理URL，将不使用代理", Colors.YELLOW)
            use_proxy = False
    
    # 测试连接
    connection_success = test_twitter_connection(username, password, use_proxy, proxy_url)
    
    # 如果连接成功，询问是否保存配置
    if connection_success:
        save_config = input("\n连接测试成功! 是否将配置保存到数据库? (y/n): ").strip().lower() == 'y'
        
        if save_config:
            if save_to_database(username, password, proxy_url if use_proxy else None):
                restart_app = input("\n是否重启应用程序以应用新配置? (y/n): ").strip().lower() == 'y'
                
                if restart_app:
                    restart_application()
    else:
        print_color("\n连接测试失败，请检查您的账号、密码和网络连接", Colors.RED)

if __name__ == "__main__":
    main()
