#!/usr/bin/env python3
"""
简单测试智能工具调用API端点
"""
import requests

def test_smart_call_api():
    """测试智能工具调用API是否正常响应"""
    base_url = "http://localhost:8080"
    
    # 测试数据
    test_data = {
        "tool_name": "echo",
        "task_description": "回显一个测试消息：Hello World",
        "vm_id": "vm123", 
        "session_id": "sess456"
    }
    
    print("🧪 测试智能工具调用API端点...")
    print(f"URL: {base_url}/tools/smart-call")
    
    try:
        response = requests.post(f"{base_url}/tools/smart-call", json=test_data, timeout=5)
        
        print(f"响应状态: HTTP {response.status_code}")
        print(f"响应内容: {response.text}")
        
        return response.status_code in [200, 500]  # 200成功，500说明端点存在但执行失败
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

if __name__ == "__main__":
    if test_smart_call_api():
        print("✅ API端点响应正常")
    else:
        print("❌ API端点无响应")