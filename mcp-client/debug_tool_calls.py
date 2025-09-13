#!/usr/bin/env python3
"""
Debug script to test tool calls directly
"""

import asyncio
import os

# Set API key
os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-api03-dummy'

from core.streaming_executor import StreamingLangChainExecutor
from core.client_manager import ClientManager
from core.api_models import TaskRequest

async def test_tool_calls():
    print("=== Debugging Tool Calls ===")
    
    # 1. Setup
    cm = ClientManager()
    await cm.add_server_to_client('demo_vm', 'demo_session', 'filesystem', 'http://localhost:8003/mcp')
    executor = StreamingLangChainExecutor(cm, 'sk-ant-api03-dummy')
    
    # 2. Create simple agent to test tool calls directly
    print("\n1. Creating simple agent...")
    agent = await executor._get_simple_agent('demo_vm', 'demo_session')
    print(f"Agent created: {type(agent).__name__}")
    
    # 3. Test direct invocation with simple request
    print("\n2. Testing direct agent invocation...")
    messages = [{"role": "user", "content": "List the files in the current directory"}]
    
    try:
        result = await agent.ainvoke(
            {"messages": messages},
            config={
                "recursion_limit": 5,
                "configurable": {"thread_id": "debug_test"}
            }
        )
        print(f"Result type: {type(result)}")
        print(f"Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        
        if 'messages' in result:
            print(f"Message count: {len(result['messages'])}")
            for i, msg in enumerate(result['messages']):
                print(f"  Message {i}: {type(msg).__name__}")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    print(f"    Tool calls: {len(msg.tool_calls)}")
                    for tc in msg.tool_calls:
                        print(f"      - {getattr(tc, 'name', tc.get('name', 'unknown'))}")
                elif hasattr(msg, 'content'):
                    print(f"    Content: {str(msg.content)[:100]}...")
        
    except Exception as e:
        print(f"Error in agent invocation: {e}")
        import traceback
        traceback.print_exc()

    # 4. Test streaming agent
    print("\n3. Testing streaming agent...")
    try:
        streaming_agent = await executor._get_streaming_agent_v2('demo_vm', 'demo_session')
        print(f"Streaming agent created: {type(streaming_agent).__name__}")
        print(f"Tools available: {len(streaming_agent.tools)}")
        print(f"Tool names: {list(streaming_agent.tools.keys())}")
        
        # Test a simple conversation
        import queue
        event_queue = asyncio.Queue()
        
        from langchain_core.messages import HumanMessage
        test_messages = [HumanMessage(content="List files in current directory")]
        
        result = await streaming_agent.astream_invoke(
            messages=test_messages,
            event_queue=event_queue,
            task_id="debug_test",
            max_iterations=3
        )
        
        print(f"Streaming result: {result}")
        
    except Exception as e:
        print(f"Error in streaming agent test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tool_calls())