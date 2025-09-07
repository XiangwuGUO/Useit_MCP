#!/usr/bin/env python3
"""
测试智能工具调用功能
"""

import requests
import json
from pathlib import Path


def register_from_json(base_url: str, vm_id: str, session_id: str) -> bool:
    """从JSON文件注册服务器到MCP客户端"""
    json_file = Path("../mcp_server_frp.json")
    
    if not json_file.exists():
        print(f"❌ JSON注册文件不存在: {json_file}")
        return False
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        servers = data.get('servers', [])
        if not servers:
            return False
        
        print(f"📝 从JSON文件注册 {len(servers)} 个服务器...")
        
        for server in servers:
            payload = {
                "vm_id": vm_id,
                "session_id": session_id,
                "name": server['name'],
                "url": server['url'],
                "description": server.get('description', ''),
                "transport": server.get('transport', 'http')
            }
            
            requests.post(f"{base_url}/clients", json=payload)
        
        return True
        
    except Exception as e:
        print(f"❌ 注册失败: {e}")
        return False


def test_smart_tool_call():
    """测试智能工具调用"""
    base_url = "http://localhost:8080"
    
    # 测试数据
    test_call = {
        "tool_name": "write_text",
        "task_description": "创建一个名为test_smart_call.txt的文件，内容是'Hello from smart tool call!'",
        "vm_id": "vm123",
        "session_id": "sess456"
    }
    
    print(f"🧠 测试智能工具调用...")
    print(f"   工具: {test_call['tool_name']}")
    print(f"   任务: {test_call['task_description']}")
    print(f"   客户端: {test_call['vm_id']}/{test_call['session_id']}")
    
    # 自动注册服务器
    print("🔄 自动注册服务器...")
    register_from_json(base_url, test_call['vm_id'], test_call['session_id'])
    
    try:
        response = requests.post(f"{base_url}/tools/smart-call", json=test_call)
        
        if response.status_code == 200:
            data = response.json()
            result_data = data['data']
            
            print("✅ 智能工具调用成功!")
            print(f"   执行时间: {result_data.get('execution_time_seconds', 0):.2f}s")
            print(f"   完成摘要: {result_data.get('completion_summary', 'N/A')}")
            
            # 显示token使用情况
            if result_data.get('token_usage'):
                print(f"   Token使用: {result_data['token_usage']}")
            
            # 显示工具执行结果
            if result_data.get('result'):
                print(f"   工具结果: {result_data['result']}")
            
            return True
        else:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False


if __name__ == "__main__":
    success = test_smart_tool_call()
    if success:
        print("\n✅ 智能工具调用测试通过!")
    else:
        print("\n❌ 智能工具调用测试失败!")