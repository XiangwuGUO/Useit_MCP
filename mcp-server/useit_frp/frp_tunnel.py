#!/usr/bin/env python3
"""
简化版的 Tunnel 创建工具
基于 tunneling.py 的核心功能，专门用于创建隧道连接
"""

import atexit
import hashlib
import os
import platform
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import httpx
import json
import secrets

VERSION = "0.3"

# 获取机器架构
machine = platform.machine()
if machine == "x86_64":
    machine = "amd64"
elif machine == "aarch64":
    machine = "arm64"

# 二进制文件配置
BINARY_REMOTE_NAME = f"frpc_{platform.system().lower()}_{machine.lower()}"
EXTENSION = ".exe" if os.name == "nt" else ""
BINARY_URL = f"https://cdn-media.huggingface.co/frpc-gradio-{VERSION}/{BINARY_REMOTE_NAME}{EXTENSION}"

# 校验和字典
CHECKSUMS = {
    "https://cdn-media.huggingface.co/frpc-gradio-0.3/frpc_windows_amd64.exe": "14bc0ea470be5d67d79a07412bd21de8a0a179c6ac1116d7764f68e942dc9ceb",
    "https://cdn-media.huggingface.co/frpc-gradio-0.3/frpc_linux_amd64": "c791d1f047b41ff5885772fc4bf20b797c6059bbd82abb9e31de15e55d6a57c4",
    "https://cdn-media.huggingface.co/frpc-gradio-0.3/frpc_linux_arm64": "823ced25104de6dc3c9f4798dbb43f20e681207279e6ab89c40e2176ccbf70cd",
    "https://cdn-media.huggingface.co/frpc-gradio-0.3/frpc_darwin_amd64": "930f8face3365810ce16689da81b7d1941fda4466225a7bbcbced9a2916a6e15",
    "https://cdn-media.huggingface.co/frpc-gradio-0.3/frpc_darwin_arm64": "dfac50c690aca459ed5158fad8bfbe99f9282baf4166cf7c410a6673fbc1f327",
}

# 文件路径配置
CURRENT_DIR = Path(__file__).parent
LOCAL_BINARY_PATH = CURRENT_DIR / f"{BINARY_REMOTE_NAME}_v{VERSION}"

# 备用路径（如果本地没有的话）
HOME_DIR = Path.home()
BINARY_FOLDER = HOME_DIR / ".frpc"
BINARY_FILENAME = f"{BINARY_REMOTE_NAME}_v{VERSION}"
BACKUP_BINARY_PATH = BINARY_FOLDER / BINARY_FILENAME

TUNNEL_TIMEOUT_SECONDS = 30
CHUNK_SIZE = 128


class TunnelManager:
    """隧道管理器"""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.tunnels = self._load_tunnels()

    def _load_tunnels(self) -> dict:
        """从文件加载隧道信息"""
        if not self.state_file.exists():
            return {}
        with open(self.state_file, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save_tunnels(self):
        """保存隧道信息到文件"""
        with open(self.state_file, "w") as f:
            json.dump(self.tunnels, f, indent=4)

    def add_tunnel(self, tunnel_info: dict):
        """添加一个新隧道"""
        self.tunnels[tunnel_info["share_token"]] = tunnel_info
        self._save_tunnels()

    def remove_tunnel(self, tunnel_id: str):
        """移除一个隧道"""
        if tunnel_id in self.tunnels:
            del self.tunnels[tunnel_id]
            self._save_tunnels()

    def get_tunnel(self, tunnel_id: str) -> Optional[dict]:
        """获取一个隧道的信息"""
        return self.tunnels.get(tunnel_id)

    def find_tunnel_by_url(self, url: str) -> Optional[dict]:
        """通过公网URL查找隧道"""
        for tunnel in self.tunnels.values():
            if tunnel.get("public_url") == url:
                return tunnel
        return None

    def get_all_tunnels(self) -> List[dict]:
        """获取所有隧道的信息"""
        return list(self.tunnels.values())

    def list_tunnels(self):
        """列出所有正在运行的隧道"""
        if not self.tunnels:
            print("当前没有正在运行的隧道。")
            return

        print(f"{'ID':<20} {'本地服务':<25} {'公网URL':<40} {'PID':<10}")
        print("-" * 95)

        dead_tunnels = []
        for tunnel_id, info in self.tunnels.items():
            if not self._is_pid_running(info["pid"]):
                dead_tunnels.append(tunnel_id)
                continue
            
            local_service = f"{info['local_host']}:{info['local_port']}"
            print(f"{tunnel_id:<20} {local_service:<25} {info['public_url']:<40} {info['pid']:<10}")

        if dead_tunnels:
            print("\n发现已失效的隧道，正在清理...")
            for tunnel_id in dead_tunnels:
                self.remove_tunnel(tunnel_id)
            print("清理完成。")

    @staticmethod
    def _is_pid_running(pid: int) -> bool:
        """检查进程ID是否存在"""
        if platform.system() == "Windows":
            try:
                # 使用 tasklist 命令检查 PID
                output = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}"], text=True)
                return str(pid) in output
            except subprocess.CalledProcessError:
                return False  # 如果命令失败，通常意味着进程不存在
        else:
            # POSIX 系统
            try:
                os.kill(pid, 0)
            except OSError:
                return False
            else:
                return True

    def stop_tunnel(self, tunnel_id: str):
        """停止一个隧道"""
        tunnel_info = self.get_tunnel(tunnel_id)
        if not tunnel_info:
            print(f"错误: 未找到ID为 '{tunnel_id}' 的隧道。")
            return

        pid = tunnel_info["pid"]
        print(f"正在停止隧道 {tunnel_id} (PID: {pid})...")

        if self._is_pid_running(pid):
            try:
                proc = subprocess.Popen(["kill", str(pid)] if platform.system() != "Windows" else ["taskkill", "/PID", str(pid), "/F"])
                proc.wait(timeout=5)
                print(f"成功停止进程 {pid}。")
            except Exception as e:
                print(f"停止进程 {pid} 失败: {e}")
        else:
            print(f"进程 {pid} 已不存在。")

        self.remove_tunnel(tunnel_id)
        print(f"隧道 {tunnel_id} 已被移除。")


