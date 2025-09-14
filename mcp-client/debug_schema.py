#!/usr/bin/env python3
"""
调试工具schema结构
"""
import asyncio
import sys
import json
sys.path.append('.')

from core.client_manager import ClientManager
from langchain_mcp_adapters.client import MultiServerMCPClient

async def debug_tool_schema():
    # 假设服务器配置
    mcp_config = {
        "filesystem": {
            "transport": "streamable-http",
            "url": "http://localhost:8005/mcp",
            "headers": {"Content-Type": "application/json"},
        }
    }
    
    try:
        # 创建MCP客户端
        mcp_client = MultiServerMCPClient(mcp_config)
        
        # 获取工具
        tools = await mcp_client.get_tools()
        
        print(f"获取到 {len(tools)} 个工具\n")
        
        # 详细检查第一个工具
        if tools:
            tool = tools[0]
            print(f"工具名称: {tool.name}")
            print(f"工具类型: {type(tool).__name__}")
            print(f"工具属性: {[attr for attr in dir(tool) if not attr.startswith('_')]}")
            
            if hasattr(tool, 'args_schema'):
                schema = tool.args_schema
                print(f"\nargs_schema 类型: {type(schema).__name__}")
                print(f"args_schema 值: {schema}")
                
                if isinstance(schema, dict):
                    print(f"字典keys: {list(schema.keys())}")
                    if 'properties' in schema:
                        print(f"properties: {list(schema['properties'].keys())}")
                        # 打印每个属性的详细信息
                        for prop_name, prop_info in schema['properties'].items():
                            print(f"  {prop_name}: {prop_info}")
                
                # 尝试JSON序列化
                try:
                    json_schema = json.dumps(schema, indent=2)
                    print(f"\nJSON序列化成功:\n{json_schema}")
                except Exception as e:
                    print(f"\nJSON序列化失败: {e}")
            
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_tool_schema())