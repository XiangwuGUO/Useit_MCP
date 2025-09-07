#!/usr/bin/env python3
"""
MCP Gateway Server 演示脚本

展示如何使用新的统一MCP网关服务器进行各种操作
"""

import asyncio
import base64
import json
from datetime import datetime
from typing import Dict, Any

import httpx

# 配置
GATEWAY_URL = "http://localhost:8080"
DEMO_VM_ID = "demo-vm-001"
DEMO_SESSION_ID = "demo-session-001"

# MCP服务器配置
MCP_SERVERS = [
    {
        "name": "FileSystem",
        "url": "http://localhost:8003",
        "description": "文件系统操作服务器"
    },
    {
        "name": "AudioSlicer", 
        "url": "http://localhost:8002",
        "description": "音频切片处理服务器"
    },
    {
        "name": "WebSearch",
        "url": "http://localhost:8004", 
        "description": "网页搜索服务器"
    }
]

# 演示任务
DEMO_TASKS = [
    {
        "name": "文件系统基础操作",
        "server": "FileSystem",
        "description": "创建一个测试目录，在里面创建一个hello.txt文件，内容是当前时间的问候语"
    },
    {
        "name": "项目结构创建",
        "server": "FileSystem", 
        "description": "创建一个完整的Python项目结构，包含src目录、tests目录、README.md文件和requirements.txt文件"
    },
    {
        "name": "网页搜索测试",
        "server": "WebSearch",
        "description": "搜索'Python FastAPI最佳实践'并保存结果到文件"
    },
    {
        "name": "数据处理任务",
        "server": "FileSystem",
        "description": "创建一个data目录，在里面创建sample.json文件，包含一些示例数据，然后读取这个文件并创建一个summary.txt总结文件内容"
    }
]


