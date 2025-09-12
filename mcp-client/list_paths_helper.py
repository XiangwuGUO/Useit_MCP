#!/usr/bin/env python3
"""
简单的路径列表获取函数 - 直接调用MCP客户端

使用方法：
```python
from list_paths_helper import get_all_paths

# 获取路径列表
paths = get_all_paths(vm_id="demo_vm", session_id="demo_session")
print(paths)
```
"""

import requests
from typing import List, Optional


def get_all_paths(vm_id: str, 
                  session_id: str, 
                  mcp_client_url: str = "http://localhost:8080",
                  server_name: str = "filesystem") -> List[str]:
    """
    获取MCP服务器base_dir下所有文件和文件夹的绝对路径列表
    
    Args:
        vm_id: 虚拟机ID
        session_id: 会话ID  
        mcp_client_url: MCP客户端URL，默认http://localhost:8080
        server_name: MCP服务器名称，默认filesystem
        
    Returns:
        List[str]: 所有文件和文件夹的绝对路径列表
        
    Raises:
        Exception: 当调用失败时抛出异常
    """
    try:
        url = f"{mcp_client_url}/filesystem/list-all-paths"
        
        payload = {
            "vm_id": vm_id,
            "session_id": session_id,
            "tool_name": "list_all_paths",
            "arguments": {},
            "server_name": server_name
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                paths = data.get("data", {}).get("paths", [])
                return paths
            else:
                raise Exception(f"API调用失败: {data.get('message', 'Unknown error')}")
        else:
            raise Exception(f"HTTP错误 {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"连接MCP客户端失败: {mcp_client_url}. 请确保服务正在运行。")
    except requests.exceptions.Timeout as e:
        raise Exception(f"请求超时: {e}")
    except Exception as e:
        raise Exception(f"调用失败: {e}")


def get_all_paths_safe(vm_id: str, 
                       session_id: str, 
                       mcp_client_url: str = "http://localhost:8080",
                       server_name: str = "filesystem") -> Optional[List[str]]:
    """
    安全版本的路径获取函数，不会抛出异常
    
    Args:
        vm_id: 虚拟机ID
        session_id: 会话ID  
        mcp_client_url: MCP客户端URL，默认http://localhost:8080
        server_name: MCP服务器名称，默认filesystem
        
    Returns:
        Optional[List[str]]: 成功时返回路径列表，失败时返回None
    """
    try:
        return get_all_paths(vm_id, session_id, mcp_client_url, server_name)
    except Exception as e:
        print(f"❌ 获取路径失败: {e}")
        return None


if __name__ == "__main__":
    # 测试函数
    print("🧪 测试路径获取函数")
    print("=" * 40)
    
    try:
        # 测试1：基础调用
        print("1️⃣ 测试基础调用:")
        paths = get_all_paths("demo_vm", "demo_session")
        print(f"✅ 成功获取 {len(paths)} 个路径")
        
        # 显示前5个路径
        print("\n📁 路径示例:")
        for i, path in enumerate(paths[:5]):
            print(f"  {i+1}. {path}")
        if len(paths) > 5:
            print(f"  ... 还有 {len(paths) - 5} 个路径")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        
        # 测试2：安全版本
        print("\n2️⃣ 测试安全版本:")
        paths = get_all_paths_safe("demo_vm", "demo_session")
        if paths:
            print(f"✅ 安全调用成功，获取 {len(paths)} 个路径")
        else:
            print("❌ 安全调用也失败了")
    
    print("\n" + "=" * 40)
    print("💡 使用提示:")
    print("   from list_paths_helper import get_all_paths")
    print("   paths = get_all_paths('your_vm_id', 'your_session_id')")