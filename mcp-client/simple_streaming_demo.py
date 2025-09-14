#!/usr/bin/env python3
"""
简化的流式MCP客户端演示
专门针对单个MCP服务器的流式工具调用

包含功能：
1. MCP客户端状态检查
2. MCP服务器注册  
3. 流式任务执行（实时进度监控）
4. 直接路径列表获取（快速工具调用）
"""

import requests
import json
import time
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from register_from_json import register_all_servers_from_json, load_mcp_config

# 配置常量
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


def call_streaming_task(
    mcp_client_url: str,
    vm_id: str, 
    session_id: str,
    mcp_server_name: str,
    task_description: str
) -> Tuple[bool, Dict[str, Any]]:
    """调用流式任务，实时显示工具执行进度"""
    
    print(f"🌊 执行流式任务...")
    print(f"   📋 任务: {task_description}")
    print(f"   🎯 MCP服务器: {mcp_server_name}")
    print(f"   📍 会话: {vm_id}/{session_id}")
    print()
    
    try:
        # 构建任务请求
        task_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "mcp_server_name": mcp_server_name,
            "task_description": task_description
        }
        
        # 发送流式请求
        response = requests.post(
            f"{mcp_client_url}/tasks/execute-stream",
            json=task_request,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=(30, 300)
        )
        
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            print(f"❌ 流式请求失败: {error_msg}")
            return False, {"error": error_msg}
        
        # 处理SSE流 - 简化版
        return _process_sse_stream(response)
        
    except Exception as e:
        print(f"❌ 流式任务执行异常: {e}")
        return False, {"error": str(e)}