class FrpTunnel:
    """简化的隧道类"""
    
    def __init__(self, local_port: int, local_host: str = "127.0.0.1", manager: Optional[TunnelManager] = None):
        """
        初始化隧道
        
        Args:
            local_port: 本地端口
            local_host: 本地主机地址，默认为 127.0.0.1
        """
        self.local_port = local_port
        self.local_host = local_host
        self.proc = None
        self.public_url = None
        self.pid = None
        self.manager = manager
        
        # 远程服务器配置
        self.remote_host = "useit.run"
        self.remote_port = 7000
        # 使用毫秒级时间戳 + 随机字符串确保唯一性
        self.share_token = f"gradio_{int(time.time() * 1000)}_{secrets.token_hex(2)}"
        self.log_file_path = CURRENT_DIR / f"logs/{self.share_token}.log"
        
    def get_binary_path(self):
        """获取二进制文件路径，优先使用本地文件"""
        # 优先检查项目目录下的二进制文件
        if LOCAL_BINARY_PATH.exists():
            print(f"使用本地二进制文件: {LOCAL_BINARY_PATH}")
            return LOCAL_BINARY_PATH
            
        # 检查备用路径
        if BACKUP_BINARY_PATH.exists():
            print(f"使用缓存的二进制文件: {BACKUP_BINARY_PATH}")
            return BACKUP_BINARY_PATH
            
        # 如果都不存在，下载到备用路径
        print(f"本地未找到二进制文件，将下载到: {BACKUP_BINARY_PATH}")
        self.download_binary()
        return BACKUP_BINARY_PATH
    
    def download_binary(self):
        """下载 frpc 二进制文件"""
        if BACKUP_BINARY_PATH.exists():
            print(f"二进制文件已存在: {BACKUP_BINARY_PATH}")
            return
            
        print(f"正在下载 frpc 二进制文件...")
        BINARY_FOLDER.mkdir(parents=True, exist_ok=True)
        
        try:
            resp = httpx.get(BINARY_URL, timeout=30)
            
            if resp.status_code == 403:
                raise OSError(
                    f"无法设置共享链接，当前平台不兼容。"
                    f"平台信息: {platform.uname()}"
                )
            
            resp.raise_for_status()
            
            # 保存文件
            with open(BACKUP_BINARY_PATH, "wb") as file:
                file.write(resp.content)
                
            # 添加执行权限
            st = os.stat(BACKUP_BINARY_PATH)
            os.chmod(BACKUP_BINARY_PATH, st.st_mode | stat.S_IEXEC)
            
            # 验证校验和
            if BINARY_URL in CHECKSUMS:
                self._verify_checksum()
                
            print(f"二进制文件下载完成: {BACKUP_BINARY_PATH}")
            
        except Exception as e:
            print(f"下载失败: {e}")
            raise
            
    def _verify_checksum(self):
        """验证文件校验和"""
        sha = hashlib.sha256()
        with open(BACKUP_BINARY_PATH, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE * sha.block_size), b""):
                sha.update(chunk)
        calculated_hash = sha.hexdigest()
        
        if calculated_hash != CHECKSUMS[BINARY_URL]:
            raise ValueError("文件校验和不匹配，可能文件已损坏")
            
    def start_tunnel(self) -> Optional[str]:
        """
        启动隧道连接
        
        Returns:
            公网 URL
        """
        print(f"正在为本地服务 {self.local_host}:{self.local_port} 创建隧道...")
        
        # 获取二进制文件路径
        binary_path = self.get_binary_path()
        
        # 构建命令
        command = [
            str(binary_path),
            "http",
            "-n", self.share_token,
            "-l", str(self.local_port),
            "-i", self.local_host,
            "--uc",
            "--sd", "random",
            "--ue", 
            "--server_addr", f"{self.remote_host}:{self.remote_port}",
            "--disable_log_color",
        ]
        
        # 添加调试信息
        print(f"隧道服务器: {self.remote_host}:{self.remote_port}")
        print(f"本地服务: {self.local_host}:{self.local_port}")
        print(f"令牌: {self.share_token}")
        
        print(f"执行命令: {' '.join(command)}")
        
        # 确保日志目录存在
        self.log_file_path.parent.mkdir(exist_ok=True)

        # 启动进程，并将输出重定向到日志文件
        with open(self.log_file_path, "w") as log_file:
            self.proc = subprocess.Popen(
                command, 
                stdout=log_file, 
                stderr=subprocess.STDOUT,
                text=True
            )
        self.pid = self.proc.pid
        
        # 读取公网 URL
        self.public_url = self._read_url_from_output()
        
        if self.public_url:
            print(f"隧道创建成功!")
            print(f"本地地址: http://{self.local_host}:{self.local_port}")
            print(f"公网地址: {self.public_url}")
            print(f"隧道 ID: {self.share_token}")
            print(f"日志文件: {self.log_file_path}")

            if self.manager:
                self.manager.add_tunnel({
                    "share_token": self.share_token,
                    "local_port": self.local_port,
                    "local_host": self.local_host,
                    "public_url": self.public_url,
                    "pid": self.pid,
                    "log_file": str(self.log_file_path)
                })
        else:
            print("创建隧道失败，请检查日志文件获取更多信息。")
            print(f"日志文件: {self.log_file_path}")

        return self.public_url
        
    def _read_url_from_output(self) -> Optional[str]:
        """从输出流中读取公网 URL"""
        start_time = time.time()
        
        while time.time() - start_time < TUNNEL_TIMEOUT_SECONDS:
            if not self.log_file_path.exists():
                time.sleep(0.2)
                continue

            with open(self.log_file_path, "r") as f:
                log_content = f.read()

            # 查找成功消息
            if "start proxy success" in log_content:
                result = re.search(r"start proxy success: (.+)", log_content)
                if result:
                    url = result.group(1).strip()
                    if url.startswith("https://"):
                        http_url = url.replace("https://", "http://")
                        print(f"🔗 生成的地址:")
                        print(f"   HTTPS: {url}")
                        print(f"   HTTP:  {http_url}")
                        print(f"💡 如果HTTPS无法访问，请尝试HTTP版本")
                    return url
            
            # 检查错误
            if "login to server failed" in log_content:
                print(f"登录服务器失败。请查看日志获取详细信息: {self.log_file_path}", file=sys.stderr)
                return None

            time.sleep(0.5)

        print(f"隧道创建超时。请查看日志获取详细信息: {self.log_file_path}", file=sys.stderr)
        return None
            

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FRP 隧道管理工具")
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用的命令")

    # 'start' 命令
    parser_start = subparsers.add_parser("start", help="启动一个新的隧道")
    parser_start.add_argument("port", type=int, help="本地服务的端口号")
    parser_start.add_argument("--host", default="127.0.0.1", help="本地服务的地址 (默认: 127.0.0.1)")

    # 'list' 命令
    parser_list = subparsers.add_parser("list", help="列出所有正在运行的隧道")

    # 'stop' 命令
    parser_stop = subparsers.add_parser("stop", help="停止一个正在运行的隧道")
    parser_stop.add_argument("tunnel_id", help="要停止的隧道的ID")

    args = parser.parse_args()
    
    manager = TunnelManager(CURRENT_DIR / "tunnels.json")

    if args.command == "start":
        try:
            tunnel = FrpTunnel(args.port, args.host, manager=manager)
            tunnel.start_tunnel()
        except Exception as e:
            print(f"启动隧道时发生错误: {e}")
            sys.exit(1)

    elif args.command == "list":
        manager.list_tunnels()

    elif args.command == "stop":
        manager.stop_tunnel(args.tunnel_id)
