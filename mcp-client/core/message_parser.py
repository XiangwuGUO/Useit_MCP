#!/usr/bin/env python3
"""
Agent消息解析器
通过解析LangGraph Agent的执行消息来捕获工具调用事件
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, AsyncGenerator
from uuid import uuid4

from .stream_models import StreamEvent, ToolStartEvent, ToolResultEvent

logger = logging.getLogger(__name__)


class AgentMessageParser:
    """Agent消息解析器，从执行消息中提取工具调用事件"""
    
    def __init__(self, event_queue: asyncio.Queue, task_id: str):
        self.event_queue = event_queue
        self.task_id = task_id
        self.step_counter = 0
        self.tool_start_times = {}
        self.active_tools = {}
        
        print(f"🎯 [PARSER] 消息解析器已创建，任务ID: {task_id}")
        logger.info(f"AgentMessageParser 已创建，任务ID: {task_id}")
    
    async def parse_agent_result(self, result: Dict[str, Any]) -> AsyncGenerator[StreamEvent, None]:
        """解析Agent执行结果，生成工具事件"""
        
        print(f"🔍 [PARSER] 开始解析Agent结果")
        print(f"🔍 [PARSER] 结果类型: {type(result)}")
        print(f"🔍 [PARSER] 结果键: {list(result.keys()) if isinstance(result, dict) else 'NOT_DICT'}")
        logger.info(f"开始解析Agent执行结果")
        
        try:
            # 获取消息列表
            messages = result.get('messages', [])
            if not messages:
                print(f"⚠️ [PARSER] 没有找到消息")
                # 尝试直接打印整个结果结构用于调试
                print(f"🔍 [PARSER] 完整结果: {json.dumps(result, indent=2, default=str)[:500]}...")
                return
            
            print(f"📝 [PARSER] 找到 {len(messages)} 个消息")
            
            # 解析每个消息，查找工具调用
            for i, message in enumerate(messages):
                print(f"🔍 [PARSER] 解析第 {i+1} 个消息")
                async for event in self._parse_single_message(message, i):
                    yield event
                    
        except Exception as e:
            logger.error(f"解析Agent结果失败: {e}", exc_info=True)
            print(f"❌ [PARSER] 解析失败: {e}")
    
    async def _parse_single_message(self, message: Any, message_index: int) -> AsyncGenerator[StreamEvent, None]:
        """解析单个消息"""
        
        try:
            # 检查消息类型和内容
            message_type = getattr(message, '__class__', type(message)).__name__
            print(f"   📋 [PARSER] 消息类型: {message_type}")
            
            # 获取消息内容
            content = getattr(message, 'content', None)
            additional_kwargs = getattr(message, 'additional_kwargs', {})
            tool_calls = additional_kwargs.get('tool_calls', [])
            
            print(f"   📄 [PARSER] 内容: {str(content)[:100] if content else 'None'}...")
            print(f"   🔧 [PARSER] 工具调用数: {len(tool_calls)}")
            
            # 如果有工具调用，解析它们
            if tool_calls:
                for tool_call in tool_calls:
                    async for event in self._parse_tool_call(tool_call, message_index):
                        yield event
            
            # 检查是否是工具响应消息
            if hasattr(message, 'tool_call_id'):
                async for event in self._parse_tool_response(message, message_index):
                    yield event
                    
        except Exception as e:
            logger.error(f"解析消息失败: {e}", exc_info=True)
            print(f"❌ [PARSER] 解析消息失败: {e}")
    
    async def _parse_tool_call(self, tool_call: Dict[str, Any], message_index: int) -> AsyncGenerator[StreamEvent, None]:
        """解析工具调用"""
        
        try:
            self.step_counter += 1
            step_number = self.step_counter
            
            # 提取工具信息
            tool_call_id = tool_call.get('id', str(uuid4()))
            function = tool_call.get('function', {})
            tool_name = function.get('name', 'unknown_tool')
            arguments_str = function.get('arguments', '{}')
            
            print(f"🔧 [PARSER] 工具开始: {tool_name} (步骤 {step_number})")
            logger.info(f"解析到工具调用: {tool_name} (步骤 {step_number})")
            
            # 记录开始时间
            start_time = time.time()
            self.tool_start_times[tool_call_id] = start_time
            self.active_tools[tool_call_id] = {
                'tool_name': tool_name,
                'step_number': step_number,
                'start_time': start_time,
                'arguments_str': arguments_str
            }
            
            # 解析参数
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError as e:
                logger.warning(f"解析工具参数失败: {e}")
                arguments = {"raw_arguments": arguments_str}
            
            # 提取服务器名称
            server_name = self._extract_server_name(tool_name)
            
            # 创建工具开始事件
            tool_start_event = ToolStartEvent(
                task_id=self.task_id,
                step_number=step_number,
                tool_name=tool_name,
                server_name=server_name,
                arguments=arguments,
                reasoning=f"执行工具 {tool_name} 来处理请求"
            )
            
            # 发送事件
            stream_event = StreamEvent(
                type="tool_start",
                data=tool_start_event.dict()
            )
            
            await self.event_queue.put(stream_event)
            yield stream_event
            
        except Exception as e:
            logger.error(f"解析工具调用失败: {e}", exc_info=True)
            print(f"❌ [PARSER] 解析工具调用失败: {e}")
    
    async def _parse_tool_response(self, message: Any, message_index: int) -> AsyncGenerator[StreamEvent, None]:
        """解析工具响应"""
        
        try:
            tool_call_id = getattr(message, 'tool_call_id', None)
            if not tool_call_id or tool_call_id not in self.active_tools:
                print(f"⚠️ [PARSER] 工具响应找不到对应的开始信息: {tool_call_id}")
                return
            
            tool_info = self.active_tools[tool_call_id]
            tool_name = tool_info['tool_name']
            step_number = tool_info['step_number']
            start_time = tool_info['start_time']
            
            # 计算执行时间
            end_time = time.time()
            execution_time = end_time - start_time
            
            print(f"✅ [PARSER] 工具完成: {tool_name} (耗时 {execution_time:.2f}秒)")
            logger.info(f"工具执行完成: {tool_name} (耗时 {execution_time:.2f}秒)")
            
            # 提取结果
            content = getattr(message, 'content', '')
            result = self._process_tool_output(content)
            
            # 提取服务器名称
            server_name = self._extract_server_name(tool_name)
            
            # 创建工具结果事件
            tool_result_event = ToolResultEvent(
                task_id=self.task_id,
                step_number=step_number,
                tool_name=tool_name,
                server_name=server_name,
                result=result,
                status="success",
                execution_time=execution_time
            )
            
            # 发送事件
            stream_event = StreamEvent(
                type="tool_result",
                data=tool_result_event.dict()
            )
            
            await self.event_queue.put(stream_event)
            yield stream_event
            
            # 清理工具信息
            del self.active_tools[tool_call_id]
            if tool_call_id in self.tool_start_times:
                del self.tool_start_times[tool_call_id]
                
        except Exception as e:
            logger.error(f"解析工具响应失败: {e}", exc_info=True)
            print(f"❌ [PARSER] 解析工具响应失败: {e}")
    
    def _extract_server_name(self, tool_name: str) -> str:
        """从工具名称中提取服务器名称"""
        # 工具名称格式通常为: server_name__tool_name
        if "__" in tool_name:
            return tool_name.split("__")[0]
        return "unknown"
    
    def _process_tool_output(self, output: str) -> Any:
        """处理工具输出结果"""
        try:
            # 尝试解析为JSON
            if output.strip().startswith('{') or output.strip().startswith('['):
                return json.loads(output)
            else:
                # 如果不是JSON，返回原始字符串
                return output
        except json.JSONDecodeError:
            # 解析失败，返回原始字符串
            return output
    
    def get_current_step_count(self) -> int:
        """获取当前步骤计数"""
        return self.step_counter
    
    def get_active_tools_count(self) -> int:
        """获取当前活跃工具数量"""
        return len(self.active_tools)