import requests
import json
import os
from typing import Optional, Dict, Any
from pathlib import Path


def register_from_json(mcp_client_url: str, vm_id: str, session_id: str) -> bool:
    """从JSON文件注册服务器到MCP客户端"""
    json_file = Path("../mcp_server_frp.json")
    
    if not json_file.exists():
        print(f"❌ JSON注册文件不存在: {json_file}")
        return False
    # 输出json_file的完整地址
    print(f"JSON文件地址: {json_file}")
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        servers = data.get('servers', [])
        if not servers:
            print("❌ JSON文件中没有服务器配置")
            return False
        
        print(f"📝 从JSON文件注册 {len(servers)} 个服务器...")
        success_count = 0
        
        for server in servers:
            print(f"  📡 注册服务器: {server['name']}...")
            try:
                payload = {
                    "vm_id": vm_id,
                    "session_id": session_id,
                    "name": server['name'],
                    "url": server['url'],
                    "description": server.get('description', ''),
                    "transport": server.get('transport', 'http')
                }
                
                response = requests.post(f"{mcp_client_url}/clients", json=payload)
                if response.status_code == 200:
                    print(f"     ✅ {server['name']} 注册成功")
                    success_count += 1
                else:
                    print(f"     ❌ {server['name']} 注册失败: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"     ❌ {server['name']} 注册异常: {e}")
        
        print(f"✅ 成功注册 {success_count}/{len(servers)} 个服务器")
        return success_count > 0
        
    except Exception as e:
        print(f"❌ 处理JSON文件失败: {e}")
        return False


def _register_servers_with_vm_session(mcp_client_url: str, vm_id: str, session_id: str) -> bool:
    """
    Register MCP servers from JSON file with specified vm_id and session_id
    
    Args:
        mcp_client_url: URL of the MCP client server
        vm_id: Virtual machine ID
        session_id: Session ID
        
    Returns:
        bool: True if registration successful
    """
    return register_from_json(mcp_client_url, vm_id, session_id)




def _calling_external_mcp_server(instruction_text: str, mcp_server_name: str, vm_id: str, session_id: str, mcp_client_url: Optional[str] = None) -> tuple:
    """
    Call external MCP server with smart tool call and return completion summary
    
    Args:
        instruction_text: The task description for the tool
        mcp_server_name: The name of the MCP server to call (e.g. filesystem, audio_slicer)
        vm_id: Virtual machine ID (required)
        session_id: Session ID (required)  
        mcp_client_url: URL of the external MCP server

    Returns:
        tuple: (is_completed, completion_summary, token_usage)
    """
    try:
        # Use config value if URL not provided
        if mcp_client_url is None:
            mcp_client_url = 'http://localhost:8080'
        
        print(f"Calling external MCP server at {mcp_client_url}")
        print(f"Smart server call: {mcp_server_name} - {instruction_text}")
        print(f"Target client: {vm_id}/{session_id}")
        
        # Prepare request data for smart tool call
        request_data = {
            "mcp_server_name": mcp_server_name,
            "task_description": instruction_text,
            "vm_id": vm_id,
            "session_id": session_id
        }
        
        # Make HTTP request to MCP server smart-call endpoint
        response = requests.post(
            f"{mcp_client_url}/tools/smart-call",
            json=request_data,
            timeout=60
        )
        
        # Check response status
        if response.status_code != 200:
            error_msg = f"MCP server returned status {response.status_code}: {response.text}"
            print(error_msg)
            return False, f"Error calling MCP server: {error_msg}", {}
        
        # Parse response
        response_data = response.json()  
        # Expected response_data format:
        # {
        #     "success": True,
        #     "message": "智能工具调用成功",
        #     "data": {
        #         "success": True,
        #         "tool_name": "write_text",
        #         "completion_summary": "Completion summary",
        #         "token_usage": {
        #             "model_name": 100
        #         },
        #         "result": {...}
        #     }
        # }
        
        is_success = response_data.get('success', False)
        if is_success and 'data' in response_data:
            data = response_data['data']
            is_completed = data.get('success', False)
            completion_summary = data.get('completion_summary', 'No completion summary provided')
            token_usage = data.get('token_usage', {})
            selected_tool = data.get('selected_tool_name', 'N/A')
            
            print(f"Smart server call completed: {completion_summary}")
            print(f"Selected tool: {selected_tool}")
            if token_usage:
                print(f"Token usage: {token_usage}")
            
            return is_completed, completion_summary, token_usage
        else:
            return False, response_data.get('message', 'Unknown error'), {}


    except Exception as e:
        error_msg = f"Unexpected error calling MCP server: {str(e)}"
        print(error_msg)
        return False, f"Error: {error_msg}", {}


def check_source_files_status(mcp_client_url: str, vm_id: str, session_id: str):
    """检查客户机端的源文件状态"""
    print("🔍 检查客户机端源文件状态...")
    
    try:
        # 获取BASE_DIR路径
        tool_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "tool_name": "get_base",
            "arguments": {}
        }
        
        response = requests.post(
            f"{mcp_client_url}/tools/call",
            json=tool_request,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                base_dir = result.get("data", "未知")
                print(f"  📁 客户机BASE_DIR: {base_dir}")
            else:
                print("  ❌ 无法获取BASE_DIR信息")
        
        # 列出源目录文件
        list_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "tool_name": "list_dir",
            "arguments": {
                "path": ".",
                "recursive": True,
                "files_only": True
            }
        }
        
        response = requests.post(
            f"{mcp_client_url}/tools/call",
            json=list_request,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                data = result.get("data", {})
                entries = data.get("entries", [])
                
                if entries:
                    print(f"  📂 找到 {len(entries)} 个文件:")
                    for entry in entries[:5]:  # 显示前5个
                        size = entry.get('size', 0)
                        size_str = f"{size / 1024:.1f}KB" if size else "0B"
                        print(f"    - {entry.get('relative', entry.get('name', 'N/A'))} ({size_str})")
                    
                    if len(entries) > 5:
                        print(f"    ... 还有 {len(entries) - 5} 个文件")
                else:
                    print("  📂 客户机BASE_DIR中没有文件可同步")
                    print("  💡 提示: 请在客户机的BASE_DIR中放置一些文件进行测试")
            else:
                print("  ❌ 无法列出源目录文件")
        
    except Exception as e:
        print(f"  ❌ 检查源文件状态异常: {e}")


def test_file_sync_functionality(mcp_client_url: str, vm_id: str, session_id: str) -> bool:
    """测试文件同步功能"""
    print("\n📁 步骤3: 测试文件同步功能")
    print("-" * 40)
    
    # 先检查客户机端的BASE_DIR状态
    check_source_files_status(mcp_client_url, vm_id, session_id)
    
    # 目标路径（服务器端）
    target_base_path = "/mnt/efs/data/useit/users_workspace"
    
    # 测试不同的同步策略
    strategies = [
        ("size_hash", "大小+MD5哈希策略 (默认推荐)"),
        ("hash", "SHA256哈希策略 (高安全性)")
    ]
    
    sync_success = False
    
    for strategy, description in strategies:
        print(f"\n🧪 测试 {description}")
        
        # 预演模式测试
        print("  📋 预演模式...")
        sync_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "target_base_path": target_base_path,
            "sync_strategy": strategy,
            "dry_run": True,
            "force_sync": False,
            "chunk_size": 8192
        }
        
        success = call_sync_tool(mcp_client_url, sync_request, f"{strategy} (预演)")
        
        if success and strategy == "size_hash":  # 对默认策略进行实际同步
            print("  📁 实际同步...")
            sync_request["dry_run"] = False
            actual_success = call_sync_tool(mcp_client_url, sync_request, f"{strategy} (实际)")
            if actual_success:
                sync_success = True
        elif success and strategy != "size_hash":
            sync_success = True
    
    # 同步完成后，检查目标目录
    if sync_success:
        check_target_files_status(target_base_path, vm_id, session_id)
    
    return sync_success


