#!/usr/bin/env python3
"""
传统MCP服务器启动器 (不含FRP功能)
用于纯本地测试和开发环境
"""

import os
import socket
import subprocess
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ServerConfig:
    name: str
    module_path: str
    port: Optional[int] = None
    transport: str = "streamable-http"
    env_vars: Optional[Dict[str, str]] = None
    description: str = ""


class PortManager:
    """端口管理器"""
    
    def __init__(self, start_port: int = 8000, max_attempts: int = 100):
        self.start_port = start_port
        self.max_attempts = max_attempts
        self.allocated_ports = set()
    
    def find_available_port(self, preferred_port: Optional[int] = None) -> int:
        """找到可用端口"""
        if preferred_port and self._is_port_available(preferred_port):
            self.allocated_ports.add(preferred_port)
            return preferred_port
        
        for i in range(self.max_attempts):
            port = self.start_port + i
            if port not in self.allocated_ports and self._is_port_available(port):
                self.allocated_ports.add(port)
                return port
        
        raise RuntimeError(f"Could not find available port after {self.max_attempts} attempts")
    
    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    def release_port(self, port: int):
        """释放端口"""
        self.allocated_ports.discard(port)


class MCPServerManager:
    """传统MCP服务器管理器"""
    
    def __init__(self):
        self.port_manager = PortManager()
        self.running_processes = {}
        self.server_addresses = {}
        
    def get_official_servers(self) -> List[ServerConfig]:
        """获取官方服务器配置"""
        return [
            ServerConfig(
                name="audio_slicer",
                module_path="official_server/audio_slicer/server.py",
                port=8002,
                description="Audio slicing service for beat-based segmentation"
            ),
            ServerConfig(
                name="filesystem", 
                module_path="official_server/filesystem/server.py",
                port=8003,
                description="Sandboxed filesystem operations"
            ),
            ServerConfig(
                name="web_search",
                module_path="official_server/web_search/server.py", 
                port=8004,
                description="Web search using OpenAI API",
                env_vars={"OPENAI_API_KEY": "required"}
            )
        ]
    
    def load_custom_servers_config(self, config_path: str = "servers_config.yaml") -> List[ServerConfig]:
        """加载自定义服务器配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            return []
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            servers = []
            for server_data in config_data.get('custom_servers', []):
                servers.append(ServerConfig(
                    name=server_data['name'],
                    module_path=server_data['module_path'],
                    port=server_data.get('port'),
                    transport=server_data.get('transport', 'streamable-http'),
                    env_vars=server_data.get('env_vars'),
                    description=server_data.get('description', '')
                ))
            return servers
        except Exception as e:
            print(f"Warning: Failed to load custom servers config: {e}")
            return []
    
    def start_server(self, config: ServerConfig) -> Tuple[str, subprocess.Popen]:
        """启动单个MCP服务器"""
        # 分配端口
        port = self.port_manager.find_available_port(config.port)
        
        # 准备环境变量
        env = {"MCP_SERVER_PORT": str(port)}
        if config.env_vars:
            for key, value in config.env_vars.items():
                if value == "required" and key not in os.environ:
                    env_val = input(f"Enter {key} for {config.name}: ").strip()
                    if not env_val:
                        raise ValueError(f"Required environment variable {key} not provided")
                    env[key] = env_val
                elif value != "required":
                    env[key] = value
                else:
                    env[key] = os.environ.get(key, "")
        
        # 准备命令
        server_path = Path(__file__).parent / config.module_path
        if not server_path.exists():
            raise FileNotFoundError(f"Server module not found: {server_path}")
        
        cmd = [sys.executable, str(server_path)]
        if config.transport == "stdio":
            cmd.append("stdio")
        
        # 启动进程
        process = subprocess.Popen(
            cmd,
            env={**os.environ, **env} if env else None,
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
        
        return address, process
    
    def start_all_servers(self, include_custom: bool = True) -> Dict[str, str]:
        """启动所有服务器"""
        addresses = {}
        
        print("🚀 启动MCP服务器集群...")
        
        # 启动官方服务器
        for config in self.get_official_servers():
            try:
                address, process = self.start_server(config)
                self.running_processes[config.name] = process
                addresses[config.name] = address
                print(f"✓ Started {config.name} at {address}")
                    
            except Exception as e:
                print(f"✗ Failed to start {config.name}: {e}")
        
        # 启动自定义服务器
        if include_custom:
            for config in self.load_custom_servers_config():
                try:
                    address, process = self.start_server(config)
                    self.running_processes[config.name] = process
                    addresses[config.name] = address
                    print(f"✓ Started custom server {config.name} at {address}")
                        
                except Exception as e:
                    print(f"✗ Failed to start custom server {config.name}: {e}")
        
        self.server_addresses = addresses
        return addresses
    
    def stop_all_servers(self):
        """停止所有服务器"""
        print("🛑 停止MCP服务器...")
        for name, process in self.running_processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✓ Stopped {name}")
            except Exception as e:
                print(f"✗ Error stopping {name}: {e}")
                try:
                    process.kill()
                except:
                    pass
        
        self.running_processes.clear()
        self.server_addresses.clear()
        self.port_manager.allocated_ports.clear()
    
    def get_server_status(self) -> Dict[str, str]:
        """获取服务器状态"""
        status = {}
        for name, process in self.running_processes.items():
            if process.poll() is None:
                status[name] = f"running - {self.server_addresses.get(name, 'unknown address')}"
            else:
                status[name] = "stopped"
        return status


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='传统MCP服务器启动器')
    parser.add_argument('--single', '-s', help='启动单个服务器')
    parser.add_argument('--no-custom', action='store_true', help='跳过自定义服务器')
    parser.add_argument('--list', action='store_true', help='列出可用服务器')
    
    args = parser.parse_args()
    
    manager = MCPServerManager()
    
    if args.list:
        print("官方服务器:")
        for server in manager.get_official_servers():
            print(f"  - {server.name}: {server.description}")
        
        custom_servers = manager.load_custom_servers_config()
        if custom_servers:
            print("\n自定义服务器:")
            for server in custom_servers:
                print(f"  - {server.name}: {server.description}")
        return
    
    if args.single:
        # 启动单个服务器
        all_servers = manager.get_official_servers() + manager.load_custom_servers_config()
        target_server = next((s for s in all_servers if s.name == args.single), None)
        
        if not target_server:
            print(f"Server '{args.single}' not found")
            return
        
        try:
            address, process = manager.start_server(target_server)
            print(f"Started {target_server.name} at {address}")
            print("Press Ctrl+C to stop...")
            
            try:
                while process.poll() is None:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                process.terminate()
                process.wait()
        except Exception as e:
            print(f"Failed to start {target_server.name}: {e}")
        return
    
    # 启动所有服务器
    try:
        print("Starting MCP servers...")
        addresses = manager.start_all_servers(include_custom=not args.no_custom)
        
        if not addresses:
            print("No servers started")
            return
        
        print(f"\n🎉 成功启动 {len(addresses)} 个MCP服务器！")
        print("\nPress Ctrl+C to stop all servers...")
        
        try:
            while True:
                time.sleep(1)
                # 检查进程状态
                dead_servers = []
                for name, process in manager.running_processes.items():
                    if process.poll() is not None:
                        dead_servers.append(name)
                
                if dead_servers:
                    print(f"Servers stopped unexpectedly: {', '.join(dead_servers)}")
                    break
                        
        except KeyboardInterrupt:
            print("\nShutting down all servers...")
    
    finally:
        manager.stop_all_servers()


if __name__ == "__main__":
    main()