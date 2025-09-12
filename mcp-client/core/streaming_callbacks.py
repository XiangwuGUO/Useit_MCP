#!/usr/bin/env python3
"""
流式工具调用回调处理器
使用 LangChain 回调机制监听工具调用事件
"""

import asyncio
import time
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .stream_models import StreamEvent, ToolStartEvent, ToolResultEvent

logger = logging.getLogger(__name__)


class StreamingToolCallbackHandler(BaseCallbackHandler):
    """流式工具调用回调处理器"""
    
    def __init__(self, event_queue: asyncio.Queue, task_id: str):
        super().__init__()
        self.event_queue = event_queue
        self.task_id = task_id
        self.step_counter = 0
        self.tool_start_times = {}
        self.active_tools = {}  # 跟踪活跃的工具调用
        
        print(f"🎯 [CALLBACK] 回调处理器已创建，任务ID: {task_id}")
        logger.info(f"StreamingToolCallbackHandler 已创建，任务ID: {task_id}")
        
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """工具开始执行时的回调"""
        
        self.step_counter += 1
        step_number = self.step_counter
        tool_name = serialized.get('name', 'unknown_tool')
        run_id = run_id or str(uuid4())
        
        print(f"🔧 [CALLBACK] 工具开始执行: {tool_name} (步骤 {step_number})")
        logger.info(f"工具开始执行: {tool_name} (步骤 {step_number})")
        
        # 记录开始时间和工具信息
        start_time = time.time()
        self.tool_start_times[run_id] = start_time
        self.active_tools[run_id] = {
            'tool_name': tool_name,
            'step_number': step_number,
            'start_time': start_time,
            'input': input_str
        }
        
        # 解析工具参数
        try:
            arguments = self._parse_tool_input(input_str)
        except Exception as e:
            logger.warning(f"解析工具输入失败: {e}")
            arguments = {"input": input_str}
        
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
        
        # 发送事件到队列
        stream_event = StreamEvent(
            type="tool_start",
            data=tool_start_event.dict()
        )
        
        # 异步发送事件
        self._send_event_async(stream_event)
    
    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """工具执行结束时的回调"""
        
        if not run_id or run_id not in self.active_tools:
            logger.warning(f"工具结束回调找不到对应的开始信息: {run_id}")
            return
        
        tool_info = self.active_tools[run_id]
        tool_name = tool_info['tool_name']
        step_number = tool_info['step_number']
        start_time = tool_info['start_time']
        
        # 计算执行时间
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"✅ [CALLBACK] 工具执行完成: {tool_name} (耗时 {execution_time:.2f}秒)")
        logger.info(f"工具执行完成: {tool_name} (耗时 {execution_time:.2f}秒)")
        
        # 提取服务器名称
        server_name = self._extract_server_name(tool_name)
        
        # 处理输出结果
        result = self._process_tool_output(output)
        
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
        
        # 发送事件到队列
        stream_event = StreamEvent(
            type="tool_result",
            data=tool_result_event.dict()
        )
        
        # 异步发送事件
        self._send_event_async(stream_event)
        
        # 清理工具信息
        del self.active_tools[run_id]
        if run_id in self.tool_start_times:
            del self.tool_start_times[run_id]
    
    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """工具执行错误时的回调"""
        
        if not run_id or run_id not in self.active_tools:
            logger.warning(f"工具错误回调找不到对应的开始信息: {run_id}")
            return
        
        tool_info = self.active_tools[run_id]
        tool_name = tool_info['tool_name']
        step_number = tool_info['step_number']
        start_time = tool_info['start_time']
        
        # 计算执行时间
        end_time = time.time()
        execution_time = end_time - start_time
        
        logger.error(f"工具执行失败: {tool_name} - {error}")
        
        # 提取服务器名称
        server_name = self._extract_server_name(tool_name)
        
        # 创建工具错误事件
        tool_result_event = ToolResultEvent(
            task_id=self.task_id,
            step_number=step_number,
            tool_name=tool_name,
            server_name=server_name,
            result=str(error),
            status="error",
            execution_time=execution_time,
            error_message=str(error)
        )
        
        # 发送事件到队列
        stream_event = StreamEvent(
            type="tool_result",
            data=tool_result_event.dict()
        )
        
        # 异步发送事件
        self._send_event_async(stream_event)
        
        # 清理工具信息
        del self.active_tools[run_id]
        if run_id in self.tool_start_times:
            del self.tool_start_times[run_id]
    
    def _parse_tool_input(self, input_str: str) -> Dict[str, Any]:
        """解析工具输入参数"""
        try:
            import json
            # 尝试解析为JSON
            if input_str.strip().startswith('{'):
                return json.loads(input_str)
            else:
                # 如果不是JSON，作为字符串参数
                return {"input": input_str}
        except json.JSONDecodeError:
            # 解析失败，作为字符串参数
            return {"input": input_str}
    
    def _extract_server_name(self, tool_name: str) -> str:
        """从工具名称中提取服务器名称"""
        # 工具名称格式通常为: server_name__tool_name
        if "__" in tool_name:
            return tool_name.split("__")[0]
        return "unknown"
    
    def _process_tool_output(self, output: str) -> Any:
        """处理工具输出结果"""
        try:
            import json
            # 尝试解析为JSON
            if output.strip().startswith('{') or output.strip().startswith('['):
                return json.loads(output)
            else:
                # 如果不是JSON，返回原始字符串
                return output
        except json.JSONDecodeError:
            # 解析失败，返回原始字符串
            return output
    
    def _send_event_async(self, event: StreamEvent):
        """异步发送事件到队列"""
        try:
            # 获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在当前循环中安排协程
                loop.create_task(self.event_queue.put(event))
            else:
                # 如果没有运行的循环，直接运行
                asyncio.run(self.event_queue.put(event))
        except RuntimeError:
            # 处理没有事件循环的情况
            logger.warning("无法发送流式事件：没有活跃的事件循环")
        except Exception as e:
            logger.error(f"发送流式事件失败: {e}")
    
    def get_current_step_count(self) -> int:
        """获取当前步骤计数"""
        return self.step_counter
    
    def get_active_tools_count(self) -> int:
        """获取当前活跃工具数量"""
        return len(self.active_tools)