def check_target_files_status(target_base_path: str, vm_id: str, session_id: str):
    """检查目标目录的文件状态"""
    print("\n🔍 检查同步目标目录...")
    
    target_dir = Path(target_base_path) / f"{vm_id}_{session_id}" / "mcp_files"
    
    try:
        if target_dir.exists():
            files = list(target_dir.rglob("*"))
            file_list = [f for f in files if f.is_file()]
            
            if file_list:
                print(f"  ✅ 目标目录存在: {target_dir}")
                print(f"  📂 同步的文件 ({len(file_list)} 个):")
                
                for file_path in file_list[:5]:  # 显示前5个
                    try:
                        relative_path = file_path.relative_to(target_dir)
                        size = file_path.stat().st_size
                        size_str = f"{size / 1024:.1f}KB" if size else "0B"
                        print(f"    - {relative_path} ({size_str})")
                    except Exception as e:
                        print(f"    - {file_path.name} (读取信息失败: {e})")
                
                if len(file_list) > 5:
                    print(f"    ... 还有 {len(file_list) - 5} 个文件")
                    
                # 显示总大小
                total_size = sum(f.stat().st_size for f in file_list if f.is_file())
                print(f"  📊 总大小: {total_size / 1024:.1f}KB")
                
            else:
                print(f"  📂 目标目录存在但为空: {target_dir}")
        else:
            print(f"  ❌ 目标目录不存在: {target_dir}")
            print(f"  💡 这可能表示同步未实际执行或路径配置错误")
            
    except Exception as e:
        print(f"  ❌ 检查目标目录异常: {e}")


