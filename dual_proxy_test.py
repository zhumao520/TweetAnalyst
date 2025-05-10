import os
import requests
import time
import json
import argparse

def test_proxy_with_url(proxy_url, test_url, timeout=10):
    """
    使用指定URL测试代理连接

    Args:
        proxy_url: 代理URL
        test_url: 测试URL
        timeout: 超时时间（秒）

    Returns:
        dict: 测试结果
    """
    print(f"测试URL: {test_url}")

    # 设置代理
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    # 测试连接
    try:
        start_time = time.time()
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        end_time = time.time()

        print(f"状态码: {response.status_code}")
        print(f"响应时间: {end_time - start_time:.2f}秒")

        # 对于Google的测试URL，204状态码表示成功
        if test_url == "https://www.google.com/generate_204" and response.status_code == 204:
            print("Google连接测试成功（204状态码）")
            return {
                "success": True,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "data": {"message": "Google连接测试成功"}
            }

        # 尝试解析响应
        try:
            data = response.json()
            print(f"响应内容: {json.dumps(data, indent=2, ensure_ascii=False)}")

            # 如果是IP测试，显示IP地址
            if 'origin' in data:
                print(f"当前IP: {data['origin']}")

            return {
                "success": True,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "data": data
            }
        except:
            print(f"响应内容: {response.text[:200]}")
            return {
                "success": True,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "data": {"text": response.text[:200]}
            }

    except Exception as e:
        print(f"连接失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

def test_dual_proxy(proxy_url):
    """
    同时测试国内和国外网站

    Args:
        proxy_url: 代理URL

    Returns:
        dict: 测试结果
    """
    print(f"\n正在测试代理: {proxy_url}")

    # 测试国内网站（百度）
    print("\n===== 测试国内网站 =====")
    baidu_result = test_proxy_with_url(proxy_url, "http://www.baidu.com")

    # 测试国外网站（Google）
    print("\n===== 测试国外网站 =====")
    foreign_result = test_proxy_with_url(proxy_url, "https://www.google.com/generate_204")

    # 分析结果
    baidu_success = baidu_result.get("success", False)
    foreign_success = foreign_result.get("success", False)

    print("\n===== 测试结果分析 =====")
    if baidu_success and foreign_success:
        print("✅ 代理工作正常，可以访问国内和国外网站")
        diagnosis = "代理工作正常，可以访问国内和国外网站"
    elif baidu_success and not foreign_success:
        print("⚠️ 代理可以访问国内网站，但无法访问国外网站")
        print("可能原因：代理服务器无法访问国外网站或代理配置不正确")
        diagnosis = "代理可以访问国内网站，但无法访问国外网站。可能是代理服务器本身无法访问国外网站。"
    elif not baidu_success and foreign_success:
        print("⚠️ 代理可以访问国外网站，但无法访问国内网站")
        print("可能原因：代理配置不正确或代理服务器屏蔽了国内网站")
        diagnosis = "代理可以访问国外网站，但无法访问国内网站。这种情况比较少见，可能是代理配置有特殊限制。"
    else:
        print("❌ 代理完全无法工作，无法访问任何网站")
        print("可能原因：代理服务器不可用、代理地址或端口错误、网络连接问题")
        diagnosis = "代理完全无法工作。请检查代理服务器是否正常运行，以及代理地址和端口是否正确。"

    return {
        "baidu_test": baidu_result,
        "foreign_test": foreign_result,
        "diagnosis": diagnosis
    }

def main():
    parser = argparse.ArgumentParser(description='测试代理连接')
    parser.add_argument('--proxy', default='http://192.168.3.219:1080', help='代理URL')
    args = parser.parse_args()

    # 测试代理
    results = test_dual_proxy(args.proxy)

    # 输出诊断结果
    print("\n===== 最终诊断 =====")
    print(results["diagnosis"])

if __name__ == "__main__":
    main()
