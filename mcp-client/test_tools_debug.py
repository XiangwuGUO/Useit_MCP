#!/usr/bin/env python3
"""
测试MCP工具的名称和描述是否正确传输
"""

import asyncio
import sys
import os
sys.path.append('.')

from core.client_manager import ClientManager
from langchain_mcp_adapters.client import MultiServerMCPClient

async def test_mcp_tools():
    """测试MCP工具信息"""
    
    # 创建客户端管理器
    client_manager = ClientManager()
    
    # 手动添加文件系统客户端用于测试
    filesystem_client_info = {
        "server_name": "filesystem",
        "server_type": "filesystem",
        "connection_url": "http://localhost:8003",
        "transport": "streamable-http"
    }
    
    await client_manager.add_client(**filesystem_client_info)
    
    # 构建MCP配置
    mcp_config = {}
    for server_name, client_info in client_manager.clients.items():
        mcp_config[server_name] = {
            "transport": "streamable-http",
            "url": client_info.connection_url,
            "headers": {"Content-Type": "application/json"},
        }
    
    print(f"MCP配置: {mcp_config}")
    
    # 创建MCP客户端
    mcp_client = MultiServerMCPClient(mcp_config)
    
    try:
        # 获取工具
        tools = await mcp_client.get_tools()
        
        print(f"\n🔍 获取到 {len(tools)} 个工具:")
        
        for i, tool in enumerate(tools):
            print(f"\n工具 {i+1}:")
            print(f"  类型: {type(tool).__name__}")
            print(f"  名称: {getattr(tool, 'name', 'NO_NAME')}")
            print(f"  描述: {getattr(tool, 'description', 'NO_DESC')}")
            print(f"  属性: {[attr for attr in dir(tool) if not attr.startswith('_')]}")
            
            # 检查args_schema
            if hasattr(tool, 'args_schema') and tool.args_schema:
                print(f"  args_schema类型: {type(tool.args_schema).__name__}")
                if hasattr(tool.args_schema, 'model_fields'):
                    fields = getattr(tool.args_schema, 'model_fields', {})
                    print(f"  参数字段: {list(fields.keys())}")
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(test_mcp_tools())