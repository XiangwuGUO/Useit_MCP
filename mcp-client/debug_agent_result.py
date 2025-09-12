#!/usr/bin/env python3
"""
调试Agent结果结构
"""

import json
import sys
sys.path.append('.')

from simple_mcp_demo import call_mcp_client_streaming

def main():
    """直接调用流式接口并打印原始结果"""
    
    # 配置
    mcp_client_url = "http://localhost:8080"
    vm_id = "debug_vm"
    session_id = "debug_session"
    
    print("🔍 调试Agent结果结构...")
    
    # 先注册服务器
    from simple_mcp_demo import register_from_json
    json_path = "/home/ubuntu/workspace/gxw/useit_mcp_new/useit_mcp_test_dir/.useit/mcp_server_frp.json"
    register_from_json(mcp_client_url, vm_id, session_id, json_path)
    
    # 直接调用流式接口观察调试输出
    success, result = call_mcp_client_streaming(
        mcp_client_url=mcp_client_url,
        vm_id=vm_id,
        session_id=session_id,
        mcp_server_name="filesystem",
        task_description="简单测试：显示当前目录的第一个文件",
    )
    
    print(f"\n🎯 调试完成，成功: {success}")

if __name__ == "__main__":
    main()