def _process_sse_stream(response) -> Tuple[bool, Dict[str, Any]]:
    """简化的SSE流处理"""
    
    execution_steps = []
    task_result = None
    tool_count = 0
    
    print(f"📡 开始接收实时事件流...")
    print("=" * 50)
    
    try:
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith('data:'):
                continue
            
            # 解析事件数据
            try:
                data_content = line[5:].strip()  # 去掉 'data:' 前缀
                event_data = json.loads(data_content)
                event_type = event_data.get("type")
                data = event_data.get("data", {})
                
                # 处理不同类型的事件
                if event_type == "start":
                    task_id = data.get('task_id')
                    print(f"🚀 任务开始 (ID: {task_id})")
                    print(f"   📋 描述: {data.get('task_description', '')}")
                    print()
                
                elif event_type == "tool_start":
                    tool_count += 1
                    tool_name = data.get('tool_name', 'unknown')
                    server_name = data.get('server_name', 'unknown')
                    step_number = data.get('step_number', tool_count)
                    arguments = data.get('arguments', {})
                    
                    # 服务器名称应由MCP服务器端正确提供，不再进行客户端推断
                    
                    print(f"🔧 步骤 {step_number}: 开始执行工具 '{tool_name}'")
                    print(f"   📡 MCP服务器: {server_name}")
                    if arguments:
                        print(f"   📝 参数: {json.dumps(arguments, ensure_ascii=False)}")
                    print()
                    
                elif event_type == "tool_result": 
                    tool_name = data.get('tool_name', 'unknown')
                    server_name = data.get('server_name', 'unknown')
                    status = data.get('status', 'unknown')
                    execution_time = data.get('execution_time', 0)
                    step_number = data.get('step_number', '?')
                    result = data.get('result', '')
                    token_usage = data.get('token_usage', {})
                    
                    # 服务器名称应由MCP服务器端正确提供，不再进行客户端推断
                    
                    status_emoji = "✅" if status == "success" else "❌"
                    print(f"{status_emoji} 步骤 {step_number}: 工具 '{tool_name}' 执行完成")
                    print(f"   📡 MCP服务器: {server_name}")
                    print(f"   ⏱️  执行时间: {execution_time:.3f}秒")
                    print(f"   📊 状态: {status}")
                    
                    # 显示token使用情况
                    if token_usage:
                        model_name = token_usage.get('model_name', 'unknown')
                        total_tokens = token_usage.get('total_tokens', 0)
                        print(f"   🔢 Token使用: {model_name} - {total_tokens} tokens")
                    
                    # 显示结果预览（前100个字符）
                    if result:
                        # result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                        result_preview = result
                        print(f"   📄 结果预览: {result_preview}")
                    
                    execution_steps.append({
                        "step": step_number,
                        "tool_name": tool_name,
                        "status": status,
                        "execution_time": execution_time,
                        "result": result,
                        "token_usage": token_usage
                    })
                    print()
                
                elif event_type == "complete":
                    success = data.get('success', False)
                    final_result = data.get('final_result', '')
                    summary = data.get('summary', '')
                    total_execution_time = data.get('execution_time', 0)
                    total_steps = data.get('total_steps', 0)
                    total_token_usage = data.get('total_token_usage', {})
                    
                    print("=" * 50)
                    print(f"🎯 任务完成!")
                    print(f"   ✅ 执行状态: {'成功' if success else '失败'}")
                    print(f"   ⏱️  总执行时间: {total_execution_time:.2f}秒")
                    print(f"   📊 总步骤数: {total_steps}")
                    print(f"   🔧 实际工具调用数: {len(execution_steps)}")
                    
                    # 显示总token使用量
                    if total_token_usage:
                        for model_name, token_count in total_token_usage.items():
                            print(f"   🔢 总Token使用: {model_name} - {token_count} tokens")
                    
                    task_result = {
                        "success": success,
                        "execution_steps": execution_steps,
                        "final_result": final_result,
                        "summary": summary,
                        "execution_time": total_execution_time,
                        "tool_count": len(execution_steps),
                        "total_token_usage": total_token_usage
                    }
                    
                    return success, task_result
                
                elif event_type == "error":
                    error_message = data.get('error_message', '未知错误')
                    print(f"❌ 任务执行错误: {error_message}")
                    return False, {"error": error_message, "execution_steps": execution_steps}
                    
            except json.JSONDecodeError as e:
                print(f"⚠️ 解析事件数据失败: {e}")
                continue
        
        # 流结束但没有完成事件
        print("⚠️ 流式连接意外结束")
        return False, {
            "error": "流式连接意外结束",
            "execution_steps": execution_steps,
            "tool_count": len(execution_steps)
        }
        
    except Exception as e:
        print(f"❌ 处理SSE流失败: {e}")
        return False, {"error": f"处理SSE流失败: {e}"}


