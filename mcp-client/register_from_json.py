#!/usr/bin/env python3
"""
MCP服务器JSON配置注册器

从JSON配置文件批量注册MCP服务器，支持FRP隧道配置。
"""

import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


def load_mcp_config(json_file_path: str) -> Dict[str, Any]:
    """
    加载MCP服务器配置JSON文件
    
    Args:
        json_file_path: JSON配置文件路径
        
    Returns:
        Dict: 解析后的配置数据
        
    Raises:
        FileNotFoundError: 配置文件不存在
        json.JSONDecodeError: JSON格式错误
    """
    json_path = Path(json_file_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {json_file_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 验证必需字段
        required_fields = ['vm_id', 'session_id', 'registry_url', 'servers']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"配置文件缺少必需字段: {field}")
        
        print(f"✅ 成功加载配置文件: {json_file_path}")
        print(f"   📍 会话: {config['vm_id']}/{config['session_id']}")
        print(f"   📡 注册URL: {config['registry_url']}")
        print(f"   🔧 服务器数量: {len(config['servers'])}")
        
        return config
        
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON格式错误: {e}")


def register_single_server_from_config(
    registry_url: str,
    vm_id: str, 
    session_id: str,
    server_config: Dict[str, Any]
) -> bool:
    """
    注册单个MCP服务器
    
    Args:
        registry_url: MCP客户端注册URL
        vm_id: 虚拟机ID
        session_id: 会话ID
        server_config: 服务器配置字典
        
    Returns:
        bool: 注册是否成功
    """
    
    # 提取服务器信息
    server_name = server_config.get('name')
    server_url = server_config.get('url') or server_config.get('local_url')
    description = server_config.get('description', f"{server_name} MCP服务器")
    transport = server_config.get('transport', 'http')
    
    # 如果启用了FRP且有public_url，优先使用public_url
    if server_config.get('frp_enabled') and server_config.get('public_url'):
        server_url = server_config['public_url']
        print(f"🌐 {server_name}: 使用FRP公网地址 {server_url}")
    else:
        print(f"🔗 {server_name}: 使用本地地址 {server_url}")
    
    if not server_name or not server_url:
        print(f"❌ 服务器配置不完整: {server_config}")
        return False
    
    try:
        payload = {
            "vm_id": vm_id,
            "session_id": session_id,
            "name": server_name,
            "url": server_url,
            "description": description,
            "transport": transport
        }
        
        print(f"📡 注册服务器: {server_name} -> {server_url}")
        
        response = requests.post(f"{registry_url}/clients", json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ {server_name} 注册成功")
            return True
        elif response.status_code == 400:
            print(f"⚠️ {server_name} 可能已存在 (HTTP {response.status_code})")
            return True  # 已存在也算成功
        else:
            print(f"❌ {server_name} 注册失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ {server_name} 注册异常: {e}")
        return False


def register_all_servers_from_json(
    json_file_path: str,
    registry_url_override: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    从JSON配置文件批量注册所有MCP服务器
    
    Args:
        json_file_path: JSON配置文件路径
        registry_url_override: 可选的注册URL覆盖（优先级高于配置文件）
        
    Returns:
        Tuple[bool, Dict]: (是否全部成功, 详细结果)
    """
    
    print(f"🚀 开始从JSON配置文件注册MCP服务器")
    print(f"📄 配置文件: {json_file_path}")
    print("=" * 60)
    
    try:
        # 1. 加载配置
        config = load_mcp_config(json_file_path)
        
        vm_id = config['vm_id']
        session_id = config['session_id']
        registry_url = registry_url_override or config['registry_url']
        servers = config['servers']
        
        print(f"\n📋 配置信息:")
        print(f"   📍 会话: {vm_id}/{session_id}")
        print(f"   📡 注册地址: {registry_url}")
        print(f"   🔧 待注册服务器: {len(servers)} 个")
        
        # 2. 检查MCP客户端状态
        print(f"\n🔍 检查MCP客户端状态...")
        try:
            health_response = requests.get(f"{registry_url}/health", timeout=5)
            if health_response.status_code == 200:
                health_data = health_response.json().get('data', {})
                print(f"✅ MCP客户端运行正常")
                print(f"   📊 当前已连接服务器: {health_data.get('connected_servers', 0)}")
                print(f"   🔧 当前可用工具: {health_data.get('total_tools', 0)}")
            else:
                print(f"⚠️ MCP客户端响应异常: HTTP {health_response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ 无法连接到MCP客户端: {registry_url}")
            return False, {"error": "无法连接到MCP客户端"}
        
        # 3. 批量注册服务器
        print(f"\n📡 开始批量注册服务器...")
        
        successful_servers = []
        failed_servers = []
        
        for i, server_config in enumerate(servers, 1):
            server_name = server_config.get('name', f'server_{i}')
            print(f"\n{i}️⃣ 注册服务器: {server_name}")
            
            if register_single_server_from_config(registry_url, vm_id, session_id, server_config):
                successful_servers.append(server_name)
            else:
                failed_servers.append(server_name)
        
        # 4. 汇总结果
        total_servers = len(servers)
        successful_count = len(successful_servers)
        failed_count = len(failed_servers)
        
        print(f"\n" + "=" * 60)
        print(f"📊 注册结果汇总")
        print(f"=" * 60)
        print(f"总服务器数: {total_servers}")
        print(f"成功注册: {successful_count} ✅")
        print(f"注册失败: {failed_count} ❌")
        print(f"成功率: {successful_count/total_servers*100:.1f}%")
        
        if successful_servers:
            print(f"\n✅ 成功注册的服务器:")
            for server in successful_servers:
                print(f"   - {server}")
        
        if failed_servers:
            print(f"\n❌ 注册失败的服务器:")
            for server in failed_servers:
                print(f"   - {server}")
        
        # 5. 验证最终状态
        print(f"\n🔍 验证注册后状态...")
        try:
            final_health = requests.get(f"{registry_url}/health", timeout=5)
            if final_health.status_code == 200:
                final_data = final_health.json().get('data', {})
                print(f"✅ 当前连接服务器: {final_data.get('connected_servers', 0)}")
                print(f"🔧 当前可用工具: {final_data.get('total_tools', 0)}")
        except Exception as e:
            print(f"⚠️ 无法验证最终状态: {e}")
        
        all_successful = failed_count == 0
        
        result_data = {
            "total_servers": total_servers,
            "successful_count": successful_count,
            "failed_count": failed_count,
            "successful_servers": successful_servers,
            "failed_servers": failed_servers,
            "success_rate": successful_count/total_servers*100 if total_servers > 0 else 0,
            "vm_id": vm_id,
            "session_id": session_id,
            "registry_url": registry_url
        }
        
        if all_successful:
            print(f"\n🎉 所有服务器注册成功!")
        else:
            print(f"\n⚠️ 部分服务器注册失败，请检查日志")
        
        return all_successful, result_data
        
    except Exception as e:
        print(f"❌ 注册过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False, {"error": str(e)}


def main():
    """主函数 - 演示用法"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python register_from_json.py <json_config_file> [registry_url]")
        print("示例: python register_from_json.py /path/to/mcp_server_frp.json")
        print("示例: python register_from_json.py /path/to/mcp_server_frp.json http://localhost:8080")
        return
    
    json_file = sys.argv[1]
    registry_url_override = sys.argv[2] if len(sys.argv) > 2 else None
    
    success, result = register_all_servers_from_json(json_file, registry_url_override)
    
    exit_code = 0 if success else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()