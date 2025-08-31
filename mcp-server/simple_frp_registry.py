#!/usr/bin/env python3
"""
简化的FRP注册工具
仅用于MCP服务器注册时使用FRP反向代理，解决服务器端客户端连接客户机端服务器的问题
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

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
    

class SimpleFRPRegistry:
    """简化的FRP注册器"""
    
    def __init__(self):
        self.active_tunnels = {}  # server_name -> tunnel
        self.registered_servers = {}  # server_name -> registration info
        
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
        
        # 注册到MCP客户端
        registration_url = registration_info["public_url"] or registration_info["local_url"]
        success = self._register_to_client(config, registration_url)
        
        if success:
            self.registered_servers[config.server_name] = registration_info
            print(f"✅ 服务器 {config.server_name} 注册成功")
            print(f"   本地地址: {local_url}")
            if registration_info["public_url"]:
                print(f"   公网地址: {registration_info['public_url']}")
                print(f"   注册地址: {registration_info['public_url']} (FRP)")
            else:
                print(f"   注册地址: {local_url} (本地)")
        else:
            print(f"❌ 服务器 {config.server_name} 注册失败")
            # 如果注册失败，清理隧道
            if config.server_name in self.active_tunnels:
                self.active_tunnels[config.server_name].stop_tunnel()
                del self.active_tunnels[config.server_name]
        
        return registration_info
    
    def _register_to_client(self, config: ServerRegistrationConfig, registration_url: str) -> bool:
        """向MCP客户端注册服务器"""
        try:
            register_data = {
                "name": config.server_name,
                "url": registration_url,
                "description": config.description,
                "transport": "http"
            }
            
            # 尝试注册
            response = requests.post(
                f"{config.registry_url}/servers/register",
                json=register_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return True
            else:
                print(f"注册失败，状态码: {response.status_code}, 响应: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"注册请求失败: {e}")
            return False
        except Exception as e:
            print(f"注册过程出错: {e}")
            return False
    
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
        
        return success
    
    def unregister_all_servers(self):
        """取消注册所有服务器并停止所有隧道"""
        print("🛑 停止所有 FRP 隧道和服务器注册...")
        
        for server_name in list(self.active_tunnels.keys()):
            self.unregister_server(server_name)
        
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

def get_registry() -> SimpleFRPRegistry:
    """获取全局注册器实例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = SimpleFRPRegistry()
    return _registry_instance


def register_mcp_server(
    server_name: str,
    local_port: int,
    local_host: str = "127.0.0.1", 
    description: str = "",
    enable_frp: bool = False,
    registry_url: str = None
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
        registry_url=registry_url
    )
    
    registry = get_registry()
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
    
    if registration_info["frp_enabled"]:
        print(f"\n🎉 服务器注册成功！")
        print(f"💡 服务器端MCP客户端现在可以通过公网地址连接到此服务器")
        print(f"🔗 公网地址: {registration_info['public_url']}")
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
        print(f"\n✅ 服务器注册完成（本地模式）")