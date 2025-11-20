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

# 导入FRP API 客户端功能
import requests

# FRP API 服务器配置
FRP_API_URL = "http://localhost:5888"
FRP_AVAILABLE = True  # 假设FRP API服务器可用

def create_frp_tunnel(port: int, host: str = "127.0.0.1") -> dict:
    """通过API创建FRP隧道"""
    try:
        response = requests.post(
            f"{FRP_API_URL}/tunnels",
            json={"port": port, "host": host},
            timeout=30
        )
        
        if response.status_code == 201:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "无法连接到FRP API服务器，请确保FRP服务器在端口5888上运行"}
    except Exception as e:
        return {"success": False, "error": f"创建FRP隧道失败: {str(e)}"}


def delete_frp_tunnel(tunnel_id: str) -> dict:
    """通过API删除FRP隧道"""
    try:
        response = requests.delete(
            f"{FRP_API_URL}/tunnels/{tunnel_id}",
            timeout=10
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "无法连接到FRP API服务器"}
    except Exception as e:
        return {"success": False, "error": f"删除FRP隧道失败: {str(e)}"}


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
        self.vm_id = ""  # 虚拟机ID
        self.session_id = ""  # 会话ID
        self._cleanup_registered = False
        self.active_frp_tunnels = {}  # 存储隧道ID而不是隧道对象
        self.base_dir = os.environ.get('MCP_BASE_DIR', os.path.join(os.getcwd(), 'mcp_workspace'))
        # 记录每个服务器实际使用的端口（用于FRP注册与JSON一致）
        self.server_ports: Dict[str, int] = {}
        # 日志目录（位于项目根目录 logs/）
        try:
            project_root = Path(__file__).resolve().parents[1]
            self.log_dir = project_root / 'logs'
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.log_dir = Path(os.getcwd())
        # 记录每个服务器的日志文件句柄，便于关闭
        self.server_log_files = {}
    
    def _get_log_file_path(self, server_name: str) -> Path:
        """获取服务器日志文件路径"""
        return self.log_dir / f"{server_name}_server.log"
    
    def _rotate_log_file(self, log_path: Path):
        """将现有日志文件重命名为 *_old.log，再写入新日志文件"""
        try:
            if log_path.exists():
                old_path = log_path.with_name(f"{log_path.stem}_old{log_path.suffix}")
                try:
                    if old_path.exists():
                        old_path.unlink()
                except Exception:
                    pass
                try:
                    log_path.rename(old_path)
                except Exception:
                    pass
        except Exception:
            pass
        
    def _register_cleanup(self):
        """注册退出清理（仅在实际启动服务器时调用）"""
        if not self._cleanup_registered:
            atexit.register(self.cleanup)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            self._cleanup_registered = True
    
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
                name="excel_executor",
                module_path="official_server/excel_executor/server.py",
                port=8004,
                description="Excel自动化操作服务(两阶段流水线:Vision分析→代码生成→执行)"
            ),
            SimpleServerConfig(
                name="word_executor",
                module_path="official_server/word_executor/server.py",
                port=8005,
                description="Word文档自动化操作服务(增强流水线:Vision→文档搜索→段落定位→代码生成→执行)"
            ),
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
        
        # 准备日志文件：旋转旧日志后重新写入
        log_path = self._get_log_file_path(config.name)
        self._rotate_log_file(log_path)
        try:
            log_file = open(log_path, 'w', encoding='utf-8')
        except Exception:
            log_file = subprocess.DEVNULL

        # 启动进程，输出重定向到对应日志
        process = subprocess.Popen(
            cmd,
            env={**os.environ, **env},
            stdout=log_file,
            stderr=log_file
        )
        # 保存日志句柄
        if log_file is not subprocess.DEVNULL:
            self.server_log_files[config.name] = log_file
        
        # 等待启动
        time.sleep(1)
        
        # 构建地址
        if config.transport == "streamable-http":
            address = f"http://localhost:{port}/mcp"
        else:
            address = f"stdio://localhost:{port}"
        
        # 保存实际端口
        try:
            self.server_ports[config.name] = int(port)
        except Exception:
            pass
        
        print(f"✅ {config.name} 启动成功: {address}")
        return address, process
    
    def start_all_servers(self, include_custom: bool = True) -> Dict[str, str]:
        """启动所有服务器"""
        addresses = {}
        
        # 只有在实际启动服务器时才注册清理函数
        self._register_cleanup()
        
        print(f"🚀 启动 MCP 服务器{'（含JSON文件生成）' if self.enable_frp else ''}...")
        
        # 启动官方服务器
        for config in self.get_official_servers():
            try:
                address, process = self.start_server(config)
                self.running_processes[config.name] = process
                self.server_addresses[config.name] = address
                addresses[config.name] = address
                
                # 如果启用FRP，记录服务器信息（稍后统一生成JSON）
                if self.enable_frp:
                    # 仅记录信息，不进行实际注册
                    pass
                
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
                    
                    # 如果启用FRP，记录服务器信息（稍后统一生成JSON）
                    if self.enable_frp:
                        # 仅记录信息，不进行实际注册
                        pass
                    
                except Exception as e:
                    print(f"❌ 启动自定义服务器 {config.name} 失败: {e}")
        
        # 如果启用FRP，统一生成JSON文件
        if self.enable_frp and addresses:
            self._generate_frp_json(addresses)
        
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
    
    def _generate_frp_json(self, addresses: Dict[str, str]):
        """生成FRP JSON注册文件（包含隧道创建）"""
        try:
            import json
            import time
            
            # 确保.useit目录存在
            useit_dir = os.path.join(self.base_dir, '.useit')
            os.makedirs(useit_dir, exist_ok=True)
            
            # 创建FRP隧道并构建服务器列表
            servers = []
            
            for server_name, address in addresses.items():
                # 优先使用启动时记录的真实端口
                port = self.server_ports.get(server_name)
                if not port:
                    port = self._extract_port_from_address(address)
                
                # 查找服务器配置获取描述
                all_configs = self.get_official_servers() + self.load_custom_servers_config()
                config = next((c for c in all_configs if c.name == server_name), None)
                description = config.description if config else ""
                
                public_url = None
                frp_enabled = False
                tunnel_id = None
                
                # 通过API创建FRP隧道
                if FRP_AVAILABLE:
                    try:
                        print(f"🌐 为 {server_name} 创建 FRP 隧道...")
                        result = create_frp_tunnel(port, "127.0.0.1")
                        
                        if result["success"]:
                            tunnel_data = result["data"]
                            tunnel_url = tunnel_data.get("public_url", "")
                            tunnel_id = tunnel_data.get("share_token", "")
                            
                            # 强制使用HTTP而不是HTTPS
                            if tunnel_url.startswith("https://"):
                                tunnel_url = tunnel_url.replace("https://", "http://")
                                print(f"🔄 转换为HTTP地址: {tunnel_url}")
                            
                            # 为MCP添加路径
                            if not tunnel_url.endswith("/mcp"):
                                public_url = tunnel_url.rstrip("/") + "/mcp"
                            else:
                                public_url = tunnel_url
                            
                            # 存储隧道ID以便清理
                            self.active_frp_tunnels[server_name] = tunnel_id
                            frp_enabled = True
                            
                            print(f"✅ FRP 隧道创建成功: {public_url}")
                        else:
                            print(f"❌ FRP 隧道创建失败 {server_name}: {result['error']}")
                            print(f"⚠️ 将使用本地地址")
                        
                    except Exception as e:
                        print(f"❌ FRP 隧道创建异常 {server_name}: {e}")
                        print(f"⚠️ 将使用本地地址")
                else:
                    print(f"⚠️ FRP 功能未可用，使用本地地址: {server_name}")
                
                # 本地URL用真实端口构建，避免与实际监听不一致
                local_url = f"http://localhost:{port}/mcp" if config and config.transport == 'streamable-http' else address

                server_data = {
                    "name": server_name,
                    "url": public_url or address,
                    "description": description,
                    "transport": "http",
                    "local_url": local_url,
                    "public_url": public_url,
                    "frp_enabled": frp_enabled,
                    "tunnel_id": tunnel_id,
                    "timestamp": int(time.time())
                }
                servers.append(server_data)
            
            # 构建完整的JSON结构
            json_data = {
                "vm_id": self.vm_id,
                "session_id": self.session_id,
                "registry_url": self.registry_url,
                "servers": servers
            }
            
            # 写入文件到base_dir/.useit/目录
            json_file = os.path.join(useit_dir, "mcp_server_frp.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ JSON注册文件已生成: {json_file}")
            print(f"   VM ID: {self.vm_id}")
            print(f"   Session ID: {self.session_id}")
            print(f"   服务器数量: {len(servers)}")
            print(f"   FRP隧道数量: {len(self.active_frp_tunnels)}")
            
        except Exception as e:
            print(f"❌ 生成JSON文件失败: {e}")
    
    def _generate_single_server_json(self, config: SimpleServerConfig, address: str):
        """为单个服务器生成JSON文件（包含FRP隧道创建）"""
        try:
            import json
            import time
            
            # 确保.useit目录存在
            useit_dir = os.path.join(self.base_dir, '.useit')
            os.makedirs(useit_dir, exist_ok=True)
            
            # 优先使用记录的真实端口
            port = self.server_ports.get(config.name)
            if not port:
                port = self._extract_port_from_address(address)
            public_url = None
            frp_enabled = False
            tunnel_id = None
            
            # 通过API创建FRP隧道
            if FRP_AVAILABLE:
                try:
                    print(f"🌐 为 {config.name} 创建 FRP 隧道...")
                    result = create_frp_tunnel(port, "127.0.0.1")
                    
                    if result["success"]:
                        tunnel_data = result["data"]
                        tunnel_url = tunnel_data.get("public_url", "")
                        tunnel_id = tunnel_data.get("share_token", "")
                        
                        # 强制使用HTTP而不是HTTPS
                        if tunnel_url.startswith("https://"):
                            tunnel_url = tunnel_url.replace("https://", "http://")
                            print(f"🔄 转换为HTTP地址: {tunnel_url}")
                        
                        # 为MCP添加路径
                        if not tunnel_url.endswith("/mcp"):
                            public_url = tunnel_url.rstrip("/") + "/mcp"
                        else:
                            public_url = tunnel_url
                        
                        frp_enabled = True
                        print(f"✅ FRP 隧道创建成功: {public_url}")
                        
                        # 存储隧道ID以便清理
                        self.active_frp_tunnels[config.name] = tunnel_id
                    else:
                        print(f"❌ FRP 隧道创建失败 {config.name}: {result['error']}")
                        print(f"⚠️ 将使用本地地址")
                    
                except Exception as e:
                    print(f"❌ FRP 隧道创建异常 {config.name}: {e}")
                    print(f"⚠️ 将使用本地地址")
            else:
                print(f"⚠️ FRP 功能未可用，使用本地地址: {config.name}")
            
            local_url = f"http://localhost:{port}/mcp" if config and config.transport == 'streamable-http' else address

            server_data = {
                "name": config.name,
                "url": public_url or address,
                "description": config.description,
                "transport": "http",
                "local_url": local_url,
                "public_url": public_url,
                "frp_enabled": frp_enabled,
                "tunnel_id": tunnel_id,
                "timestamp": int(time.time())
            }
            
            # 构建完整的JSON结构
            json_data = {
                "vm_id": self.vm_id,
                "session_id": self.session_id,
                "registry_url": self.registry_url,
                "servers": [server_data]
            }
            
            # 写入文件到base_dir/.useit/目录
            json_file = os.path.join(useit_dir, "mcp_server_frp.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ JSON注册文件已生成: {json_file}")
            if public_url:
                print(f"🔗 公网地址: {public_url}")
            
        except Exception as e:
            print(f"❌ 生成JSON文件失败: {e}")
    
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
        # 关闭日志文件
        for name, f in list(self.server_log_files.items()):
            try:
                f.flush()
                f.close()
            except Exception:
                pass
            self.server_log_files.pop(name, None)
        
    def cleanup(self):
        """清理资源"""
        self.stop_all_servers()
        self._cleanup_frp_tunnels()
    
    def _cleanup_frp_tunnels(self):
        """清理FRP隧道"""
        if self.active_frp_tunnels:
            print("🛑 停止FRP隧道...")
            for server_name, tunnel_id in self.active_frp_tunnels.items():
                try:
                    result = delete_frp_tunnel(tunnel_id)
                    if result["success"]:
                        print(f"✅ FRP隧道已停止: {server_name} ({tunnel_id})")
                    else:
                        print(f"❌ 停止隧道失败 {server_name}: {result['error']}")
                except Exception as e:
                    print(f"❌ 停止隧道异常 {server_name}: {e}")
            self.active_frp_tunnels.clear()
            
            # 删除JSON文件
            try:
                import os
                json_file = os.path.join(self.base_dir, '.useit', 'mcp_server_frp.json')
                if os.path.exists(json_file):
                    os.remove(json_file)
                    print(f"✅ 已删除JSON文件: {json_file}")
            except Exception as e:
                print(f"❌ 删除JSON文件失败: {e}")
    
    def get_server_status(self) -> Dict[str, str]:
        """获取服务器状态"""
        status = {}
        for name, process in self.running_processes.items():
            if process.poll() is None:
                local_addr = self.server_addresses.get(name, 'unknown')
                
                if self.enable_frp and hasattr(self, 'active_frp_tunnels'):
                    # 从JSON文件获取FRP信息
                    try:
                        import json
                        json_file = os.path.join(self.base_dir, '.useit', 'mcp_server_frp.json')
                        with open(json_file, 'r') as f:
                            json_data = json.load(f)
                            server_info = next((s for s in json_data['servers'] if s['name'] == name), None)
                            if server_info and server_info.get('public_url'):
                                status[name] = f"运行中 - 本地: {local_addr}, 公网: {server_info['public_url']}"
                            else:
                                status[name] = f"运行中 - {local_addr} (未创建FRP隧道)"
                    except:
                        status[name] = f"运行中 - {local_addr} (无FRP信息)"
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
    parser.add_argument('--vm-id', help='虚拟机ID (FRP模式必需)')
    parser.add_argument('--session-id', help='会话ID (FRP模式必需)')
    parser.add_argument('--base-dir', help='MCP服务器基础工作目录', 
                       default=os.path.join(os.getcwd(), 'mcp_workspace'))
    parser.add_argument('--list', action='store_true', help='列出可用服务器')
    parser.add_argument('--status', action='store_true', help='显示服务器状态')
    # python simple_launcher.py --enable-frp --vm-id 123 --session-id 456 --base-dir D:\develop\New_Start\Excel\mcp_workspace --single excel_server
    args = parser.parse_args()
    
    launcher = SimpleMCPLauncher()
    launcher.enable_frp = args.enable_frp
    launcher.registry_url = args.registry_url
    launcher.vm_id = getattr(args, 'vm_id', '') or ''
    launcher.session_id = getattr(args, 'session_id', '') or ''
    
    # 设置基础工作目录
    base_dir = os.path.abspath(args.base_dir.strip('"\''))  # 移除可能的引号
    os.makedirs(base_dir, exist_ok=True)
    os.environ['MCP_BASE_DIR'] = base_dir
    launcher.base_dir = base_dir  # 直接设置launcher的base_dir
    print(f"📁 MCP基础工作目录: {base_dir}")
    
    # 检查FRP模式必需参数
    if args.enable_frp and (not launcher.vm_id or not launcher.session_id):
        print("❌ FRP模式需要提供 --vm-id 和 --session-id 参数")
        print("用法: python simple_launcher.py --enable-frp --vm-id <vm_id> --session-id <session_id>")
        return
    
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
        launcher._register_cleanup()  # 注册清理函数
        
        all_servers = launcher.get_official_servers() + launcher.load_custom_servers_config()
        target_server = next((s for s in all_servers if s.name == args.single), None)
        
        if not target_server:
            print(f"❌ 未找到服务器: {args.single}")
            return
        
        try:
            address, process = launcher.start_server(target_server)
            launcher.running_processes[target_server.name] = process
            launcher.server_addresses[target_server.name] = address
            
            # 如果启用FRP，生成单个服务器的JSON文件
            if args.enable_frp:
                launcher._generate_single_server_json(target_server, address)
            
            print(f"\n🎉 服务器 {target_server.name} 启动成功!")
            if args.enable_frp:
                print(f"📄 JSON注册文件已生成，请通过安全通道传输到服务器端")
                print(f"📁 文件路径: ./mcp_server_frp.json")
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
            print(f"   • JSON注册文件已生成: mcp_server_frp.json")
            print(f"   • 请通过安全通道传输JSON文件到服务器端进行注册")
            print(f"   • 目标注册地址: {args.registry_url}")
            print(f"   • 服务器数量: {len(addresses)}")
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