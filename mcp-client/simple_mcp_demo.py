#!/usr/bin/env python3
"""
简单的MCP客户端调用演示
包含三个核心功能：1、JSON注册 2、MCP客户端调用 3、文件同步
"""

import requests
import json
import os
import time
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

# 配置常量
MCP_BASE_DIR = "/home/ubuntu/workspace/gxw/useit_mcp_new/useit-mcp"
DEFAULT_MCP_CLIENT_URL = "http://localhost:8080"


def register_from_json(mcp_client_url: str, vm_id: str, session_id: str, json_path: str = None) -> bool:
    """从JSON文件注册MCP服务器"""
    print(f"📝 从JSON文件注册MCP服务器...")
    
    # 如果没有提供路径，使用默认路径
    if json_path is None:
        raise ValueError("JSON路径不能为空")
    
    json_file = Path(json_path)
    if not json_file.exists():
        print(f"❌ JSON注册文件不存在: {json_file}")
        print("💡 请先运行MCP服务器生成配置文件: ./start_simple_servers.sh start")
        return False
    
    print(f"📍 JSON文件路径: {json_file}")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        servers = data.get('servers', [])
        if not servers:
            print("❌ JSON文件中没有服务器配置")
            return False
        
        print(f"📊 发现 {len(servers)} 个服务器配置")
        success_count = 0
        
        for server in servers:
            server_name = server.get('name', 'unknown')
            server_url = server.get('url', '')
            
            print(f"   📡 注册服务器: {server_name} -> {server_url}")
            
            try:
                payload = {
                    "vm_id": vm_id,
                    "session_id": session_id,
                    "name": server_name,
                    "url": server_url,
                    "description": server.get('description', f'{server_name} MCP服务器'),
                    "transport": server.get('transport', 'http')
                }
                
                response = requests.post(f"{mcp_client_url}/clients", json=payload, timeout=10)
                if response.status_code == 200:
                    print(f"      ✅ {server_name} 注册成功")
                    success_count += 1
                else:
                    print(f"      ⚠️ {server_name} 注册响应: HTTP {response.status_code}")
                    if response.status_code == 400:
                        print(f"         (可能服务器已存在)")
                    success_count += 1  # 已存在也算成功
                    
            except Exception as e:
                print(f"      ❌ {server_name} 注册异常: {e}")
        
        print(f"✅ 成功注册 {success_count}/{len(servers)} 个服务器")
        return success_count > 0
        
    except Exception as e:
        print(f"❌ 处理JSON文件失败: {e}")
        return False


def call_mcp_client(
    mcp_client_url: str,
    vm_id: str, 
    session_id: str,
    mcp_server_name: str,
    task_description: str,
    context: str = None
) -> Tuple[bool, Dict[str, Any]]:
    """调用MCP客户端执行任务"""
    
    print(f"🧠 调用MCP客户端执行任务...")
    print(f"   📋 任务: {task_description}")
    print(f"   🎯 服务器: {mcp_server_name}")
    print(f"   📍 客户端: {vm_id}/{session_id}")
    
    try:
        # 构建任务请求
        task_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "mcp_server_name": mcp_server_name,
            "task_description": task_description
        }
        
        if context:
            task_request["context"] = context
        
        # 发送请求
        response = requests.post(
            f"{mcp_client_url}/tasks/execute",
            json=task_request,
            timeout=120
        )
        
        # 处理响应
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                data = result.get('data', {})
                task_result = data.get('result', {})
                
                success = task_result.get('success', False)
                execution_steps = task_result.get('execution_steps', [])
                final_result = task_result.get('final_result', '任务完成')
                summary = task_result.get('summary', '无摘要')
                
                print(f"✅ 任务完成")
                print(f"📊 执行状态: {success}")
                print(f"🔧 执行步骤: {len(execution_steps)} 步")
                
                # 显示执行步骤
                if execution_steps:
                    print("📋 执行步骤详情:")
                    for i, step in enumerate(execution_steps, 1):
                        tool_name = step.get('tool_name', 'unknown')
                        status = step.get('status', 'unknown')
                        status_emoji = "✅" if status == 'success' else "❌"
                        print(f"   {i}. {status_emoji} {tool_name}")
                
                print(f"📝 任务摘要: {summary}")
                print(f"🎯 最终结果: {final_result[:100]}{'...' if len(final_result) > 100 else ''}")
                
                return True, {
                    "success": success,
                    "execution_steps": execution_steps,
                    "final_result": final_result,
                    "summary": summary,
                    "step_count": len(execution_steps)
                }
            else:
                error_msg = result.get('message', '任务执行失败')
                print(f"❌ 任务执行失败: {error_msg}")
                return False, {"error": error_msg}
                
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            print(f"❌ 请求失败: {error_msg}")
            return False, {"error": error_msg}
            
    except Exception as e:
        error_msg = f"任务执行异常: {e}"
        print(f"❌ {error_msg}")
        return False, {"error": error_msg}