def call_sync_tool(mcp_client_url: str, sync_request: Dict[str, Any], test_name: str) -> bool:
    """调用文件同步工具"""
    try:
        # 直接调用工具 - 需要将参数包装在req字段中
        tool_request = {
            "vm_id": sync_request["vm_id"],
            "session_id": sync_request["session_id"],
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
            print(f"    🔍 调试: 响应数据 = {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if result.get("success"):
                data = result.get("data", {})
                print(f"    ✅ {test_name} 成功")
                
                # 获取消息
                message = data.get('message') or result.get('message', 'N/A')
                print(f"    📄 {message}")
                
                # 解析同步摘要
                summary = data.get("sync_summary", {})
                if summary:
                    print(f"    📊 统计: 总文件{summary.get('total_files', 0)}, "
                          f"需同步{summary.get('synced', 0)}, "
                          f"跳过{summary.get('skipped', 0)}, "
                          f"错误{summary.get('errors', 0)}")
                    
                    if summary.get('target_path'):
                        print(f"    🎯 目标路径: {summary['target_path']}")
                        
                    if not summary.get('dry_run', True):
                        print(f"    💾 实际同步完成!")
                else:
                    print("    📊 未找到同步摘要信息")
                
                # 显示同步的文件列表
                synced_files = data.get("synced_files", [])
                if synced_files:
                    print(f"    📂 同步文件 ({len(synced_files)} 个):")
                    for i, file in enumerate(synced_files[:5]):  # 显示前5个
                        print(f"      - {file}")
                    if len(synced_files) > 5:
                        print(f"      ... 还有 {len(synced_files) - 5} 个文件")
                else:
                    print("    📂 没有需要同步的文件")
                
                # 显示跳过的文件
                skipped_files = data.get("skipped_files", [])
                if skipped_files:
                    print(f"    ⏭️  跳过文件 ({len(skipped_files)} 个):")
                    for i, file in enumerate(skipped_files[:3]):
                        print(f"      - {file}")
                    if len(skipped_files) > 3:
                        print(f"      ... 还有 {len(skipped_files) - 3} 个文件")
                
                # 显示错误文件
                error_files = data.get("error_files", [])
                if error_files:
                    print(f"    ❌ 错误文件 ({len(error_files)} 个):")
                    for error in error_files[:2]:
                        print(f"      - {error.get('file', 'N/A')}: {error.get('error', 'N/A')}")
                
                return True
            else:
                print(f"    ❌ {test_name} 失败: {result.get('message', 'Unknown error')}")
                print(f"    🔍 完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
                return False
        else:
            print(f"    ❌ HTTP错误 {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"    ❌ 测试异常 ({test_name}): {e}")
        return False


def check_mcp_client_status(mcp_client_url: str) -> bool:
    """检查MCP客户端状态"""
    try:
        # 检查健康状态
        response = requests.get(f"{mcp_client_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ MCP客户端运行正常")
        else:
            print(f"⚠️ MCP客户端响应异常: {response.status_code}")
            return False
            
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到MCP客户端: {mcp_client_url}")
        print("   请启动MCP客户端: cd mcp-client && python server.py")
        return False
    except Exception as e:
        print(f"❌ 状态检查异常: {e}")
        return False


def show_test_summary(registration_success: bool, smart_call_success: bool, sync_success: bool):
    """显示测试总结"""
    print("\n" + "=" * 60)
    print("📊 完整测试结果汇总:")
    print("=" * 60)
    
    print(f"1️⃣  服务器注册: {'✅ 成功' if registration_success else '❌ 失败'}")
    print(f"2️⃣  智能工具调用: {'✅ 成功' if smart_call_success else '❌ 失败'}")  
    print(f"3️⃣  文件同步功能: {'✅ 成功' if sync_success else '❌ 失败'}")
    
    all_success = registration_success and smart_call_success and sync_success
    
    if all_success:
        print(f"\n🎉 所有测试通过！MCP系统运行正常")
        print("\n💡 你现在可以:")
        print("  - 通过MCP客户端调用各种工具")
        print("  - 使用文件同步功能保持客户机和服务器文件一致")
        print("  - 开发更多自定义MCP服务器扩展功能")
    else:
        print(f"\n⚠️  部分测试失败，请检查:")
        if not registration_success:
            print("  - 客户机MCP服务器是否正常运行")
            print("  - FRP配置文件是否正确生成")
        if not smart_call_success:
            print("  - MCP客户端与服务器的连接")
            print("  - 工具调用的参数和权限")
        if not sync_success:
            print("  - 文件系统权限和路径配置")
            print("  - 同步目标目录是否可访问")




if __name__ == "__main__":
    # 配置参数
    mcp_client_url = 'http://localhost:8080'
    vm_id = "vm123"
    session_id = "sess456"
    instruction_text = "创建一个c++的hello world cpp程序。"
    mcp_server_name = "filesystem"
    
    print("🚀 MCP系统完整功能测试")
    print(f"🎯 目标客户端: {vm_id}/{session_id}")
    print(f"🌐 MCP客户端: {mcp_client_url}")
    print("=" * 60)
    
    # 0. 检查MCP客户端状态
    print("🔍 步骤0: 检查MCP客户端状态")
    if not check_mcp_client_status(mcp_client_url):
        print("\n❌ MCP客户端连接失败，无法继续测试")
        exit(1)
    
    # 1. 注册服务器
    print("\n📝 步骤1: 注册MCP服务器")
    registration_success = _register_servers_with_vm_session(mcp_client_url, vm_id, session_id)
    
    if not registration_success:
        print("❌ 服务器注册失败，无法继续测试")
        exit(1)
    
    # 2. 调用智能工具
    print("\n🧠 步骤2: 执行智能工具调用") 
    is_completed, completion_summary, token_usage = _calling_external_mcp_server(
        instruction_text, 
        mcp_server_name, 
        vm_id,
        session_id,
        mcp_client_url
    )
    
    print(f"  📊 智能工具调用结果:")
    print(f"  ✅ 完成状态: {is_completed}")
    print(f"  📄 摘要: {completion_summary}")
    if token_usage:
        print(f"  💰 Token使用: {token_usage}")
    
    smart_call_success = bool(is_completed)
    
    # 3. 测试文件同步功能
    sync_success = test_file_sync_functionality(mcp_client_url, vm_id, session_id)
    
    # 4. 显示完整测试总结
    print("\n" + "=" * 60)
    print("📊 完整测试结果汇总:")
    print("=" * 60)
    print(f"1️⃣  服务器注册: {'✅ 成功' if registration_success else '❌ 失败'}")
    print(f"3️⃣  文件同步功能: {'✅ 成功' if sync_success else '❌ 失败'}")
    
    all_success = registration_success and sync_success
    
    if all_success:
        print(f"\n🎉 所有测试通过！MCP系统运行正常")
    else:
        print(f"\n⚠️ 部分测试失败，请检查相关组件")