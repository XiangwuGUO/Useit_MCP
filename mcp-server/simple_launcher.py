#!/usr/bin/env python3
"""
简化的MCP服务器启动器
保留本地测试功能，可选择启用FRP反向代理进行远程注册
专为客户机上的MCP服务器设计，使服务器端MCP客户端可以连接
"""

import os
import sys
import time
import yaml
import socket
import subprocess
import signal
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# 导入简化的FRP注册器
from simple_frp_registry import register_mcp_server, cleanup_all_registrations, get_registry


@dataclass
class SimpleServerConfig:
    """简化的服务器配置"""
    name: str
    module_path: str
    port: Optional[int] = None
    transport: str = "streamable-http"
    env_vars: Optional[Dict[str, str]] = None
    description: str = ""


class SimplePortManager:
    """简单的端口管理器"""
    
    def __init__(self, start_port: int = 8002):
        self.start_port = start_port
        self.allocated_ports = set()
    
    def find_available_port(self, preferred_port: Optional[int] = None) -> int:
        """找到可用端口"""
        if preferred_port and self._is_port_available(preferred_port):
            self.allocated_ports.add(preferred_port)
            return preferred_port
        
        for port in range(self.start_port, self.start_port + 100):
            if port not in self.allocated_ports and self._is_port_available(port):
                self.allocated_ports.add(port)
                return port
        
        raise RuntimeError("无法找到可用端口")
    
    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except OSError:
            return False