def call_mcp_client_streaming(
    mcp_client_url: str,
    vm_id: str, 
    session_id: str,
    mcp_server_name: str,
    task_description: str,
    context: str = None
) -> Tuple[bool, Dict[str, Any]]:
    """流式调用MCP客户端执行任务"""
    
    print(f"🌊 流式调用MCP客户端执行任务...")
    print(f"   📋 任务: {task_description}")
    print(f"   🎯 服务器: {mcp_server_name}")
    print(f"   📍 客户端: {vm_id}/{session_id}")
    print(f"   💡 实时显示执行进度...")
    print()
    
    try:
        # 构建任务请求
        task_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "mcp_server_name": mcp_server_name,
            "task_description": task_description
        }
        
        if context:
            task_request["context"] = context
        
        # 发送流式请求
        response = requests.post(
            f"{mcp_client_url}/tasks/execute-stream",
            json=task_request,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=(30, 300)  # 连接超时30秒，读取超时300秒
        )
        
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            print(f"❌ 流式请求失败: {error_msg}")
            return False, {"error": error_msg}
        
        # 处理SSE流
        task_result = {}
        execution_steps = []
        step_count = 0
        
        try:
            # 手动解析SSE流
            current_event = {}
            total_lines = 0
            total_events = 0
            
            print(f"📡 开始接收SSE流...")
            
            for line in response.iter_lines(decode_unicode=True):
                total_lines += 1
                
                if line is None:
                    continue
                    
                line = line.strip()
                
                # 调试：显示所有行数据
                if line:
                    print(f"🔍 原始行 #{total_lines}: '{line}'")
                
                if not line:
                    # 空行表示事件结束，处理当前事件
                    if current_event.get('data'):
                        total_events += 1
                        print(f"🎯 处理第 {total_events} 个事件: {current_event}")
                        
                        event_data = _process_sse_event(current_event)
                        if event_data:
                            result = _handle_sse_event(event_data, execution_steps)
                            if result:
                                return result
                    
                    current_event = {}
                    continue
                
                # 解析SSE字段
                if line.startswith('event:'):
                    # 如果有上一个事件未处理，先处理它
                    if current_event.get('data'):
                        total_events += 1
                        print(f"🎯 处理第 {total_events} 个事件: {current_event}")
                        event_data = _process_sse_event(current_event)
                        if event_data:
                            result = _handle_sse_event(event_data, execution_steps)
                            if result:
                                return result
                    
                    # 开始新事件
                    current_event = {'event': line[6:].strip()}
                elif line.startswith('data:'):
                    data_content = line[5:].strip()
                    if 'data' not in current_event:
                        current_event['data'] = data_content
                    else:
                        current_event['data'] += '\n' + data_content
                elif line.startswith('id:'):
                    current_event['id'] = line[3:].strip()
            
            # 处理最后一个事件（如果有的话）
            if current_event.get('data'):
                total_events += 1
                print(f"🎯 处理最后一个事件: {current_event}")
                event_data = _process_sse_event(current_event)
                if event_data:
                    result = _handle_sse_event(event_data, execution_steps)
                    if result:
                        return result
            
            # 如果流结束但没有收到完成事件
            print(f"⚠️ 流式连接结束")
            print(f"📊 统计: 处理了 {total_lines} 行数据, {total_events} 个事件")
            if total_events == 0:
                print(f"❌ 没有收到任何事件，可能服务器端有问题")
            else:
                print(f"⚠️ 收到了事件但没有完成事件")
            
            return False, {
                "error": "流式连接意外结束",
                "execution_steps": execution_steps,
                "debug_info": {
                    "total_lines": total_lines,
                    "total_events": total_events
                }
            }
            
        except Exception as e:
            print(f"❌ 处理SSE流失败: {e}")
            return False, {"error": f"处理SSE流失败: {e}"}
            
    except Exception as e:
        error_msg = f"流式任务执行异常: {e}"
        print(f"❌ {error_msg}")
        return False, {"error": error_msg}


