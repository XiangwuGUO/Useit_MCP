#!/usr/bin/env python3
"""
流式Agent实现
通过自定义执行循环实现实时工具事件流传输
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, AsyncGenerator
from uuid import uuid4

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from .stream_models import StreamEvent, ToolStartEvent, ToolResultEvent
from .debug_logger import debug_logger

logger = logging.getLogger(__name__)


class StreamingAgent:
    """流式Agent，支持实时工具事件传输"""
    
    def __init__(self, model, tools: List[BaseTool], system_prompt: str):
        # 绑定工具到模型！这是关键！
        self.model = model.bind_tools(tools)
        self.tools = {tool.name: tool for tool in tools}
        self.tools_list = tools  # 保留原始列表用于调试
        self.system_prompt = system_prompt
        
        # Token 使用跟踪
        self.total_token_usage = {"claude-sonnet-4-20250514": 0}
        self.step_token_usage = {}  # 每个步骤的token使用
        
        print(f"🤖 [AGENT] 流式Agent创建完成，包含 {len(tools)} 个工具")
        print(f"🤖 [AGENT] 工具名称列表: {list(self.tools.keys())}")
        print(f"🤖 [AGENT] 模型已绑定工具，支持工具调用")
    
    async def astream_invoke(
        self, 
        messages: List, 
        event_queue: asyncio.Queue,
        task_id: str,
        max_iterations: int = 10
    ) -> Dict[str, Any]:
        """流式执行Agent，实时发送工具事件"""
        
        print(f"🚀 [AGENT] 开始流式执行，最大迭代次数: {max_iterations}")
        
        # 准备消息历史
        conversation = [SystemMessage(content=self.system_prompt)] + messages
        step_counter = 0
        
        for iteration in range(max_iterations):
            print(f"🔄 [AGENT] 第 {iteration + 1} 轮对话")
            
            try:
                # 1. 调用模型生成响应
                response = await self.model.ainvoke(conversation)
                conversation.append(response)
                
                print(f"📝 [AGENT] 模型响应类型: {type(response).__name__}")
                
                # 2. 跟踪token使用（如果响应包含usage信息）
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    usage = response.usage_metadata
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    total_tokens = input_tokens + output_tokens
                    
                    # 记录当前步骤的token使用
                    self.step_token_usage[step_counter] = {
                        "model_name": "claude-sonnet-4-20250514",
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens
                    }
                    
                    # 累加到总计
                    self.total_token_usage["claude-sonnet-4-20250514"] += total_tokens
                    
                    print(f"🔢 [AGENT] Token使用: input={input_tokens}, output={output_tokens}, total={total_tokens}")
                elif hasattr(response, 'response_metadata') and response.response_metadata:
                    # 尝试从response_metadata获取usage信息
                    usage = response.response_metadata.get('usage', {})
                    if usage:
                        input_tokens = usage.get('input_tokens', 0)
                        output_tokens = usage.get('output_tokens', 0)
                        total_tokens = input_tokens + output_tokens
                        
                        self.step_token_usage[step_counter] = {
                            "model_name": "claude-sonnet-4-20250514", 
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens
                        }
                        
                        self.total_token_usage["claude-sonnet-4-20250514"] += total_tokens
                        
                        print(f"🔢 [AGENT] Token使用 (metadata): input={input_tokens}, output={output_tokens}, total={total_tokens}")
                else:
                    print(f"⚠️ [AGENT] 无法获取token使用信息")
                
                # 2. 检查是否有工具调用
                tool_calls = getattr(response, 'tool_calls', [])
                print(f"🔍 [AGENT] 响应对象类型: {type(response).__name__}")
                print(f"🔍 [AGENT] 响应对象属性: {dir(response)}")
                print(f"🔍 [AGENT] tool_calls 属性: {tool_calls}")
                print(f"🔍 [AGENT] tool_calls 类型: {type(tool_calls)}")
                
                if not tool_calls:
                    print(f"✅ [AGENT] 没有工具调用，对话结束")
                    # 尝试其他方式获取工具调用
                    if hasattr(response, 'additional_kwargs'):
                        print(f"🔍 [AGENT] additional_kwargs: {response.additional_kwargs}")
                    if hasattr(response, 'content'):
                        print(f"🔍 [AGENT] content: {response.content}")
                    break
                
                print(f"🔧 [AGENT] 发现 {len(tool_calls)} 个工具调用")
                print(f"🔍 [AGENT] 工具调用详情: {tool_calls}")
                
                # 3. 执行每个工具调用
                tool_messages = []
                for tool_call in tool_calls:
                    step_counter += 1
                    
                    # 限制总工具调用次数不超过10次
                    if step_counter > 10:
                        print(f"⚠️ [AGENT] 工具调用次数已达到上限(10次)，停止执行后续调用")
                        logger.warning(f"工具调用次数已达到上限(10次)，停止处理后续调用")
                        break
                    
                    # 发送工具开始事件
                    await self._send_tool_start_event(
                        event_queue, task_id, step_counter, tool_call
                    )
                    
                    # 执行工具
                    tool_result = await self._execute_tool(tool_call, step_counter)
                    
                    # 发送工具结果事件
                    await self._send_tool_result_event(
                        event_queue, task_id, step_counter, tool_call, tool_result
                    )
                    
                    # 创建工具消息
                    tool_message = ToolMessage(
                        content=str(tool_result.get('result', '')),
                        tool_call_id=tool_call['id']
                    )
                    tool_messages.append(tool_message)
                
                # 如果达到调用次数上限，结束迭代
                if step_counter > 10:
                    print(f"⚠️ [AGENT] 达到最大工具调用次数限制，任务执行结束")
                    break
                
                # 4. 添加工具响应到对话历史
                conversation.extend(tool_messages)
                
            except Exception as e:
                logger.error(f"Agent执行失败: {e}", exc_info=True)
                print(f"❌ [AGENT] 执行失败: {e}")
                break
        
        # 返回最终结果
        return {
            "messages": conversation,
            "iterations": iteration + 1,
            "total_steps": step_counter,
            "total_token_usage": self.total_token_usage.copy(),
            "step_token_usage": self.step_token_usage.copy()
        }
    
    async def _send_tool_start_event(
        self, 
        event_queue: asyncio.Queue, 
        task_id: str, 
        step_number: int, 
        tool_call: Dict
    ):
        """发送工具开始事件"""
        
        # LangChain工具调用格式可能不同，尝试多种解析方式
        print(f"🔍 [AGENT] 工具调用对象: {tool_call}")
        print(f"🔍 [AGENT] 工具调用类型: {type(tool_call)}")
        
        # 尝试不同的工具调用格式
        if hasattr(tool_call, 'name'):
            # 直接属性格式
            tool_name = tool_call.name
            arguments = getattr(tool_call, 'args', {})
            print(f"🔍 [AGENT] 方式1: 属性格式，工具名={tool_name}")
        elif isinstance(tool_call, dict):
            # 字典格式 - 检查多种可能的结构
            if 'function' in tool_call:
                function = tool_call.get('function', {})
                tool_name = function.get('name', 'unknown_tool')
                arguments_str = function.get('arguments', '{}')
                try:
                    arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    arguments = {"raw_arguments": arguments_str}
                print(f"🔍 [AGENT] 方式2: function格式，工具名={tool_name}")
            else:
                tool_name = tool_call.get('name', 'unknown_tool')
                arguments = tool_call.get('args', tool_call.get('arguments', {}))
                print(f"🔍 [AGENT] 方式3: 直接dict格式，工具名={tool_name}")
        else:
            tool_name = 'unknown_tool'
            arguments = {}
            print(f"🔍 [AGENT] 方式4: 未知格式，工具名={tool_name}")
        
        print(f"🔧 [AGENT] 步骤 {step_number}: 开始执行工具 {tool_name}")
        print(f"🔧 [AGENT] 工具参数: {arguments}")
        
        server_name = self._extract_server_name(tool_name)
        print(f"🔧 [AGENT] 解析的服务器名称: {server_name}")
        
        tool_start_event = ToolStartEvent(
            task_id=task_id,
            step_number=step_number,
            tool_name=tool_name,
            server_name=server_name,
            arguments=arguments,
            reasoning=f"执行工具 {tool_name} 来处理请求"
        )
        
        stream_event = StreamEvent(
            type="tool_start",
            data=tool_start_event.model_dump()
        )
        
        await event_queue.put(stream_event)
    
    async def _send_tool_result_event(
        self,
        event_queue: asyncio.Queue,
        task_id: str,
        step_number: int,
        tool_call: Dict,
        tool_result: Dict
    ):
        """发送工具结果事件"""
        
        # 使用与其他地方一致的解析逻辑
        if hasattr(tool_call, 'name'):
            tool_name = tool_call.name
        elif isinstance(tool_call, dict):
            if 'function' in tool_call:
                function = tool_call.get('function', {})
                tool_name = function.get('name', 'unknown_tool')
            else:
                tool_name = tool_call.get('name', 'unknown_tool')
        else:
            tool_name = 'unknown_tool'
        
        execution_time = tool_result.get('execution_time', 0)
        success = tool_result.get('success', True)
        result = tool_result.get('result', '')
        
        print(f"✅ [AGENT] 步骤 {step_number}: 工具 {tool_name} 执行完成 (耗时 {execution_time:.2f}秒)")
        
        server_name = self._extract_server_name(tool_name)
        
        # 获取当前步骤的token使用情况
        current_step_token = self.step_token_usage.get(step_number, {})
        token_usage_summary = {
            "total_tokens": current_step_token.get("total_tokens", 0)
        } if current_step_token else {"total_tokens": 0}
        
        tool_result_event = ToolResultEvent(
            task_id=task_id,
            step_number=step_number,
            tool_name=tool_name,
            server_name=server_name,
            result=result,
            status="success" if success else "error",
            execution_time=execution_time,
            token_usage=token_usage_summary
        )
        
        stream_event = StreamEvent(
            type="tool_result",
            data=tool_result_event.model_dump()
        )
        
        await event_queue.put(stream_event)
    
    async def _execute_tool(self, tool_call: Dict, step_number: int) -> Dict:
        """执行单个工具调用"""
        
        # 使用与_send_tool_start_event相同的解析逻辑
        if hasattr(tool_call, 'name'):
            tool_name = tool_call.name
            arguments = getattr(tool_call, 'args', {})
        elif isinstance(tool_call, dict):
            if 'function' in tool_call:
                function = tool_call.get('function', {})
                tool_name = function.get('name')
                arguments_str = function.get('arguments', '{}')
                try:
                    arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    arguments = {"raw_arguments": arguments_str}
            else:
                tool_name = tool_call.get('name')
                arguments = tool_call.get('args', tool_call.get('arguments', {}))
        else:
            tool_name = None
            arguments = {}
        
        print(f"🔧 [AGENT] 执行工具: {tool_name} 参数: {arguments}")
        print(f"🔧 [AGENT] 可用工具: {list(self.tools.keys())}")
        
        if not tool_name:
            print(f"❌ [AGENT] 工具名称为空!")
            return {
                'success': False,
                'result': '工具名称为空',
                'execution_time': 0
            }
        
        if tool_name not in self.tools:
            print(f"❌ [AGENT] 工具 {tool_name} 不在可用工具列表中!")
            return {
                'success': False,
                'result': f'工具 {tool_name} 不存在',
                'execution_time': 0
            }
        
        try:
            # 执行工具
            start_time = time.time()
            tool = self.tools[tool_name]
            
            print(f"🔧 [AGENT] 工具对象类型: {type(tool).__name__}")
            print(f"🔧 [AGENT] 工具对象方法: {[m for m in dir(tool) if not m.startswith('_')]}")
            
            # 记录工具输入（如果调试开启）
            if debug_logger.debug_enabled:
                await debug_logger.log_tool_execution(
                    tool_name=tool_name,
                    tool_input=arguments,
                    tool_output=None,  # 暂时为空，稍后更新
                    success=None  # 暂时为空，稍后更新
                )
            
            # 尝试不同的工具调用方法
            try:
                print(f"🔧 [AGENT] 尝试调用工具，参数: {arguments}")
                
                # 参数格式适配：
                # 默认传递平级参数；只有当工具 args_schema 明确包含 'req' 字段时，才包装为 {"req": ...}
                fixed_arguments = arguments
                needs_req_wrapper = False
                try:
                    schema = getattr(tool, 'args_schema', None)
                    if schema is not None and hasattr(schema, 'model_fields'):
                        needs_req_wrapper = 'req' in getattr(schema, 'model_fields', {})
                except Exception:
                    needs_req_wrapper = False

                if isinstance(arguments, dict):
                    if needs_req_wrapper:
                        if 'req' not in arguments:
                            fixed_arguments = {"req": arguments}
                            print(f"🔧 [AGENT] 为工具 {tool_name} 包装 req 参数: {arguments} -> {fixed_arguments}")
                        else:
                            print(f"🔧 [AGENT] 已包含 req，直接使用: {arguments}")
                    else:
                        # 工具不需要 req 包装，保持平级
                        fixed_arguments = arguments
                        if 'req' in arguments:
                            print(f"⚠️ [AGENT] 检测到多余的 req，工具 {tool_name} 使用平级参数，建议移除 req")
                    # 空参数允许（如 get_base 等），不做强制填充
                else:
                    print(f"🔧 [AGENT] 非字典参数，原样传递: {arguments}")
                
                # 尝试直接调用工具（推荐方式）
                if hasattr(tool, 'invoke'):
                    print(f"🔧 [AGENT] 使用 invoke 方法")
                    result = await tool.ainvoke(fixed_arguments) if asyncio.iscoroutinefunction(tool.ainvoke) else tool.invoke(fixed_arguments)
                elif hasattr(tool, '_run'):
                    print(f"🔧 [AGENT] 使用 _run 方法")
                    # 尝试_run方法，带config参数
                    if asyncio.iscoroutinefunction(tool._run):
                        result = await tool._run(config={}, **fixed_arguments)
                    else:
                        result = tool._run(config={}, **fixed_arguments)
                else:
                    print(f"🔧 [AGENT] 使用直接调用")
                    # 最后的备选方案
                    result = await tool(fixed_arguments) if asyncio.iscoroutinefunction(tool) else tool(fixed_arguments)
                    
                print(f"🔧 [AGENT] 工具调用成功，结果类型: {type(result)}")
                print(f"🔧 [AGENT] 工具调用结果: {str(result)[:200]}...")
                
            except TypeError as te:
                print(f"🔧 [AGENT] TypeError: {te}")
                # 如果config参数不需要，尝试不带config
                if "config" in str(te):
                    print(f"🔧 [AGENT] 重试不带config参数")
                    if asyncio.iscoroutinefunction(tool._run):
                        result = await tool._run(**arguments)
                    else:
                        result = tool._run(**arguments)
                else:
                    raise te
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 记录工具执行成功结果（如果调试开启）
            if debug_logger.debug_enabled:
                await debug_logger.log_tool_execution(
                    tool_name=tool_name,
                    tool_input=arguments,
                    tool_output=result,
                    success=True
                )
            
            return {
                'success': True,
                'result': result,
                'execution_time': execution_time
            }
            
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {e}")
            print(f"❌ [AGENT] 工具 {tool_name} 执行失败: {e}")
            
            # 记录工具执行失败结果（如果调试开启）
            if debug_logger.debug_enabled:
                await debug_logger.log_tool_execution(
                    tool_name=tool_name,
                    tool_input=arguments,
                    tool_output=None,
                    success=False,
                    error=str(e)
                )
            
            return {
                'success': False,
                'result': str(e),
                'execution_time': time.time() - start_time if 'start_time' in locals() else 0
            }
    
    def _extract_server_name(self, tool_name: str) -> str:
        """从工具名称中提取服务器名称"""
        # MCP工具名称格式通常为: server_name__tool_name
        if "__" in tool_name:
            return tool_name.split("__")[0]
        
        # 如果没有__分隔符，检查常见的MCP服务器工具
        common_filesystem_tools = ['list_dir', 'read_file', 'write_file', 'stat', 'get_base', 'list_all_paths']
        common_audio_tools = ['slice_audio', 'get_audio_info']
        
        if tool_name in common_filesystem_tools:
            return "filesystem"
        elif tool_name in common_audio_tools:
            return "audio_slicer"
        
        return "unknown"
    
    def get_total_token_usage(self) -> Dict[str, int]:
        """获取总token使用情况"""
        return self.total_token_usage.copy()
    
    def get_step_token_usage(self, step_number: int) -> Optional[Dict[str, Any]]:
        """获取指定步骤的token使用情况"""
        return self.step_token_usage.get(step_number)