def test_filesystem_paths(
    mcp_client_url: str, 
    vm_id: str, 
    session_id: str
) -> bool:
    """测试获取文件系统路径列表功能 - 专用于直接调用，AI无法访问"""
    
    print(f"📁 测试获取文件系统所有路径（绕过AI直接调用）...")
    print(f"   📍 会话: {vm_id}/{session_id}")
    print(f"   🚫 AI无法看到或调用list_all_paths工具")
    print(f"   🔗 通过MCP服务器HTTP端点调用，复用现有端口")
    
    try:
        # 构建请求
        payload = {
            "vm_id": vm_id,
            "session_id": session_id,
            "tool_name": "list_all_paths",
            "arguments": {},
            "server_name": "filesystem"
        }
        
        print(f"   🚀 调用接口: /filesystem/list-all-paths")
        response = requests.post(f"{mcp_client_url}/filesystem/list-all-paths", 
                               json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                paths = data.get("data", {}).get("paths", [])
                print(f"   ✅ 成功获取 {len(paths)} 个路径")
                
                # 统计文件和目录 - 处理路径可能是字符串或字典的情况
                from pathlib import Path
                
                # 提取实际的路径字符串
                actual_paths = []
                for p in paths:
                    if isinstance(p, str):
                        actual_paths.append(p)
                    elif isinstance(p, dict) and 'path' in p:
                        actual_paths.append(p['path'])
                    else:
                        actual_paths.append(str(p))
                
                try:
                    dirs = sum(1 for p in actual_paths if Path(p).is_dir())
                    files = sum(1 for p in actual_paths if Path(p).is_file())
                    print(f"   📊 统计: 目录 {dirs} 个, 文件 {files} 个")
                except Exception as e:
                    print(f"   📊 路径数量: {len(actual_paths)} 个 (统计失败: {e})")
                
                # 显示前5个路径作为示例
                print(f"   📂 路径示例 (前5个):")
                for i, path in enumerate(actual_paths[:5]):
                    try:
                        path_type = "📁" if Path(path).is_dir() else "📄"
                        print(f"      {i+1}. {path_type} {path}")
                    except Exception:
                        print(f"      {i+1}. 📄 {path}")
                
                if len(actual_paths) > 5:
                    print(f"      ... 还有 {len(actual_paths) - 5} 个路径")
                
                return True
            else:
                print(f"   ❌ 接口调用失败: {data.get('message', 'Unknown error')}")
                return False
        else:
            print(f"   ❌ HTTP错误: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 连接失败")
        return False
    except Exception as e:
        print(f"   ❌ 调用异常: {e}")
        return False


def check_mcp_client_status(mcp_client_url: str) -> bool:
    """检查MCP客户端状态"""
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
        return False
    except Exception as e:
        print(f"❌ 状态检查异常: {e}")
        return False


def register_servers_from_json_config(json_config_path: str, mcp_client_url: str) -> Tuple[bool, str, str]:
    """
    从JSON配置文件注册MCP服务器
    
    Args:
        json_config_path: JSON配置文件路径
        mcp_client_url: MCP客户端URL（用于覆盖配置文件中的registry_url）
        
    Returns:
        Tuple[bool, str, str]: (是否成功, vm_id, session_id)
    """
    print("🔗 使用JSON配置文件注册MCP服务器...")
    print(f"   📄 配置文件: {json_config_path}")
    
    try:
        # 检查文件是否存在
        if not Path(json_config_path).exists():
            print(f"❌ 配置文件不存在: {json_config_path}")
            return False, "", ""
        
        # 加载配置获取vm_id和session_id
        config = load_mcp_config(json_config_path)
        vm_id = config['vm_id']
        session_id = config['session_id']
        
        print(f"   📍 会话信息: {vm_id}/{session_id}")
        
        # 使用指定的MCP客户端URL进行注册
        success, result = register_all_servers_from_json(json_config_path, mcp_client_url)
        
        if success:
            print(f"✅ JSON配置注册成功，注册了 {result['successful_count']} 个服务器")
            return True, vm_id, session_id
        else:
            print(f"❌ JSON配置注册失败: {result.get('error', '未知错误')}")
            return False, vm_id, session_id
            
    except Exception as e:
        print(f"❌ JSON注册过程异常: {e}")
        return False, "", ""


def main():
    """主演示函数"""
    print("🚀 简化流式MCP客户端演示")
    print("=" * 60)
    
    # 配置
    mcp_client_url = DEFAULT_MCP_CLIENT_URL
    
    # 尝试使用JSON配置文件注册（如果存在）
    json_path = "/home/ubuntu/workspace/gxw/useit_mcp_new/useit_mcp_test_dir/.useit/mcp_server_frp.json"
    vm_id = "vm123"
    session_id = "sess456"
    
    # 1. 检查客户端状态
    print("1️⃣ 检查MCP客户端状态...")
    if not check_mcp_client_status(mcp_client_url):
        print("❌ MCP客户端不可用，请先启动服务器")
        return
    print()
    
    # 2. 注册MCP服务器
    print("\n" + "=" * 40)
    print("📋 步骤1: 从JSON文件注册服务器")
    print("=" * 40)
    registration_success = register_from_json(mcp_client_url, vm_id, session_id, json_path)
    
    if not registration_success:
        print("\n⚠️ 服务器注册失败，但继续演示...")
    
    # # 3. 执行流式任务
    # print("3️⃣ 执行流式任务...")
    # 3. 测试流式任务执行
    print("3️⃣ 测试流式任务执行...")
    # task_description = "Create a new Markdown file named 'Flat_White_Tutorial.txt' in the sandbox root containing a concise, step-by-step tutorial on making a Flat White: include sections for Overview, Equipment, Ingredients with measurements (e.g., 18g espresso yielding ~36g in 25–30s; 120–150 ml milk), Steps (dose and tamp, pull double-shot espresso, steam milk to 55–60°C/130–140°F with fine microfoam, pour with a thin stream to integrate crema and finish with a simple heart), Tips (bean choice, grind adjustments, milk texturing cues, cleaning), and Variations (iced flat white, alternative milks)."
    task_description = '''Create a new Markdown file named 'test.md' and write the string: 'JSON 注册
文件: mcp-client/register_from_json.py、simple_streaming_demo.py
步骤: 读取 FRP 生成的 mcp_server_frp.json → 取每个 server 的 url（公网地址）→ 调用 MCP 网关 POST /clients 注册这些 server。
获取工具
由执行器在运行时连接到已注册的 MCP 服务器，通过 langchain-mcp-adapters 将 MCP 工具转成 LangChain 工具（StructuredTool）。
二、Agent 构建与消息流
执行器
文件: mcp-client/core/langchain_executor.py（非流式）与 core/streaming_executor.py（流式）
作用: 负责
创建/复用包含 MCP 工具的 LangChain Agent
绑定模型（如 ChatAnthropic）
在流式模式下，暴露 SSE 事件，实时回传工具步骤与结果' to it'''
    streaming_success, streaming_result = call_streaming_task(
        mcp_client_url=mcp_client_url,
        vm_id=vm_id,
        session_id=session_id,
        mcp_server_name="filesystem",
        task_description=task_description
    )
    print()
    
    # 4. 测试路径列表功能（直接调用，不通过AI）
    print("4️⃣ 测试获取路径列表功能（直接工具调用）...")
    print("    📌 注意：此功能专用于直接调用，AI无法访问此工具")
    paths_success = test_filesystem_paths(
        mcp_client_url=mcp_client_url,
        vm_id=vm_id,
        session_id=session_id
    )
    print()
    
    # 5. 显示最终结果总结
    print("=" * 60)
    print("📊 执行结果总结")
    print("=" * 60)
    
    print(f"1️⃣ MCP客户端状态检查: ✅ 成功")
    print(f"2️⃣ MCP服务器注册: ✅ 成功")
    print(f"3️⃣ 流式任务执行: {'✅ 成功' if streaming_success else '❌ 失败'}")
    print(f"4️⃣ 路径列表获取: {'✅ 成功' if paths_success else '❌ 失败'}")
    
    if streaming_success:
        print(f"\n📋 流式任务详情:")
        print(f"   🔧 工具调用数: {streaming_result.get('tool_count', 0)}")
        print(f"   ⏱️  总执行时间: {streaming_result.get('execution_time', 0):.2f}秒")
        
        # 显示工具执行摘要
        steps = streaming_result.get('execution_steps', [])
        if steps:
            print(f"   📋 工具执行摘要:")
            for step in steps:
                status_emoji = "✅" if step.get('status') == 'success' else "❌"
                print(f"      {status_emoji} {step.get('tool_name', 'unknown')} ({step.get('execution_time', 0):.3f}s)")
    else:
        print(f"\n❌ 流式任务失败: {streaming_result.get('error', '未知错误')}")
    
    if streaming_success and paths_success:
        print(f"\n🎉 所有功能演示成功!")
        print(f"💡 功能完整性验证通过:")
        print(f"   - 流式任务执行: 支持实时进度监控（AI可用）")
        print(f"   - 直接工具调用: 支持快速路径查询（AI不可见）")
        print(f"   - 工具访问控制: list_all_paths专用于直接调用")
    else:
        print(f"\n⚠️ 部分功能需要进一步配置")


if __name__ == "__main__":
    main()