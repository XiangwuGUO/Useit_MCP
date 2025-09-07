#!/usr/bin/env python3
"""
MCP客户端FRP模式功能测试脚本
专门测试基于JSON文件注册的FRP模式
需要手动指定vm_id和session_id参数
"""

import asyncio
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List

import requests

# 配置
MCP_CLIENT_URL = "http://localhost:8080"
TEST_TIMEOUT = 10

class MCPClientFRPTester:
    """MCP客户端FRP模式测试器"""
    
    def __init__(self, base_url: str = MCP_CLIENT_URL, vm_id: str = "", session_id: str = ""):
        self.base_url = base_url.rstrip('/')
        self.vm_id = vm_id
        self.session_id = session_id
        self.session = requests.Session()
        self.session.timeout = TEST_TIMEOUT
        
        if not vm_id or not session_id:
            raise ValueError("vm_id和session_id参数是必需的")
    
    def test_json_file_exists(self) -> bool:
        """测试JSON注册文件是否存在"""
        print("\n📄 检查JSON注册文件...")
        json_file = Path("../mcp_server_frp.json")
        
        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"✅ 找到JSON注册文件: {json_file}")
                print(f"   VM ID: {data.get('vm_id', 'N/A')}")
                print(f"   Session ID: {data.get('session_id', 'N/A')}")
                print(f"   服务器数量: {len(data.get('servers', []))}")
                
                # 检查是否包含当前测试的vm_id和session_id
                if data.get('vm_id') == self.vm_id and data.get('session_id') == self.session_id:
                    print("✅ JSON文件包含匹配的vm_id和session_id")
                    return True
                else:
                    print("⚠️ JSON文件中的vm_id/session_id与测试参数不匹配")
                    print(f"   文件中: {data.get('vm_id')}/{data.get('session_id')}")
                    print(f"   测试用: {self.vm_id}/{self.session_id}")
                    return False
                    
            except Exception as e:
                print(f"❌ 读取JSON文件失败: {e}")
                return False
        else:
            print(f"❌ 未找到JSON注册文件: {json_file}")
            print("💡 请先运行 'start_simple_servers.sh start-frp <vm_id> <session_id>' 生成注册文件")
            return False
    
    def test_manual_registration(self) -> bool:
        """测试手动注册JSON文件中的服务器"""
        print(f"\n📝 测试手动注册服务器 (VM: {self.vm_id}, Session: {self.session_id})...")
        
        json_file = Path("../mcp_server_frp.json")
        if not json_file.exists():
            print("❌ JSON注册文件不存在")
            return False
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            servers = data.get('servers', [])
            if not servers:
                print("❌ JSON文件中没有服务器配置")
                return False
            
            success_count = 0
            for server in servers:
                print(f"  📡 注册服务器: {server['name']}...")
                try:
                    payload = {
                        "vm_id": self.vm_id,
                        "session_id": self.session_id,
                        "name": server['name'],
                        "url": server['url'],
                        "description": server.get('description', ''),
                        "transport": server.get('transport', 'http')
                    }
                    
                    response = self.session.post(f"{self.base_url}/clients", json=payload)
                    if response.status_code == 200:
                        print(f"     ✅ {server['name']} 注册成功")
                        success_count += 1
                    else:
                        print(f"     ❌ {server['name']} 注册失败: HTTP {response.status_code}")
                        if response.text:
                            print(f"     响应: {response.text}")
                            
                except Exception as e:
                    print(f"     ❌ {server['name']} 注册异常: {e}")
            
            print(f"\n✅ 成功注册 {success_count}/{len(servers)} 个服务器")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ 处理JSON文件失败: {e}")
            return False
    
    def test_health(self) -> bool:
        """测试健康检查"""
        print(f"\n🏥 测试健康检查 (VM: {self.vm_id}, Session: {self.session_id})...")
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
        """测试列出所有客户端，重点关注指定的vm_id/session_id"""
        print(f"\n📋 测试列出客户端 (查找 {self.vm_id}/{self.session_id})...")
        try:
            response = self.session.get(f"{self.base_url}/clients")
            if response.status_code == 200:
                data = response.json()
                clients = data['data']
                print(f"✅ 获取到 {len(clients)} 个客户端:")
                
                target_found = False
                for client in clients:
                    client_id = f"{client['vm_id']}/{client['session_id']}"
                    status_icon = "🎯" if client['vm_id'] == self.vm_id and client['session_id'] == self.session_id else "  "
                    server_count = client.get('server_count', 0)
                    connected_count = len(client.get('connected_servers', []))
                    
                    print(f"{status_icon} - {client_id}: {client['status']} (服务器: {connected_count}/{server_count})")
                    
                    # 显示服务器详情
                    if 'servers' in client and client['servers']:
                        for server in client['servers']:
                            connected_icon = "✅" if server['connected'] else "❌"
                            print(f"     {connected_icon} {server['name']}: {server['url']}")
                            if server['description']:
                                print(f"        描述: {server['description']}")
                    
                    if client['vm_id'] == self.vm_id and client['session_id'] == self.session_id:
                        target_found = True
                        print(f"     ✅ 找到目标客户端: {client_id}")
                        print(f"     ℹ️ 工具数: {client.get('tool_count', 0)}, 资源数: {client.get('resource_count', 0)}")
                
                if not target_found:
                    print(f"⚠️ 未找到指定的客户端: {self.vm_id}/{self.session_id}")
                
                return clients
            else:
                print(f"❌ 获取客户端列表失败: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ 获取客户端列表异常: {e}")
            return []
    
    def test_list_tools(self) -> List[Dict[str, Any]]:
        """测试列出所有工具，重点关注指定vm_id/session_id的工具"""
        print(f"\n🔧 测试列出工具 (过滤 {self.vm_id}/{self.session_id})...")
        try:
            response = self.session.get(f"{self.base_url}/tools")
            if response.status_code == 200:
                data = response.json()
                all_tools = data['data']
                
                # 过滤指定vm_id/session_id的工具
                target_tools = [
                    tool for tool in all_tools 
                    if tool['vm_id'] == self.vm_id and tool['session_id'] == self.session_id
                ]
                
                print(f"✅ 总工具数: {len(all_tools)}, 目标客户端工具: {len(target_tools)}")
                
                if target_tools:
                    # 按服务器分组显示
                    servers = {}
                    for tool in target_tools:
                        server_name = tool.get('server_name', 'unknown')
                        if server_name not in servers:
                            servers[server_name] = []
                        servers[server_name].append(tool)
                    
                    print(f"   [{self.vm_id}/{self.session_id}]的工具 (按服务器分组):")
                    for server_name, tools in servers.items():
                        print(f"     💻 {server_name}:")
                        for tool in tools:
                            print(f"       - {tool['name']}: {tool.get('description', 'N/A')}")
                else:
                    print(f"❌ 未找到 {self.vm_id}/{self.session_id} 的工具")
                
                return target_tools
            else:
                print(f"❌ 获取工具列表失败: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ 获取工具列表异常: {e}")
            return []
    
    def test_filesystem_operations(self):
        """测试filesystem服务器操作"""
        print(f"\n📁 测试filesystem操作 ({self.vm_id}/{self.session_id})...")
        
        # 测试列出目录
        self._test_list_directory()
        
        # 测试创建目录
        self._test_create_directory()
        
        # 测试写入文件
        self._test_write_file()
        
        # 测试读取文件
        self._test_read_file()
        
        # 测试删除文件
        self._test_delete_file()
    
    def _test_list_directory(self):
        """测试列出目录内容"""
        print("  📂 测试列出目录...")
        try:
            payload = {
                "tool_name": "list_dir",
                "arguments": {"req": {"path": "."}},
                "vm_id": self.vm_id,
                "session_id": self.session_id
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
                print(f"     响应: {response.text}")
        except Exception as e:
            print(f"     ❌ 列出目录异常: {e}")
    
    def _test_create_directory(self):
        """测试创建目录"""
        print("  📁 测试创建目录...")
        try:
            payload = {
                "tool_name": "mkdir",
                "arguments": {"req": {"path": "test_dir_claude_frp"}},
                "vm_id": self.vm_id,
                "session_id": self.session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                print("     ✅ 目录创建成功")
            else:
                print(f"     ❌ 目录创建失败: HTTP {response.status_code}")
                print(f"     响应: {response.text}")
        except Exception as e:
            print(f"     ❌ 目录创建异常: {e}")
    
    def _test_write_file(self):
        """测试写入文件"""
        print("  ✍️  测试写入文件...")
        try:
            content = f"FRP测试文件内容 - {int(time.time())}\nVM: {self.vm_id}\nSession: {self.session_id}\nMCP Client FRP 测试成功！"
            payload = {
                "tool_name": "write_text",
                "arguments": {
                    "req": {
                        "path": "test_dir_claude_frp/test_file_frp.txt",
                        "content": content
                    }
                },
                "vm_id": self.vm_id,
                "session_id": self.session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                print("     ✅ 文件写入成功")
            else:
                print(f"     ❌ 文件写入失败: HTTP {response.status_code}")
                print(f"     响应: {response.text}")
        except Exception as e:
            print(f"     ❌ 文件写入异常: {e}")
    
    def _test_read_file(self):
        """测试读取文件"""
        print("  📖 测试读取文件...")
        try:
            payload = {
                "tool_name": "read_text",
                "arguments": {"req": {"path": "test_dir_claude_frp/test_file_frp.txt"}},
                "vm_id": self.vm_id,
                "session_id": self.session_id
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
                print(f"     响应: {response.text}")
        except Exception as e:
            print(f"     ❌ 文件读取异常: {e}")
    
    def _test_delete_file(self):
        """测试删除文件"""
        print("  🗑️  测试删除文件...")
        try:
            payload = {
                "tool_name": "delete",
                "arguments": {"req": {"path": "test_dir_claude_frp/test_file_frp.txt"}},
                "vm_id": self.vm_id,
                "session_id": self.session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/call", json=payload)
            if response.status_code == 200:
                print("     ✅ 文件删除成功")
            else:
                print(f"     ❌ 文件删除失败: HTTP {response.status_code}")
                print(f"     响应: {response.text}")
        except Exception as e:
            print(f"     ❌ 文件删除异常: {e}")
    
    def test_tool_find_functionality(self):
        """测试工具查找功能"""
        print(f"\n🔍 测试工具查找功能 ({self.vm_id}/{self.session_id})...")
        try:
            # 测试查找并调用list_dir工具
            payload = {
                "tool_name": "list_dir",
                "arguments": {"req": {"path": "."}},
                "vm_id": self.vm_id,
                "session_id": self.session_id
            }
            
            response = self.session.post(f"{self.base_url}/tools/find", json=payload)
            if response.status_code == 200:
                data = response.json()
                print("✅ 工具查找调用成功")
                print(f"   工具: {data['data']['tool_name']}")
                print(f"   客户端: {data['data'].get('vm_id', 'N/A')}/{data['data'].get('session_id', 'N/A')}")
            else:
                print(f"❌ 工具查找调用失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
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
    
    def test_intelligent_task(self):
        """测试智能任务执行（如果配置了Claude API）"""
        print(f"\n🧠 测试智能任务执行 ({self.vm_id}/{self.session_id})...")
        try:
            payload = {
                "vm_id": self.vm_id,
                "session_id": self.session_id,
                "mcp_server_name": "filesystem",
                "task_description": f"在当前目录创建一个名为claude_frp_test的目录，然后在其中创建一个hello_frp.txt文件，内容为'Hello from Claude MCP FRP Test! VM: {self.vm_id}, Session: {self.session_id}'"
            }
            
            response = self.session.post(f"{self.base_url}/tasks/execute", json=payload)
            if response.status_code == 200:
                data = response.json()
                result = data['data']['result']
                print("✅ 智能任务执行成功")
                print(f"   任务描述: {payload['task_description'][:80]}...")
                if isinstance(result, dict) and 'summary' in result:
                    print(f"   执行摘要: {result['summary']}")
            else:
                print(f"❌ 智能任务执行失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"❌ 智能任务执行异常: {e}")
    
    def test_frp_connectivity(self):
        """测试FRP隧道连通性"""
        print(f"\n🌐 测试FRP隧道连通性 ({self.vm_id}/{self.session_id})...")
        
        json_file = Path("../mcp_server_frp.json")
        if not json_file.exists():
            print("❌ JSON注册文件不存在，无法测试FRP连通性")
            return
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            servers = data.get('servers', [])
            for server in servers:
                if server.get('frp_enabled') and server.get('public_url'):
                    print(f"  🔗 测试 {server['name']} 的FRP隧道...")
                    try:
                        # 测试健康检查端点
                        health_url = server['public_url'].replace('/mcp', '/health')
                        response = requests.get(health_url, timeout=5)
                        if response.status_code == 200:
                            print(f"     ✅ FRP隧道连通: {server['public_url']}")
                        else:
                            print(f"     ⚠️ FRP隧道响应异常: HTTP {response.status_code}")
                    except Exception as e:
                        print(f"     ❌ FRP隧道连接失败: {e}")
                else:
                    print(f"  📍 {server['name']}: 仅本地模式")
                    
        except Exception as e:
            print(f"❌ 测试FRP连通性失败: {e}")
    
    def run_all_tests(self):
        """运行所有FRP模式测试"""
        print("🚀 开始MCP客户端FRP模式功能测试")
        print(f"🎯 目标客户端: {self.vm_id}/{self.session_id}")
        print("=" * 60)
        
        # 1. 检查JSON文件
        if not self.test_json_file_exists():
            print("❌ JSON注册文件检查失败，建议先生成注册文件")
            return False
        
        # 2. 健康检查
        if not self.test_health():
            print("❌ 健康检查失败，停止测试")
            return False
        
        # 3. 手动注册服务器（模拟安全通道传输后的注册过程）
        print("\n🔄 模拟通过安全通道传输JSON文件并注册服务器...")
        if not self.test_manual_registration():
            print("❌ 服务器注册失败，停止测试")
            return False
        
        # 等待注册完成
        time.sleep(2)
        
        # 4. 列出客户端
        clients = self.test_list_clients()
        if not any(c['vm_id'] == self.vm_id and c['session_id'] == self.session_id for c in clients):
            print(f"❌ 未找到目标客户端 {self.vm_id}/{self.session_id}，停止测试")
            return False
        
        # 5. 列出工具
        tools = self.test_list_tools()
        if not tools:
            print(f"❌ 未找到目标客户端的工具，停止测试")
            return False
        
        # 6. 测试filesystem操作
        self.test_filesystem_operations()
        
        # 7. 测试工具查找功能
        self.test_tool_find_functionality()
        
        # 8. 测试系统统计
        self.test_stats_endpoint()
        
        # 9. 测试FRP隧道连通性
        self.test_frp_connectivity()
        
        # 10. 测试智能任务（可选）
        self.test_intelligent_task()
        
        print("\n" + "=" * 60)
        print("🎉 MCP客户端FRP模式功能测试完成")
        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MCP客户端FRP模式功能测试')
    parser.add_argument('--vm-id', required=True, help='虚拟机ID (必需)')
    parser.add_argument('--session-id', required=True, help='会话ID (必需)')
    parser.add_argument('--client-url', default=MCP_CLIENT_URL, help=f'MCP客户端地址 (默认: {MCP_CLIENT_URL})')
    parser.add_argument('--timeout', type=int, default=TEST_TIMEOUT, help=f'请求超时时间 (默认: {TEST_TIMEOUT}秒)')
    
    args = parser.parse_args()
    
    print("MCP客户端FRP模式功能测试")
    print(f"目标地址: {args.client_url}")
    print(f"VM ID: {args.vm_id}")
    print(f"Session ID: {args.session_id}")
    print(f"超时设置: {args.timeout}秒")
    
    try:
        tester = MCPClientFRPTester(
            base_url=args.client_url,
            vm_id=args.vm_id,
            session_id=args.session_id
        )
        success = tester.run_all_tests()
        
        if success:
            print("\n✅ 所有FRP测试通过!")
            return 0
        else:
            print("\n❌ 部分FRP测试失败!")
            return 1
            
    except Exception as e:
        print(f"\n❌ 测试初始化失败: {e}")
        return 1


if __name__ == "__main__":
    exit(main())