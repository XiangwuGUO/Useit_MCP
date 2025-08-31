#!/usr/bin/env python3
"""
基础功能测试 - 不依赖MCP连接
"""

import requests
import subprocess
import time
import sys

def test_health_api():
    """测试基础API功能"""
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 健康检查API正常")
            print(f"   状态: {data['data']['status']}")
            print(f"   运行时间: {data['data']['uptime']}")
            return True
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API连接失败: {e}")
        return False

def test_stats_api():
    """测试统计API"""
    try:
        response = requests.get("http://localhost:8080/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            stats = data['data']
            print(f"✅ 统计API正常")
            print(f"   客户端数: {stats['total_clients']}")
            print(f"   工具数: {stats['total_tools']}")
            print(f"   运行模式: {stats.get('mode', 'standard')}")
            return True
        else:
            print(f"❌ 统计API失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 统计API连接失败: {e}")
        return False

def test_tools_api():
    """测试工具API"""
    try:
        response = requests.get("http://localhost:8080/tools", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tools = data['data']
            print(f"✅ 工具API正常")
            print(f"   可用工具: {len(tools)}个")
            return True
        else:
            print(f"❌ 工具API失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 工具API连接失败: {e}")
        return False

def test_docs_api():
    """测试API文档"""
    try:
        response = requests.get("http://localhost:8080/docs", timeout=5)
        if response.status_code == 200:
            print(f"✅ API文档可访问")
            return True
        else:
            print(f"❌ API文档访问失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API文档连接失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 基础功能测试")
    print("=" * 40)
    
    # 测试各个API端点
    tests = [
        ("健康检查API", test_health_api),
        ("统计API", test_stats_api), 
        ("工具API", test_tools_api),
        ("API文档", test_docs_api)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n🔍 测试{name}...")
        result = test_func()
        results.append((name, result))
    
    # 汇总结果
    print(f"\n🎯 测试结果:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   • {name}: {status}")
    
    print(f"\n📊 总体结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        print(f"\n🎉 所有基础功能正常！")
        print(f"\n🔗 访问链接:")
        print(f"   • 健康检查: http://localhost:8080/health")
        print(f"   • 系统统计: http://localhost:8080/stats")
        print(f"   • API文档: http://localhost:8080/docs")
        print(f"   • 工具列表: http://localhost:8080/tools")
    else:
        print(f"\n⚠️ 部分功能异常，请检查MCP客户端是否正常运行")
        print(f"   启动命令: cd mcp-client && python server.py")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)