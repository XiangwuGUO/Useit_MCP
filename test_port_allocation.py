#!/usr/bin/env python3
"""
测试端口分配逻辑，找出为什么两个服务器都被分配到8003端口
"""

import sys
import os
sys.path.append('/home/ubuntu/workspace/gxw/useit_mcp_new/useit-mcp/mcp-server')

from simple_launcher import SimplePortManager, SimpleServerConfig, SimpleMCPLauncher

def test_port_allocation():
    """测试端口分配逻辑"""
    print("🔧 测试端口分配逻辑...")
    
    # 创建端口管理器
    port_manager = SimplePortManager(start_port=8002)
    
    # 模拟官方服务器配置
    configs = [
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
        )
    ]
    
    print("📋 配置的端口:")
    for config in configs:
        print(f"   {config.name}: {config.port}")
    
    print("\n🔄 分配端口:")
    addresses = {}
    
    for config in configs:
        # 模拟端口分配过程
        allocated_port = port_manager.find_available_port(config.port)
        address = f"http://localhost:{allocated_port}/mcp"
        addresses[config.name] = address
        
        print(f"   {config.name}: {config.port} → {allocated_port} ({address})")
        print(f"     已分配端口: {port_manager.allocated_ports}")
    
    print(f"\n📊 最终地址映射:")
    for name, addr in addresses.items():
        print(f"   {name}: {addr}")
    
    # 测试端口提取
    print(f"\n🔍 端口提取测试:")
    launcher = SimpleMCPLauncher()
    for name, addr in addresses.items():
        extracted_port = launcher._extract_port_from_address(addr)
        print(f"   {name}: {addr} → 端口 {extracted_port}")

def test_port_availability():
    """测试端口可用性检查"""
    print("\n🌐 测试端口可用性...")
    
    port_manager = SimplePortManager()
    test_ports = [8000, 8001, 8002, 8003, 8004, 8005]
    
    for port in test_ports:
        available = port_manager._is_port_available(port)
        status = "✅ 可用" if available else "❌ 占用"
        print(f"   端口 {port}: {status}")

if __name__ == "__main__":
    print("=" * 60)
    print("🎯 端口分配问题诊断")
    print("=" * 60)
    
    test_port_availability()
    print()
    test_port_allocation()
    
    print("\n" + "=" * 60)
    print("🔍 诊断完成")
    print("=" * 60)