def _process_sse_event(event: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """处理SSE事件数据"""
    try:
        if 'data' in event:
            return json.loads(event['data'])
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️ 解析事件数据失败: {e}")
        return None
    except Exception as e:
        print(f"⚠️ 处理事件失败: {e}")
        return None


def _handle_sse_event(event_data: Dict[str, Any], execution_steps: list) -> Optional[Tuple[bool, Dict[str, Any]]]:
    """处理单个SSE事件，返回结果（如果是完成或错误事件）"""
    event_type = event_data.get("type")
    data = event_data.get("data", {})
    
    # 打印原始JSON数据
    print(f"📡 收到事件: {json.dumps(event_data, ensure_ascii=False, indent=2)}")
    
    if event_type == "start":
        print(f"🚀 任务开始: {data.get('task_description', '')[:50]}...")
        task_id = data.get('task_id')
        print(f"   📍 任务ID: {task_id}")
    
    elif event_type == "tool_start":
        tool_name = data.get('tool_name', 'unknown')
        server_name = data.get('server_name', 'unknown')
        step_number = data.get('step_number', 'N/A')
        
        print(f"🔧 步骤 {step_number}: 开始执行工具")
        print(f"   🛠️  工具名称: {tool_name}")
        print(f"   📡 服务器: {server_name}")
    
    elif event_type == "tool_result":
        tool_name = data.get('tool_name', 'unknown')
        status = data.get('status', 'unknown')
        execution_time = data.get('execution_time', 0)
        step_number = data.get('step_number', 'N/A')
        
        status_emoji = "✅" if status == "success" else "❌"
        print(f"{status_emoji} 步骤 {step_number}: 工具执行完成")
        print(f"   🛠️  工具名称: {tool_name}")
        print(f"   ⏱️  执行时间: {execution_time:.2f}秒")
        print(f"   📊 状态: {status}")
        
        execution_steps.append({
            "step": step_number,
            "tool_name": tool_name,
            "status": status,
            "execution_time": execution_time,
            "result": data.get('result', '')
        })
    
    elif event_type == "complete":
        success = data.get('success', False)
        final_result = data.get('final_result', '')
        summary = data.get('summary', '')
        execution_time = data.get('execution_time', 0)
        total_steps = data.get('total_steps', 0)
        successful_steps = data.get('successful_steps', 0)
        new_files = data.get('new_files', {})
        
        print(f"🎯 任务完成!")
        print(f"   ✅ 执行状态: {'成功' if success else '失败'}")
        print(f"   ⏱️  总执行时间: {execution_time:.2f}秒")
        print(f"   📊 执行统计: {successful_steps}/{total_steps} 步骤成功")
        
        task_result = {
            "success": success,
            "execution_steps": execution_steps,
            "final_result": final_result,
            "summary": summary,
            "execution_time": execution_time,
            "step_count": len(execution_steps),
            "new_files": new_files
        }
        
        return success, task_result
    
    elif event_type == "error":
        error_message = data.get('error_message', '未知错误')
        error_type = data.get('error_type', '未知错误类型')
        
        print(f"❌ 任务执行错误:")
        print(f"   🚨 错误类型: {error_type}")
        print(f"   📝 错误信息: {error_message}")
        
        return False, {
            "error": error_message,
            "error_type": error_type,
            "execution_steps": execution_steps
        }
    
    print()  # 事件之间的分隔
    return None


def sync_files_to_target(
    mcp_client_url: str,
    vm_id: str,
    session_id: str,
    target_base_path: str,
    sync_strategy: str = "size_hash",
    dry_run: bool = True
) -> bool:
    """同步文件到目标目录"""
    print(f"📁 执行文件同步...")
    print(f"   🎯 目标路径: {target_base_path}")
    print(f"   🔧 同步策略: {sync_strategy}")
    print(f"   📋 预演模式: {dry_run}")
    
    try:
        sync_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "target_base_path": target_base_path,
            "sync_strategy": sync_strategy,
            "dry_run": dry_run,
            "force_sync": False,
            "chunk_size": 8192
        }
        
        # 调用同步工具
        tool_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "tool_name": "sync_files_to_target",
            "arguments": {
                "req": sync_request
            }
        }
        
        response = requests.post(
            f"{mcp_client_url}/tools/call",
            json=tool_request,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                data = result.get("data", {})
                print(f"✅ 文件同步成功")
                
                # 显示同步摘要
                summary = data.get("sync_summary", {})
                if summary:
                    total_files = summary.get('total_files', 0)
                    synced = summary.get('synced', 0)
                    skipped = summary.get('skipped', 0)
                    errors = summary.get('errors', 0)
                    
                    print(f"📊 同步统计: 总文件{total_files}, 需同步{synced}, 跳过{skipped}, 错误{errors}")
                    
                    if summary.get('target_path'):
                        print(f"🎯 目标路径: {summary['target_path']}")
                
                # 显示同步的文件
                synced_files = data.get("synced_files", [])
                if synced_files:
                    print(f"📂 同步文件 ({len(synced_files)} 个):")
                    for file in synced_files[:5]:  # 显示前5个
                        print(f"  - {file}")
                    if len(synced_files) > 5:
                        print(f"  ... 还有 {len(synced_files) - 5} 个文件")
                
                return True
            else:
                print(f"❌ 文件同步失败: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP错误 {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 文件同步异常: {e}")
        return False


def check_mcp_client_status(mcp_client_url: str) -> bool:
    """检查MCP客户端状态"""
    print("🔍 检查MCP客户端状态...")
    
    try:
        response = requests.get(f"{mcp_client_url}/health", timeout=5)
        if response.status_code == 200:
            result = response.json()
            status_data = result.get('data', {})
            
            print("✅ MCP客户端运行正常")
            print(f"   📡 已连接服务器: {status_data.get('connected_servers', 0)}")
            print(f"   🔧 可用工具数: {status_data.get('total_tools', 0)}")
            
            return True
        else:
            print(f"⚠️ MCP客户端响应异常: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到MCP客户端: {mcp_client_url}")
        print("   请启动MCP客户端: cd mcp-client && python server.py")
        return False
    except Exception as e:
        print(f"❌ 状态检查异常: {e}")
        return False


def main():
    """主函数 - 演示三个核心功能"""
    print("🚀 MCP客户端调用演示")
    print("=" * 60)
    
    # 配置参数
    mcp_client_url = DEFAULT_MCP_CLIENT_URL
    vm_id = "demo_vm"
    session_id = "demo_session"
    json_path = "/home/ubuntu/workspace/gxw/useit_mcp_new/useit_mcp_test_dir/.useit/mcp_server_frp.json"
    target_sync_path = "/tmp/mcp_sync_demo"
    
    print(f"🎯 配置信息:")
    print(f"   📡 MCP客户端URL: {mcp_client_url}")
    print(f"   📍 VM ID: {vm_id}")
    print(f"   📍 Session ID: {session_id}")
    print(f"   📄 JSON配置文件: {json_path}")
    print()
    
    # 步骤0: 检查MCP客户端状态
    print("=" * 40)
    print("📋 步骤0: 检查MCP客户端状态")
    print("=" * 40)
    if not check_mcp_client_status(mcp_client_url):
        print("\n❌ MCP客户端连接失败，演示终止")
        return
    
    # 步骤1: JSON注册
    print("\n" + "=" * 40)
    print("📋 步骤1: 从JSON文件注册服务器")
    print("=" * 40)
    registration_success = register_from_json(mcp_client_url, vm_id, session_id, json_path)
    
    if not registration_success:
        print("\n⚠️ 服务器注册失败，但继续演示...")
    
    # 步骤2: MCP客户端调用
    print("\n" + "=" * 40)
    print("📋 步骤2: 调用MCP客户端执行任务")
    print("=" * 40)
    
    task_description = "读取pdf文件的内容，并且把pdf的内容写到一个pdf_content.txt文件中。"
    mcp_server_name = "filesystem"
    
    # 询问用户选择调用方式
    print("请选择调用方式:")
    print("1. 普通调用 (一次性返回结果)")
    print("2. 流式调用 (实时显示执行进度)")
    
    try:
        # choice = input("请输入选择 (1-2, 默认1): ").strip() or "1"
        choice = "2"
        
        if choice == "2":
            print("\n🌊 使用流式调用方式...")
            call_success, result = call_mcp_client_streaming(
                mcp_client_url=mcp_client_url,
                vm_id=vm_id,
                session_id=session_id,
                mcp_server_name=mcp_server_name,
                task_description=task_description,
                context="演示MCP客户端流式调用功能"
            )
        else:
            print("\n📞 使用普通调用方式...")
            call_success, result = call_mcp_client(
                mcp_client_url=mcp_client_url,
                vm_id=vm_id,
                session_id=session_id,
                mcp_server_name=mcp_server_name,
                task_description=task_description,
                context="演示MCP客户端调用功能"
            )
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消操作，使用默认普通调用方式")
        call_success, result = call_mcp_client(
            mcp_client_url=mcp_client_url,
            vm_id=vm_id,
            session_id=session_id,
            mcp_server_name=mcp_server_name,
            task_description=task_description,
            context="演示MCP客户端调用功能"
        )
    
    # 步骤3: 文件同步
    print("\n" + "=" * 40)
    print("📋 步骤3: 文件同步演示")
    print("=" * 40)
    
    # 先进行预演
    print("📋 预演模式...")
    sync_success_dry = sync_files_to_target(
        mcp_client_url=mcp_client_url,
        vm_id=vm_id,
        session_id=session_id,
        target_base_path=target_sync_path,
        sync_strategy="size_hash",
        dry_run=True
    )
    
    # 如果预演成功，进行实际同步
    if sync_success_dry:
        print("\n📁 实际同步...")
        sync_success = sync_files_to_target(
            mcp_client_url=mcp_client_url,
            vm_id=vm_id,
            session_id=session_id,
            target_base_path=target_sync_path,
            sync_strategy="size_hash",
            dry_run=False
        )
    else:
        sync_success = False
    
    # 总结
    print("\n" + "=" * 40)
    print("📊 演示总结")
    print("=" * 40)
    
    print(f"1️⃣ JSON注册: {'✅ 成功' if registration_success else '❌ 失败'}")
    print(f"2️⃣ MCP客户端调用: {'✅ 成功' if call_success else '❌ 失败'}")
    print(f"3️⃣ 文件同步: {'✅ 成功' if sync_success else '❌ 失败'}")
    
    if registration_success and call_success and sync_success:
        print("\n🎉 所有功能演示成功！")
        print("\n💡 现在你可以:")
        print("  - 使用register_from_json()注册MCP服务器")
        print("  - 使用call_mcp_client()执行智能任务")
        print("  - 使用sync_files_to_target()同步文件")
    else:
        print("\n⚠️ 部分功能需要进一步配置")
        print("💡 请检查:")
        print("  - MCP服务器是否正常运行")
        print("  - JSON配置文件是否存在")
        print("  - 网络连接和权限设置")


if __name__ == "__main__":
    main()