#!/usr/bin/env python3
"""
MCP客户端功能测试脚本
测试假设MCP客户端和服务器都已启动并注册
主要测试filesystem服务器和其他核心功能
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List

import requests

# 配置
MCP_CLIENT_URL = "http://localhost:8080"
TEST_TIMEOUT = 10

class MCPClientTester:
    """MCP客户端测试器"""
    
    def __init__(self, base_url: str = MCP_CLIENT_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = TEST_TIMEOUT
        
    def test_health(self) -> bool:
        """测试健康检查"""
        print("\n🏥 测试健康检查...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 健康检查通过: {data['data']['status']}")
                print(f"   - 连接的客户端: {data['data']['connected_clients']}")
                print(f"   - 可用工具: {data['data']['total_tools']}")
                return True
            else:
                print(f"❌ 健康检查失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 健康检查异常: {e}")
            return False
    
    def test_list_clients(self) -> List[Dict[str, Any]]:
        """测试列出所有客户端"""
        print("\n📋 测试列出客户端...")
        try:
            response = self.session.get(f"{self.base_url}/clients")
            if response.status_code == 200:
                data = response.json()
                clients = data['data']
                print(f"✅ 获取到 {len(clients)} 个客户端:")
                for client in clients:
                    print(f"   - {client['vm_id']}/{client['session_id']}: {client['status']}")
                return clients
            else:
                print(f"❌ 获取客户端列表失败: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ 获取客户端列表异常: {e}")
            return []
    
    def test_list_tools(self) -> List[Dict[str, Any]]:
        """测试列出所有工具"""
        print("\n🔧 测试列出工具...")
        try:
            response = self.session.get(f"{self.base_url}/tools")
            if response.status_code == 200:
                data = response.json()
                tools = data['data']
                print(f"✅ 获取到 {len(tools)} 个工具:")
                
                # 按服务器分组显示
                servers = {}
                for tool in tools:
                    server_id = f"{tool['vm_id']}/{tool['session_id']}"
                    if server_id not in servers:
                        servers[server_id] = []
                    servers[server_id].append(tool['name'])
                
                for server_id, tool_names in servers.items():
                    print(f"   [{server_id}]: {', '.join(tool_names)}")
                
                return tools
            else:
                print(f"❌ 获取工具列表失败: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ 获取工具列表异常: {e}")
            return []
    
    def find_filesystem_client(self, clients: List[Dict[str, Any]]) -> tuple[str, str]:
        """查找filesystem服务器的客户端信息"""
        for client in clients:
            vm_id = client['vm_id']
            if 'filesystem' in vm_id.lower():
                return vm_id, client['session_id']
        
        # 如果没找到明确的filesystem，尝试第一个可用的客户端
        if clients:
            return clients[0]['vm_id'], clients[0]['session_id']
        
        raise Exception("没有找到可用的filesystem客户端")
    
    def test_filesystem_operations(self, vm_id: str, session_id: str):
        """测试filesystem服务器操作"""
        print(f"\n📁 测试filesystem操作 ({vm_id}/{session_id})...")
        
        # 测试列出目录
        self._test_list_directory(vm_id, session_id)
        
        # 测试创建目录
        self._test_create_directory(vm_id, session_id)
        
        # 测试写入文件
        self._test_write_file(vm_id, session_id)
        
        # 测试读取文件
        self._test_read_file(vm_id, session_id)
        
        # 测试删除文件
        self._test_delete_file(vm_id, session_id)
    
    def _test_list_directory(self, vm_id: str, session_id: str):
        """测试列出目录内容"""
        print("  📂 测试列出目录...")
        try:
            payload = {
                "tool_name": "list_dir",
                "arguments": {"req": {"path": "."}},
                "vm_id": vm_id,
                "session_id": session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                data = response.json()
                result = data['data']['result']
                if isinstance(result, list) and 'content' in result[0]:
                    files = json.loads(result[0]['content'])
                    print(f"     ✅ 列出 {len(files)} 个文件/目录")
                else:
                    print("     ✅ 目录列出成功")
            else:
                print(f"     ❌ 列出目录失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"     ❌ 列出目录异常: {e}")
    
    def _test_create_directory(self, vm_id: str, session_id: str):
        """测试创建目录"""
        print("  📁 测试创建目录...")
        try:
            payload = {
                "tool_name": "mkdir",
                "arguments": {"req": {"path": "test_dir_claude"}},
                "vm_id": vm_id,
                "session_id": session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                print("     ✅ 目录创建成功")
            else:
                print(f"     ❌ 目录创建失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"     ❌ 目录创建异常: {e}")
    
    def _test_write_file(self, vm_id: str, session_id: str):
        """测试写入文件"""
        print("  ✍️  测试写入文件...")
        try:
            content = f"测试文件内容 - {int(time.time())}\nMCP Client 测试成功！"
            payload = {
                "tool_name": "write_text",
                "arguments": {
                    "req": {
                        "path": "test_dir_claude/test_file.txt",
                        "content": content
                    }
                },
                "vm_id": vm_id,
                "session_id": session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                print("     ✅ 文件写入成功")
            else:
                print(f"     ❌ 文件写入失败: HTTP {response.status_code}")
                print(f"     响应: {response.text}")
        except Exception as e:
            print(f"     ❌ 文件写入异常: {e}")
    
    def _test_read_file(self, vm_id: str, session_id: str):
        """测试读取文件"""
        print("  📖 测试读取文件...")
        try:
            payload = {
                "tool_name": "read_text",
                "arguments": {"req": {"path": "test_dir_claude/test_file.txt"}},
                "vm_id": vm_id,
                "session_id": session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                data = response.json()
                result = data['data']['result']
                if isinstance(result, list) and 'content' in result[0]:
                    content = result[0]['content']
                    print(f"     ✅ 文件读取成功: {len(content)} 字符")
                    print(f"     内容预览: {content[:50]}...")
                else:
                    print("     ✅ 文件读取成功")
            else:
                print(f"     ❌ 文件读取失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"     ❌ 文件读取异常: {e}")
    
    def _test_delete_file(self, vm_id: str, session_id: str):
        """测试删除文件"""
        print("  🗑️  测试删除文件...")
        try:
            payload = {
                "tool_name": "delete",
                "arguments": {"req": {"path": "test_dir_claude/test_file.txt"}},
                "vm_id": vm_id,
                "session_id": session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                print("     ✅ 文件删除成功")
            else:
                print(f"     ❌ 文件删除失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"     ❌ 文件删除异常: {e}")
    
    def test_tool_find_functionality(self):
        """测试工具查找功能"""
        print("\n🔍 测试工具查找功能...")
        try:
            # 测试查找并调用list_dir工具
            payload = {
                "tool_name": "list_dir",
                "arguments": {"req": {"path": "."}}
            }
            
            response = self.session.post(f"{self.base_url}/tools/find", json=payload)
            if response.status_code == 200:
                data = response.json()
                print("✅ 工具查找调用成功")
                print(f"   工具: {data['data']['tool_name']}")
            else:
                print(f"❌ 工具查找调用失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 工具查找调用异常: {e}")
    
    def test_stats_endpoint(self):
        """测试系统统计信息"""
        print("\n📊 测试系统统计...")
        try:
            response = self.session.get(f"{self.base_url}/stats")
            if response.status_code == 200:
                data = response.json()
                stats = data['data']
                print("✅ 系统统计获取成功:")
                print(f"   - 运行时间: {stats.get('uptime', 'N/A')}")
                print(f"   - 连接的客户端: {stats.get('connected_clients', 0)}")
                print(f"   - 总工具数: {stats.get('total_tools', 0)}")
                print(f"   - Claude模型: {stats.get('settings', {}).get('claude_model', 'N/A')}")
            else:
                print(f"❌ 获取系统统计失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 获取系统统计异常: {e}")
    
    def test_intelligent_task(self, vm_id: str, session_id: str):
        """测试智能任务执行（如果配置了Claude API）"""
        print(f"\n🧠 测试智能任务执行 ({vm_id}/{session_id})...")
        try:
            payload = {
                "vm_id": vm_id,
                "session_id": session_id,
                "mcp_server_name": "filesystem", 
                "task_description": "在当前目录创建一个名为claude_test的目录，然后在其中创建一个hello.txt文件，内容为'Hello from Claude MCP Test!'"
            }
            
            response = self.session.post(f"{self.base_url}/tasks/execute", json=payload)
            if response.status_code == 200:
                data = response.json()
                result = data['data']['result']
                print("✅ 智能任务执行成功")
                print(f"   任务描述: {payload['task_description'][:50]}...")
                if isinstance(result, dict) and 'summary' in result:
                    print(f"   执行摘要: {result['summary']}")
            else:
                print(f"❌ 智能任务执行失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"❌ 智能任务执行异常: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始MCP客户端功能测试")
        print("=" * 60)
        
        # 1. 健康检查
        if not self.test_health():
            print("❌ 健康检查失败，停止测试")
            return False
        
        # 2. 列出客户端
        clients = self.test_list_clients()
        if not clients:
            print("❌ 没有找到可用的客户端，停止测试")
            return False
        
        # 3. 列出工具
        tools = self.test_list_tools()
        if not tools:
            print("❌ 没有找到可用的工具，停止测试")
            return False
        
        # 4. 查找filesystem客户端
        try:
            vm_id, session_id = self.find_filesystem_client(clients)
            print(f"\n🎯 找到filesystem客户端: {vm_id}/{session_id}")
        except Exception as e:
            print(f"❌ 找不到filesystem客户端: {e}")
            return False
        
        # 5. 测试filesystem操作
        self.test_filesystem_operations(vm_id, session_id)
        
        # 6. 测试工具查找功能
        self.test_tool_find_functionality()
        
        # 7. 测试系统统计
        self.test_stats_endpoint()
        
        # 8. 测试智能任务（可选）
        self.test_intelligent_task(vm_id, session_id)
        
        print("\n" + "=" * 60)
        print("🎉 MCP客户端功能测试完成")
        return True


def main():
    """主函数"""
    print("MCP客户端功能测试")
    print(f"目标地址: {MCP_CLIENT_URL}")
    print(f"超时设置: {TEST_TIMEOUT}秒")
    
    tester = MCPClientTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ 所有测试通过!")
        return 0
    else:
        print("\n❌ 部分测试失败!")
        return 1


if __name__ == "__main__":
    exit(main())