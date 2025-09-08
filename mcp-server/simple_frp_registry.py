#!/usr/bin/env python3
"""
简化的FRP注册工具
仅用于MCP服务器注册时使用FRP反向代理，解决服务器端客户端连接客户机端服务器的问题
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# 尝试导入FRP隧道模块
try:
    # 添加frp路径到sys.path
    frp_path = Path(__file__).parent.parent.parent / "useit_frp"
    if frp_path.exists():
        sys.path.insert(0, str(frp_path))
    
    from frp_tunnel import FrpTunnel
    FRP_AVAILABLE = True
except ImportError:
    print("Warning: FRP tunnel module not found, FRP功能将被禁用")
    FRP_AVAILABLE = False


@dataclass
class ServerRegistrationConfig:
    """服务器注册配置"""
    server_name: str
    local_port: int
    local_host: str = "127.0.0.1"
    description: str = ""
    enable_frp: bool = False  # 是否启用FRP反向代理
    registry_url: str = "http://localhost:8080"  # MCP客户端注册地址
    vm_id: str = ""  # 虚拟机ID
    session_id: str = ""  # 会话ID
    

class SimpleFRPRegistry:
    """简化的FRP注册器"""
    
    def __init__(self, base_dir=None):
        self.active_tunnels = {}  # server_name -> tunnel
        self.registered_servers = {}  # server_name -> registration info
        self.base_dir = base_dir or os.environ.get('MCP_BASE_DIR', os.path.join(os.getcwd(), 'mcp_workspace'))
        
        # 确保.useit目录存在
        useit_dir = os.path.join(self.base_dir, '.useit')
        os.makedirs(useit_dir, exist_ok=True)
        
        self.json_file_path = os.path.join(useit_dir, "mcp_server_frp.json")
        
    def register_server(self, config: ServerRegistrationConfig) -> dict:
        """
        注册MCP服务器，可选择使用FRP反向代理
        
        Args:
            config: 服务器注册配置
            
        Returns:
            注册信息字典，包含local_url和public_url (如果有)
        """
        print(f"🔄 注册 MCP 服务器: {config.server_name}")
        
        # 构建本地URL
        local_url = f"http://{config.local_host}:{config.local_port}/mcp"
        
        registration_info = {
            "server_name": config.server_name,
            "local_url": local_url,
            "public_url": None,
            "description": config.description,
            "frp_enabled": False
        }
        
        # 如果启用FRP且可用，创建隧道
        if config.enable_frp and FRP_AVAILABLE:
            try:
                print(f"🌐 为 {config.server_name} 创建 FRP 隧道...")
                tunnel = FrpTunnel(config.local_port, config.local_host)
                public_url = tunnel.start_tunnel()
                
                # 强制使用HTTP而不是HTTPS
                if public_url.startswith("https://"):
                    public_url = public_url.replace("https://", "http://")
                    print(f"🔄 转换为HTTP地址: {public_url}")
                
                # 为MCP添加路径
                if not public_url.endswith("/mcp"):
                    public_url = public_url.rstrip("/") + "/mcp"
                
                self.active_tunnels[config.server_name] = tunnel
                registration_info["public_url"] = public_url
                registration_info["frp_enabled"] = True
                
                print(f"✅ FRP 隧道创建成功: {public_url}")
                
            except Exception as e:
                print(f"❌ FRP 隧道创建失败: {e}")
                print(f"⚠️ 将使用本地地址注册")
        elif config.enable_frp and not FRP_AVAILABLE:
            print(f"⚠️ FRP 功能未可用，将使用本地地址注册")
        
        # 生成注册信息JSON文件
        registration_url = registration_info["public_url"] or registration_info["local_url"]
        self._export_registration_json(config, registration_url, registration_info)
        
        self.registered_servers[config.server_name] = registration_info
        print(f"✅ 服务器 {config.server_name} 配置完成")
        print(f"   本地地址: {local_url}")
        if registration_info["public_url"]:
            print(f"   公网地址: {registration_info['public_url']}")
            print(f"   注册文件: ./{self.json_file_path}")
        else:
            print(f"   注册文件: ./{self.json_file_path} (本地模式)")
        
        return registration_info
    
    def _export_registration_json(self, config: ServerRegistrationConfig, registration_url: str, registration_info: dict):
        """更新统一的JSON注册文件"""
        try:
            server_data = {
                "name": config.server_name,
                "url": registration_url,
                "description": config.description,
                "transport": "http",
                "local_url": registration_info["local_url"],
                "public_url": registration_info["public_url"],
                "frp_enabled": registration_info["frp_enabled"],
                "timestamp": int(time.time())
            }
            
            # 读取现有的JSON文件
            existing_data = {
                "vm_id": config.vm_id,
                "session_id": config.session_id,
                "registry_url": config.registry_url,
                "servers": []
            }
            
            if os.path.exists(self.json_file_path):
                try:
                    with open(self.json_file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        # 确保必须的字段存在并更新
                        if "vm_id" not in existing_data:
                            existing_data["vm_id"] = config.vm_id
                        else:
                            existing_data["vm_id"] = config.vm_id  # 更新为最新值
                        if "session_id" not in existing_data:
                            existing_data["session_id"] = config.session_id
                        else:
                            existing_data["session_id"] = config.session_id  # 更新为最新值
                        if "servers" not in existing_data:
                            existing_data["servers"] = []
                except:
                    pass  # 使用默认数据
            
            # 更新或添加服务器
            servers = existing_data["servers"]
            server_index = next((i for i, s in enumerate(servers) if s["name"] == config.server_name), -1)
            
            if server_index >= 0:
                servers[server_index] = server_data
            else:
                servers.append(server_data)
            
            # 更新registry_url
            existing_data["registry_url"] = config.registry_url
            
            # 写入JSON文件
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 注册信息已更新到: {self.json_file_path}")
                
        except Exception as e:
            print(f"❌ 导出注册信息失败: {e}")
    
    def unregister_server(self, server_name: str) -> bool:
        """取消注册服务器并停止隧道"""
        print(f"🛑 取消注册服务器: {server_name}")
        
        success = True
        
        # 停止FRP隧道
        if server_name in self.active_tunnels:
            try:
                self.active_tunnels[server_name].stop_tunnel()
                del self.active_tunnels[server_name]
                print(f"✅ FRP 隧道已停止: {server_name}")
            except Exception as e:
                print(f"❌ 停止隧道失败: {e}")
                success = False
        
        # 从注册表中移除
        if server_name in self.registered_servers:
            del self.registered_servers[server_name]
        
        # 从统一JSON文件中移除服务器
        try:
            if os.path.exists(self.json_file_path):
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 移除指定服务器
                if "servers" in data:
                    data["servers"] = [s for s in data["servers"] if s["name"] != server_name]
                    
                    with open(self.json_file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    
                    print(f"✅ 已从JSON文件中移除: {server_name}")
        except Exception as e:
            print(f"❌ 更新JSON文件失败: {e}")
        
        return success
    
    def unregister_all_servers(self):
        """取消注册所有服务器并停止所有隧道"""
        print("🛑 停止所有 FRP 隧道和服务器注册...")
        
        for server_name in list(self.active_tunnels.keys()):
            self.unregister_server(server_name)
        
        # 清理统一JSON文件
        try:
            if os.path.exists(self.json_file_path):
                os.remove(self.json_file_path)
                print(f"✅ 已删除JSON注册文件: {self.json_file_path}")
        except Exception as e:
            print(f"❌ 删除JSON文件失败: {e}")
        
        print("✅ 所有隧道和注册已清理")
    
    def get_server_info(self, server_name: str) -> Optional[dict]:
        """获取服务器注册信息"""
        return self.registered_servers.get(server_name)
    
    def list_registered_servers(self) -> dict:
        """列出所有已注册的服务器"""
        return self.registered_servers.copy()
    
    def is_tunnel_active(self, server_name: str) -> bool:
        """检查服务器的隧道是否活跃"""
        if server_name in self.active_tunnels:
            return self.active_tunnels[server_name].is_running()
        return False


# 全局注册器实例
_registry_instance = None

def get_registry(base_dir=None) -> SimpleFRPRegistry:
    """获取全局注册器实例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = SimpleFRPRegistry(base_dir)
    return _registry_instance