class SimpleMCPLauncher:
    """简化的MCP服务器启动器"""
    
    def __init__(self):
        self.port_manager = SimplePortManager()
        self.running_processes = {}
        self.server_addresses = {}
        self.enable_frp = False  # 是否启用FRP功能
        self.registry_url = os.environ.get("MCP_CLIENT_URL", "http://localhost:8080")
        
        # 注册退出清理
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        print(f"\n收到停止信号 ({signum})，正在清理...")
        self.cleanup()
        sys.exit(0)
    
    def get_official_servers(self) -> List[SimpleServerConfig]:
        """获取官方服务器配置"""
        return [
            SimpleServerConfig(
                name="audio_slicer",
                module_path="official_server/audio_slicer/server.py",
                port=8002,
                description="音频切片服务"
            ),
            SimpleServerConfig(
                name="filesystem", 
                module_path="official_server/filesystem/server.py",
                port=8003,
                description="文件系统操作"
            ),
            SimpleServerConfig(
                name="web_search",
                module_path="official_server/web_search/server.py", 
                port=8004,
                description="网页搜索服务",
                env_vars={"OPENAI_API_KEY": "required"}
            )
        ]
    
    def load_custom_servers_config(self, config_path: str = "servers_config.yaml") -> List[SimpleServerConfig]:
        """加载自定义服务器配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            return []
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            servers = []
            for server_data in config_data.get('custom_servers', []):
                servers.append(SimpleServerConfig(
                    name=server_data['name'],
                    module_path=server_data['module_path'],
                    port=server_data.get('port'),
                    transport=server_data.get('transport', 'streamable-http'),
                    env_vars=server_data.get('env_vars'),
                    description=server_data.get('description', '')
                ))
            return servers
        except Exception as e:
            print(f"Warning: 加载自定义服务器配置失败: {e}")
            return []
    
    def start_server(self, config: SimpleServerConfig) -> Tuple[str, subprocess.Popen]:
        """启动单个MCP服务器"""
        print(f"🚀 启动服务器: {config.name}")
        
        # 分配端口
        port = self.port_manager.find_available_port(config.port)
        
        # 准备环境变量
        env = {"MCP_SERVER_PORT": str(port)}
        if config.env_vars:
            for key, value in config.env_vars.items():
                if value == "required" and key not in os.environ:
                    env_val = input(f"请输入 {key} (用于 {config.name}): ").strip()
                    if not env_val:
                        raise ValueError(f"必需的环境变量 {key} 未提供")
                    env[key] = env_val
                elif value != "required":
                    env[key] = value
                else:
                    env[key] = os.environ.get(key, "")
        
        # 准备命令
        server_path = Path(__file__).parent / config.module_path
        if not server_path.exists():
            raise FileNotFoundError(f"服务器模块未找到: {server_path}")
        
        cmd = [sys.executable, str(server_path)]
        if config.transport == "stdio":
            cmd.append("stdio")
        
        # 启动进程
        process = subprocess.Popen(
            cmd,
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待启动
        time.sleep(1)
        
        # 构建地址
        if config.transport == "streamable-http":
            address = f"http://localhost:{port}/mcp"
        else:
            address = f"stdio://localhost:{port}"
        
        print(f"✅ {config.name} 启动成功: {address}")
        return address, process
    
    def start_all_servers(self, include_custom: bool = True) -> Dict[str, str]:
        """启动所有服务器"""
        addresses = {}
        
        print(f"🚀 启动 MCP 服务器{'（含FRP注册）' if self.enable_frp else ''}...")
        
        # 启动官方服务器
        for config in self.get_official_servers():
            try:
                address, process = self.start_server(config)
                self.running_processes[config.name] = process
                self.server_addresses[config.name] = address
                addresses[config.name] = address
                
                # 如果启用FRP，进行注册
                if self.enable_frp:
                    port = self._extract_port_from_address(address)
                    register_mcp_server(
                        server_name=config.name,
                        local_port=port,
                        description=config.description,
                        enable_frp=True,
                        registry_url=self.registry_url
                    )
                
            except Exception as e:
                print(f"❌ 启动 {config.name} 失败: {e}")
        
        # 启动自定义服务器
        if include_custom:
            for config in self.load_custom_servers_config():
                try:
                    address, process = self.start_server(config)
                    self.running_processes[config.name] = process
                    self.server_addresses[config.name] = address
                    addresses[config.name] = address
                    
                    # 如果启用FRP，进行注册
                    if self.enable_frp:
                        port = self._extract_port_from_address(address)
                        register_mcp_server(
                            server_name=config.name,
                            local_port=port,
                            description=config.description,
                            enable_frp=True,
                            registry_url=self.registry_url
                        )
                    
                except Exception as e:
                    print(f"❌ 启动自定义服务器 {config.name} 失败: {e}")
        
        return addresses
    
    def _extract_port_from_address(self, address: str) -> int:
        """从地址中提取端口号"""
        try:
            if "localhost:" in address:
                port_str = address.split("localhost:")[1].split("/")[0]
                return int(port_str)
            return 8000
        except:
            return 8000
    
    def stop_all_servers(self):
        """停止所有服务器"""
        print("🛑 停止所有服务器...")
        
        for name, process in self.running_processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ 已停止: {name}")
            except Exception as e:
                print(f"❌ 停止 {name} 失败: {e}")
                try:
                    process.kill()
                except:
                    pass
        
        self.running_processes.clear()
        self.server_addresses.clear()
        
    def cleanup(self):
        """清理资源"""
        self.stop_all_servers()
        if self.enable_frp:
            cleanup_all_registrations()
    
    def get_server_status(self) -> Dict[str, str]:
        """获取服务器状态"""
        status = {}
        for name, process in self.running_processes.items():
            if process.poll() is None:
                local_addr = self.server_addresses.get(name, 'unknown')
                
                if self.enable_frp:
                    # 获取FRP信息
                    registry = get_registry()
                    server_info = registry.get_server_info(name)
                    if server_info and server_info.get("public_url"):
                        status[name] = f"运行中 - 本地: {local_addr}, 公网: {server_info['public_url']}"
                    else:
                        status[name] = f"运行中 - {local_addr} (FRP注册失败)"
                else:
                    status[name] = f"运行中 - {local_addr}"
            else:
                status[name] = "已停止"
        return status


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='简化的MCP服务器启动器')
    parser.add_argument('--single', '-s', help='只启动单个服务器')
    parser.add_argument('--no-custom', action='store_true', help='跳过自定义服务器')
    parser.add_argument('--enable-frp', action='store_true', help='启用FRP反向代理注册')
    parser.add_argument('--registry-url', help='MCP客户端注册地址', 
                       default=os.environ.get("MCP_CLIENT_URL", "http://localhost:8080"))
    parser.add_argument('--list', action='store_true', help='列出可用服务器')
    parser.add_argument('--status', action='store_true', help='显示服务器状态')
    
    args = parser.parse_args()
    
    launcher = SimpleMCPLauncher()
    launcher.enable_frp = args.enable_frp
    launcher.registry_url = args.registry_url
    
    if args.list:
        print("📋 可用服务器:")
        print("\n官方服务器:")
        for server in launcher.get_official_servers():
            print(f"  - {server.name}: {server.description}")
        
        custom_servers = launcher.load_custom_servers_config()
        if custom_servers:
            print("\n自定义服务器:")
            for server in custom_servers:
                print(f"  - {server.name}: {server.description}")
        return
    
    if args.status:
        status = launcher.get_server_status()
        if status:
            print("📊 服务器状态:")
            for name, state in status.items():
                print(f"  - {name}: {state}")
        else:
            print("📊 没有运行的服务器")
        return
    
    if args.single:
        # 启动单个服务器
        all_servers = launcher.get_official_servers() + launcher.load_custom_servers_config()
        target_server = next((s for s in all_servers if s.name == args.single), None)
        
        if not target_server:
            print(f"❌ 未找到服务器: {args.single}")
            return
        
        try:
            address, process = launcher.start_server(target_server)
            launcher.running_processes[target_server.name] = process
            launcher.server_addresses[target_server.name] = address
            
            # 如果启用FRP，进行注册
            if args.enable_frp:
                port = launcher._extract_port_from_address(address)
                register_mcp_server(
                    server_name=target_server.name,
                    local_port=port,
                    description=target_server.description,
                    enable_frp=True,
                    registry_url=args.registry_url
                )
            
            print(f"\n🎉 服务器 {target_server.name} 启动成功!")
            if args.enable_frp:
                print(f"💡 服务器已通过FRP注册，服务器端MCP客户端现在可以连接")
                registry = get_registry()
                server_info = registry.get_server_info(target_server.name)
                if server_info and server_info.get("public_url"):
                    print(f"🔗 公网地址: {server_info['public_url']}")
            print(f"📍 本地地址: {address}")
            print(f"\n按 Ctrl+C 停止...")
            
            try:
                while process.poll() is None:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n正在关闭...")
            
        except Exception as e:
            print(f"❌ 启动 {target_server.name} 失败: {e}")
        return
    
    # 启动所有服务器
    try:
        addresses = launcher.start_all_servers(include_custom=not args.no_custom)
        
        if not addresses:
            print("❌ 没有服务器启动")
            return
        
        print(f"\n🎉 成功启动 {len(addresses)} 个服务器!")
        
        if args.enable_frp:
            print(f"\n💡 FRP模式已启用:")
            print(f"   • 所有服务器已通过FRP反向代理注册")
            print(f"   • 服务器端MCP客户端现在可以连接到客户机上的服务器")
            print(f"   • 注册地址: {args.registry_url}")
            
            # 显示注册信息
            registry = get_registry()
            for server_name in addresses.keys():
                server_info = registry.get_server_info(server_name)
                if server_info:
                    print(f"   • {server_name}: {server_info.get('public_url', '注册失败')}")
        else:
            print(f"\n💡 本地模式:")
            print(f"   • 服务器仅在本地可访问")
            print(f"   • 使用 --enable-frp 启用远程访问功能")
        
        print(f"\n按 Ctrl+C 停止所有服务器...")
        
        try:
            while True:
                time.sleep(1)
                # 检查进程状态
                dead_servers = []
                for name, process in launcher.running_processes.items():
                    if process.poll() is not None:
                        dead_servers.append(name)
                
                if dead_servers:
                    print(f"❌ 服务器意外停止: {', '.join(dead_servers)}")
                    break
                        
        except KeyboardInterrupt:
            print("\n正在关闭所有服务器...")
    
    except Exception as e:
        print(f"❌ 启动过程出错: {e}")
    
    finally:
        launcher.cleanup()


if __name__ == "__main__":
    main()