class MCPGatewayDemo:
    """MCP网关演示类"""
    
    def __init__(self, gateway_url: str = GATEWAY_URL):
        self.gateway_url = gateway_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def setup_demo(self) -> bool:
        """设置演示环境"""
        print("🔧 设置演示环境...")
        
        try:
            # 1. 检查服务器状态 (先检查根路径，如果health有问题)
            root_response = await self.client.get(f"{self.gateway_url}/")
            if root_response.status_code == 200:
                root_data = root_response.json()
                print(f"   ✅ Gateway服务器运行正常: {root_data['data']['version']}")
                
                # 尝试health检查，如果失败也继续
                try:
                    health_response = await self.client.get(f"{self.gateway_url}/health")
                    if health_response.status_code == 200:
                        health_data = health_response.json()
                        print(f"   ✅ 健康检查: {health_data['data']['status']}")
                    else:
                        print(f"   ⚠️ 健康检查有问题，但继续运行演示")
                except:
                    print(f"   ⚠️ 健康检查失败，但服务器运行正常，继续演示")
            else:
                print(f"   ❌ Gateway服务器无法访问: {root_response.status_code}")
                return False
            
            # 2. 添加所有MCP服务器
            success_count = 0
            for i, server in enumerate(MCP_SERVERS):
                print(f"   📡 添加 {server['name']} 服务器...")
                
                # 为每个服务器使用不同的session_id
                session_id = f"{DEMO_SESSION_ID}-{server['name'].lower()}"
                
                client_info = {
                    "vm_id": DEMO_VM_ID,
                    "session_id": session_id,
                    "remote_url": server["url"],
                    "description": server["description"]
                }
                
                response = await self.client.post(f"{self.gateway_url}/clients", json=client_info)
                if response.status_code == 200:
                    print(f"      ✅ {server['name']} 服务器添加成功")
                    success_count += 1
                else:
                    print(f"      ⚠️ {server['name']} 添加失败: {response.status_code}")
                    # 检查是否已存在
                    status_response = await self.client.get(
                        f"{self.gateway_url}/clients/{DEMO_VM_ID}/{session_id}/status"
                    )
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data['data']['status'] == 'connected':
                            print(f"      ✅ {server['name']} 已存在且连接正常")
                            success_count += 1
                        else:
                            print(f"      ❌ {server['name']} 状态异常: {status_data['data']['status']}")
            
            if success_count == 0:
                print("   ❌ 没有可用的MCP服务器")
                return False
            
            # 3. 验证工具可用性
            all_tools = []
            for server in MCP_SERVERS:
                session_id = f"{DEMO_SESSION_ID}-{server['name'].lower()}"
                try:
                    tools_response = await self.client.get(
                        f"{self.gateway_url}/clients/{DEMO_VM_ID}/{session_id}/tools"
                    )
                    if tools_response.status_code == 200:
                        tools_data = tools_response.json()
                        tools = tools_data['data']['tools']
                        all_tools.extend([(server['name'], tool) for tool in tools])
                        print(f"   📋 {server['name']}: {len(tools)} 个工具")
                except Exception as e:
                    print(f"   ⚠️ {server['name']} 工具获取失败: {e}")
            
            print(f"   ✅ 总共发现 {len(all_tools)} 个可用工具")
            
            # 显示工具摘要
            print("   🔧 工具摘要:")
            for server_name, tool in all_tools[:8]:
                desc = tool.get('description', 'No description')[:40] + "..." if len(tool.get('description', '')) > 40 else tool.get('description', 'No description')
                print(f"      [{server_name}] {tool['name']}: {desc}")
            if len(all_tools) > 8:
                print(f"      ... 还有 {len(all_tools) - 8} 个工具")
            
            print("✅ 演示环境设置完成\n")
            return True
            
        except Exception as e:
            print(f"   ❌ 设置演示环境失败: {e}")
            return False
    
    async def run_basic_demo(self):
        """运行基础功能演示"""
        print("📋 基础功能演示")
        print("=" * 50)
        
        # 1. 系统状态
        print("\n1. 📊 系统状态查询")
        try:
            response = await self.client.get(f"{self.gateway_url}/stats")
            if response.status_code == 200:
                stats = response.json()['data']
                print(f"   运行时间: {stats['uptime_formatted']}")
                print(f"   连接客户机: {stats['total_clients']}")
                print(f"   可用工具: {stats['total_tools']}")
                print(f"   可用资源: {stats['total_resources']}")
            else:
                print(f"   ❌ 获取系统状态失败: {response.status_code}")
        except Exception as e:
            print(f"   ❌ 系统状态查询异常: {e}")
        
        # 2. 客户机管理
        print("\n2. 🖥️ 客户机管理")
        try:
            response = await self.client.get(f"{self.gateway_url}/clients")
            if response.status_code == 200:
                clients = response.json()['data']
                print(f"   客户机列表: {clients['clients']}")
                print(f"   客户机数量: {clients['count']}")
            else:
                print(f"   ❌ 获取客户机列表失败: {response.status_code}")
        except Exception as e:
            print(f"   ❌ 客户机查询异常: {e}")
        
        # 3. 简单工具调用演示
        print("\n3. 🔧 工具调用演示")
        
        # 测试FileSystem服务器的get_base工具
        print("   📁 测试FileSystem服务器...")
        try:
            fs_session_id = f"{DEMO_SESSION_ID}-filesystem"
            tool_call = {
                "tool_name": "get_base",
                "arguments": {"session_id": fs_session_id},
                "vm_id": DEMO_VM_ID,
                "session_id": fs_session_id
            }
            
            response = await self.client.post(f"{self.gateway_url}/tools/call", json=tool_call)
            if response.status_code == 200:
                result = response.json()['data']
                print(f"      ✅ FileSystem工具调用成功")
                print(f"      基础目录: {result.get('result', 'Unknown')}")
            else:
                print(f"      ❌ FileSystem工具调用失败: {response.status_code}")
        except Exception as e:
            print(f"      ❌ FileSystem工具调用异常: {e}")
        
    
    async def run_intelligent_task_demo(self):
        """运行智能任务演示"""
        print("\n🧠 智能任务执行演示")
        print("=" * 50)
        
        for i, task in enumerate(DEMO_TASKS, 1):
            print(f"\n任务 {i}: {task['name']}")
            print(f"描述: {task['description']}")
            print("-" * 40)
            
            # 构建任务请求
            server_session_id = f"{DEMO_SESSION_ID}-{task['server'].lower()}"
            task_request = {
                "vm_id": DEMO_VM_ID,
                "session_id": server_session_id,
                "mcp_server_name": task['server'],
                "task_description": task['description'],
                "max_steps": 10
            }
            
            start_time = datetime.now()
            
            try:
                response = await self.client.post(
                    f"{self.gateway_url}/tasks/execute",
                    json=task_request
                )
                
                if response.status_code == 200:
                    result = response.json()
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    print(f"✅ 任务执行成功!")
                    print(f"⏱️  执行时间: {execution_time:.2f}秒")
                    print(f"📊 步骤数量: {len(result['execution_steps'])}")
                    
                    # 显示执行步骤
                    print("\n🔧 执行步骤:")
                    for step in result['execution_steps']:
                        status_icon = "✅" if step.get('status') == 'success' else "❌"
                        print(f"   {status_icon} 步骤{step.get('step', 0)}: {step.get('tool_name', 'Unknown')}")
                        if step.get('reasoning'):
                            reasoning = step['reasoning'][:80] + "..." if len(step['reasoning']) > 80 else step['reasoning']
                            print(f"      💭 {reasoning}")
                    
                    # 显示摘要
                    print(f"\n📄 任务摘要:")
                    summary_lines = result['summary'].split('\n')
                    for line in summary_lines[:10]:  # 只显示前10行
                        if line.strip():
                            print(f"   {line}")
                    if len(summary_lines) > 10:
                        print("   ...")
                    
                else:
                    print(f"❌ 任务执行失败: {response.status_code}")
                    print(f"错误: {response.text}")
                
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                print(f"❌ 任务执行异常: {e}")
                print(f"⏱️  执行时间: {execution_time:.2f}秒")
            
            # 任务间间隔
            if i < len(DEMO_TASKS):
                print("\n⏸️  等待2秒后执行下一个任务...")
                await asyncio.sleep(2)
    
    async def run_audio_demo(self):
        """运行音频切片演示"""
        print("\n🎵 音频处理演示")
        print("=" * 50)
        
        # 创建一个简单的测试音频文件(使用sine波生成)
        print("📁 生成测试音频文件...")
        
        try:
            # 生成简单的正弦波音频数据并转换为base64
            import numpy as np
            import wave
            import tempfile
            
            # 生成2秒的440Hz正弦波
            sample_rate = 44100
            duration = 2.0
            frequency = 440.0
            
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio_data = np.sin(frequency * 2 * np.pi * t)
            audio_data = (audio_data * 32767).astype(np.int16)
            
            # 写入临时wav文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                with wave.open(tmp_file.name, 'w') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data.tobytes())
                
                # 读取文件并转换为base64
                with open(tmp_file.name, 'rb') as audio_file:
                    audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
            
            print("   ✅ 测试音频文件生成完成")
            
            # 调用音频切片工具
            session_id = f"{DEMO_SESSION_ID}-audioslicer"
            tool_call = {
                "tool_name": "slice_audio",
                "arguments": {
                    "audio_file_content_base64": audio_base64,
                    "filename": "test_audio.wav",
                    "segment_duration_s": 0.5
                },
                "vm_id": DEMO_VM_ID,
                "session_id": session_id
            }
            
            print("🔪 调用音频切片工具...")
            response = await self.client.post(f"{self.gateway_url}/tools/call", json=tool_call)
            
            if response.status_code == 200:
                result = response.json()['data']
                print("   ✅ 音频切片成功!")
                print(f"   🔍 调试信息: {type(result)} - {result}")
                
                # 修复字符串索引错误 - result可能是字符串而不是字典
                tool_result = result.get('result') if isinstance(result, dict) else result
                
                if isinstance(tool_result, dict) and 'segment_paths' in tool_result:
                    segments = tool_result['segment_paths']
                    print(f"   📂 生成了 {len(segments)} 个音频片段")
                    for i, path in enumerate(segments[:3]):  # 只显示前3个
                        print(f"      - 片段 {i+1}: {path}")
                    if len(segments) > 3:
                        print(f"      ... 还有 {len(segments) - 3} 个片段")
                elif isinstance(tool_result, str):
                    # 如果结果是字符串，尝试解析为JSON
                    try:
                        import json
                        parsed_result = json.loads(tool_result)
                        if 'segment_paths' in parsed_result:
                            segments = parsed_result['segment_paths']
                            print(f"   📂 生成了 {len(segments)} 个音频片段")
                        else:
                            print(f"   📄 解析结果: {parsed_result}")
                    except:
                        print(f"   📄 字符串结果: {tool_result}")
                else:
                    print(f"   📄 原始结果: {tool_result}")
            else:
                print(f"   ❌ 音频切片失败: {response.status_code} - {response.text}")
                
        except ImportError:
            print("   ⚠️ 缺少numpy依赖，跳过音频演示")
        except Exception as e:
            print(f"   ❌ 音频演示失败: {e}")
    
    async def cleanup_demo(self):
        """清理演示环境"""
        print("\n🧹 清理演示环境...")
        
        # 清理所有服务器的客户机连接
        for server in MCP_SERVERS:
            session_id = f"{DEMO_SESSION_ID}-{server['name'].lower()}"
            try:
                response = await self.client.delete(
                    f"{self.gateway_url}/clients/{DEMO_VM_ID}/{session_id}"
                )
                if response.status_code == 200:
                    print(f"   ✅ {server['name']} 客户机移除成功")
                else:
                    print(f"   ⚠️ {server['name']} 移除失败: {response.status_code}")
            except Exception as e:
                print(f"   ❌ 清理 {server['name']} 时出现问题: {e}")
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


