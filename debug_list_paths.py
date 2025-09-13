#!/usr/bin/env python3
"""
调试list_all_paths函数的脚本
"""
import os
import sys
from pathlib import Path

# 设置正确的MCP_BASE_DIR
os.environ['MCP_BASE_DIR'] = '/home/ubuntu/workspace/gxw/useit_mcp_new/useit_mcp_test_dir'

# 添加MCP服务器路径
server_path = Path(__file__).parent / 'mcp-server'
sys.path.insert(0, str(server_path))

# 导入filesystem服务器模块
sys.path.append(str(server_path / 'official_server' / 'filesystem'))

try:
    # 直接导入和测试
    from server import list_all_paths, BASE_DIR, get_base_dir
    
    print(f"🔍 当前工作目录: {os.getcwd()}")
    print(f"🔍 MCP_BASE_DIR环境变量: {os.environ.get('MCP_BASE_DIR', 'NOT SET')}")
    print(f"🔍 get_base_dir()返回: {get_base_dir()}")
    print(f"🔍 BASE_DIR值: {BASE_DIR}")
    print(f"🔍 BASE_DIR存在: {BASE_DIR.exists()}")
    print(f"🔍 BASE_DIR是目录: {BASE_DIR.is_dir()}")
    print(f"🔍 BASE_DIR绝对路径: {BASE_DIR.is_absolute()}")
    
    if BASE_DIR.exists():
        print(f"🔍 BASE_DIR内容: {list(BASE_DIR.iterdir())}")
    
    print("\n" + "="*50)
    print("🚀 调用list_all_paths函数...")
    
    result = list_all_paths()
    print(f"✅ 调用成功!")
    print(f"📄 返回结果: {result}")
    
    if isinstance(result, dict) and 'data' in result:
        paths = result['data'].get('paths', [])
        print(f"📊 路径数量: {len(paths)}")
        print(f"📂 前5个路径:")
        for i, path in enumerate(paths[:5]):
            print(f"  {i+1}. {path}")
    
except Exception as e:
    print(f"❌ 调用失败: {e}")
    import traceback
    traceback.print_exc()