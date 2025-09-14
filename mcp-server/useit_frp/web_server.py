#!/usr/bin/env python3
"""
简单的Web服务器，用于运行HTML网页并通过隧道发布到公网
"""

import os
import sys
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# 导入我们的隧道模块
from frp_tunnel import FrpTunnel, TunnelManager, CURRENT_DIR


class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    """自定义HTTP请求处理器"""
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")
        
    def end_headers(self):
        """添加自定义响应头"""
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


class WebServer:
    """Web服务器类"""
    
    def __init__(self, port=8000, host='127.0.0.1'):
        """
        初始化Web服务器
        
        Args:
            port: 服务器端口，默认8000
            host: 服务器主机地址，默认127.0.0.1
        """
        self.port = port
        self.host = host
        self.server = None
        self.tunnel = None
        self.tunnel_id = None
        self.manager = TunnelManager(CURRENT_DIR / "tunnels.json")
        self.server_thread = None
        
    def start_server(self):
        """启动Web服务器"""
        try:
            # 创建HTTP服务器
            self.server = HTTPServer((self.host, self.port), CustomHTTPRequestHandler)
            
            print(f"🚀 启动Web服务器...")
            print(f"📍 本地地址: http://{self.host}:{self.port}")
            print(f"📁 服务目录: {Path.cwd()}")
            
            # 在单独线程中运行服务器
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            print("✅ Web服务器启动成功!")
            return True
            
        except OSError as e:
            if e.errno == 10048:  # Windows: 端口被占用
                print(f"❌ 端口 {self.port} 已被占用，请尝试其他端口")
            else:
                print(f"❌ 启动服务器失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 启动服务器失败: {e}")
            return False
            
    def start_tunnel(self):
        """启动隧道连接"""
        try:
            print(f"\n🌐 正在创建隧道连接...")
            self.tunnel = FrpTunnel(self.port, self.host, self.manager)
            public_url = self.tunnel.start_tunnel()
            
            if public_url:
                self.tunnel_id = self.tunnel.share_token
                print(f"\n🎉 隧道创建成功!")
                print(f"🌍 公网地址: {public_url}")
                print(f"📱 现在任何人都可以通过公网链接访问你的网站了!")
            
            return public_url
            
        except Exception as e:
            print(f"❌ 创建隧道失败: {e}")
            return None
            
    def stop(self):
        """停止服务器和隧道"""
        print(f"\n🛑 正在停止服务...")
        
        if self.tunnel_id:
            self.manager.stop_tunnel(self.tunnel_id)
            
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            
        print("✅ 服务已停止")
        
    def run(self, create_tunnel=True):
        """
        运行Web服务器和隧道
        
        Args:
            create_tunnel: 是否创建隧道，默认True
        """
        try:
            # 检查HTML文件是否存在
            if not Path("index.html").exists():
                print("❌ 找不到 index.html 文件")
                print("请确保 index.html 文件在当前目录中")
                return
                
            # 启动Web服务器
            if not self.start_server():
                return
                
            # 创建隧道（如果需要）
            public_url = None
            if create_tunnel:
                public_url = self.start_tunnel()
                
            # 显示访问信息
            print(f"\n" + "="*60)
            print(f"🌟 服务器运行信息")
            print(f"="*60)
            print(f"📍 本地访问: http://{self.host}:{self.port}")
            if public_url:
                print(f"🌍 公网访问: {public_url}")
            print(f"📁 网站目录: {Path.cwd()}")
            print(f"📄 主页文件: index.html")
            print(f"="*60)
            
            if public_url:
                print(f"\n💡 提示:")
                print(f"   • 你可以把公网链接分享给任何人")
                print(f"   • 修改 index.html 后刷新页面即可看到更新")
                print(f"   • 按 Ctrl+C 停止服务")
            else:
                print(f"\n💡 提示:")
                print(f"   • 只启动了本地服务器，未创建公网隧道")
                print(f"   • 使用 --tunnel 参数可以创建公网隧道")
                print(f"   • 按 Ctrl+C 停止服务")
                
            print(f"\n⏰ 服务器启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🔄 等待连接中...")
            
            # 保持服务器运行
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n\n👋 收到停止信号...")
        except Exception as e:
            print(f"❌ 运行时错误: {e}")
        finally:
            self.stop()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="启动Web服务器并可选择创建公网隧道")
    parser.add_argument("--port", "-p", type=int, default=8888, help="服务器端口 (默认: 8888)")
    parser.add_argument("--host", default="127.0.0.1", help="服务器主机地址 (默认: 127.0.0.1)")
    parser.add_argument("--no-tunnel", action="store_true", help="不创建公网隧道，只启动本地服务器")
    
    args = parser.parse_args()
    
    print("🌟 Web服务器 + 隧道工具")
    print("="*40)
    
    # 创建并运行服务器
    server = WebServer(args.port, args.host)
    server.run(create_tunnel=not args.no_tunnel)


if __name__ == "__main__":
    main()