def register_mcp_server(
    server_name: str,
    local_port: int,
    local_host: str = "127.0.0.1", 
    description: str = "",
    enable_frp: bool = False,
    registry_url: str = None,
    vm_id: str = "",
    session_id: str = "",
    base_dir: str = None
) -> dict:
    """
    便捷函数：注册MCP服务器
    
    Args:
        server_name: 服务器名称
        local_port: 本地端口
        local_host: 本地主机地址
        description: 服务器描述
        enable_frp: 是否启用FRP反向代理
        registry_url: MCP客户端注册地址
        vm_id: 虚拟机ID
        session_id: 会话ID
        base_dir: 基础工作目录
        
    Returns:
        注册信息字典
    """
    if registry_url is None:
        registry_url = os.environ.get("MCP_CLIENT_URL", "http://localhost:8080")
    
    config = ServerRegistrationConfig(
        server_name=server_name,
        local_port=local_port,
        local_host=local_host,
        description=description,
        enable_frp=enable_frp,
        registry_url=registry_url,
        vm_id=vm_id,
        session_id=session_id
    )
    
    registry = get_registry(base_dir)
    return registry.register_server(config)


def unregister_mcp_server(server_name: str) -> bool:
    """便捷函数：取消注册MCP服务器"""
    registry = get_registry()
    return registry.unregister_server(server_name)


def cleanup_all_registrations():
    """便捷函数：清理所有注册"""
    registry = get_registry()
    registry.unregister_all_servers()


if __name__ == "__main__":
    import argparse
    import signal
    
    parser = argparse.ArgumentParser(description="MCP服务器FRP注册工具")
    parser.add_argument("server_name", help="服务器名称")
    parser.add_argument("local_port", type=int, help="本地端口")
    parser.add_argument("--host", default="127.0.0.1", help="本地主机地址")
    parser.add_argument("--description", default="", help="服务器描述")
    parser.add_argument("--enable-frp", action="store_true", help="启用FRP反向代理")
    parser.add_argument("--registry-url", help="MCP客户端注册地址")
    
    args = parser.parse_args()
    
    # 注册信号处理器
    def signal_handler(signum, frame):
        print("\n收到停止信号，正在清理...")
        cleanup_all_registrations()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 注册服务器
    registration_info = register_mcp_server(
        server_name=args.server_name,
        local_port=args.local_port,
        local_host=args.host,
        description=args.description,
        enable_frp=args.enable_frp,
        registry_url=args.registry_url
    )
    
    print(f"\n🎉 服务器配置完成！")
    print(f"📄 注册信息已保存到: mcp_server_frp.json")
    
    if registration_info["frp_enabled"]:
        print(f"🌐 FRP隧道已创建: {registration_info['public_url']}")
        print(f"💡 请通过安全通道传输JSON文件到服务器端进行注册")
        print(f"\n按 Ctrl+C 停止服务...")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
                # 检查隧道状态
                registry = get_registry()
                if not registry.is_tunnel_active(args.server_name):
                    print("❌ 隧道连接断开，正在退出...")
                    break
        except KeyboardInterrupt:
            pass
    else:
        print(f"💡 本地模式: 请通过安全通道传输JSON文件到服务器端进行注册")