#!/usr/bin/env python3
"""
简单测试文件：调用mcp-client的list_all_paths接口

使用方法：
1. 先启动MCP服务器：cd useit-mcp && ./start_simple_servers.sh start
2. 启动MCP客户端：cd mcp-client && python server.py
3. 运行测试：python test_list_all_paths.py
"""

import requests
import json
from typing import List

def test_list_all_paths(base_url: str = "http://localhost:8080", 
                        vm_id: str = "vm123", 
                        session_id: str = "sess456") -> List[str]:
    """
    测试获取文件系统所有路径的接口
    
    Args:
        base_url: MCP客户端的基础URL
        vm_id: 虚拟机ID
        session_id: 会话ID
        
    Returns:
        文件和文件夹的绝对路径列表
    """
    try:
        # 调用POST接口
        url = f"{base_url}/filesystem/list-all-paths"
        
        # 构建请求体
        payload = {
            "vm_id": vm_id,
            "session_id": session_id,
            "tool_name": "list_all_paths",
            "arguments": {},
            "server_name": "filesystem"
        }
        
        print(f"🚀 正在调用接口: {url}")
        print(f"📝 请求参数: {payload}")
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                paths = data.get("data", {}).get("paths", [])
                print(f"✅ 成功获取 {len(paths)} 个路径")
                
                # 打印前10个路径作为示例
                print("\n📁 路径列表示例 (前10个):")
                for i, path in enumerate(paths[:10]):
                    print(f"  {i+1:2d}. {path}")
                
                if len(paths) > 10:
                    print(f"  ... 还有 {len(paths) - 10} 个路径")
                
                return paths
            else:
                print(f"❌ 接口调用失败: {data.get('message', 'Unknown error')}")
                return []
        else:
            print(f"❌ HTTP错误: {response.status_code} - {response.text}")
            return []
            
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保MCP客户端服务器正在运行 (http://localhost:8080)")
        print("   启动命令: cd mcp-client && python server.py")
        return []
    except Exception as e:
        print(f"❌ 调用异常: {e}")
        return []


def test_with_different_params(base_url: str = "http://localhost:8080", 
                              vm_id: str = "filesystem", 
                              session_id: str = "auto") -> List[str]:
    """
    测试使用不同参数的接口调用
    
    Args:
        base_url: MCP客户端的基础URL
        vm_id: 虚拟机ID
        session_id: 会话ID
        
    Returns:
        文件和文件夹的绝对路径列表
    """
    try:
        url = f"{base_url}/filesystem/list-all-paths"
        
        # 构建请求体
        payload = {
            "vm_id": vm_id,
            "session_id": session_id,
            "tool_name": "list_all_paths",
            "arguments": {},
            "server_name": "filesystem"
        }
        
        print(f"🚀 正在调用接口: {url}")
        print(f"📝 请求参数: {payload}")
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                paths = data.get("data", {}).get("paths", [])
                print(f"✅ 成功获取 {len(paths)} 个路径")
                return paths
            else:
                print(f"❌ 接口调用失败: {data.get('message', 'Unknown error')}")
                return []
        else:
            print(f"❌ HTTP错误: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ 调用异常: {e}")
        return []


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 测试 MCP Client 文件系统路径列表接口")
    print("=" * 60)
    
    # 基础测试
    print("\n1️⃣ 基础测试:")
    paths = test_list_all_paths()
    
    if paths:
        print(f"\n📊 统计信息:")
        print(f"   总路径数: {len(paths)}")
        
        # 统计文件和文件夹数量
        from pathlib import Path
        dirs = sum(1 for p in paths if Path(p).is_dir())
        files = sum(1 for p in paths if Path(p).is_file())
        
        print(f"   文件夹数: {dirs}")
        print(f"   文件数: {files}")
        
        # 按操作系统显示路径格式
        import platform
        os_name = platform.system()
        print(f"   操作系统: {os_name}")
        
        if paths:
            first_path = paths[0]
            print(f"   路径格式: {'Windows格式' if '\\' in first_path else 'Unix格式'}")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成！")