async def main():
    """主演示函数"""
    print("🎯 MCP Gateway Server 演示")
    print("=" * 60)
    print()
    print("此演示将展示统一MCP网关服务器的核心功能：")
    print("1. 多服务器客户机连接管理")
    print("2. 跨服务器工具调用")
    print("3. 音频处理功能演示")
    print("4. 智能任务执行")
    print("5. 系统监控和状态管理")
    print()
    print("🛠️  测试的MCP服务器:")
    for server in MCP_SERVERS:
        print(f"   - {server['name']}: {server['description']} ({server['url']})")
    print()
    
    demo = MCPGatewayDemo()
    
    try:
        # 设置环境
        if not await demo.setup_demo():
            print("❌ 演示环境设置失败，退出演示")
            return
        
        # 运行基础功能演示
        await demo.run_basic_demo()
        
        # 运行音频处理演示
        await demo.run_audio_demo()
        
        # 运行智能任务演示
        await demo.run_intelligent_task_demo()
        
        print(f"\n{'=' * 60}")
        print("🎊 演示完成!")
        print("\n💡 关键功能:")
        print("✅ 多服务器支持 - 同时管理FileSystem、AudioSlicer、WebSearch服务器")
        print("✅ 统一网关接口 - 所有MCP服务器通过一个端点访问")
        print("✅ 智能任务执行 - 自动选择合适的工具完成复杂任务")
        print("✅ 跨服务器协作 - 不同服务器的工具可以配合使用")
        print("✅ 实时状态监控 - 监控所有连接的MCP服务器状态")
        print("✅ 完善的错误处理 - 单个服务器故障不影响其他服务器")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ 演示被用户中断")
    except Exception as e:
        print(f"\n❌ 演示执行失败: {e}")
    finally:
        # 清理环境
        await demo.cleanup_demo()
        await demo.close()


if __name__ == "__main__":
    import os
    
    # 检查环境变量
    missing_vars = []
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing_vars.append("ANTHROPIC_API_KEY (智能任务执行需要)")
    
    if not os.getenv("OPENAI_API_KEY"):
        missing_vars.append("OPENAI_API_KEY (网页搜索需要)")
    
    if missing_vars:
        print("⚠️ 警告: 缺少以下环境变量:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        print("设置方法:")
        print("   export ANTHROPIC_API_KEY='your_claude_api_key'")
        print("   export OPENAI_API_KEY='your_openai_api_key'")
        print()
        print("🔄 继续运行演示，但某些功能可能不可用...")
        print()
    
    asyncio.run(main())