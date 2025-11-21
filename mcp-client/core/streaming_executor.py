#!/usr/bin/env python3
"""
流式LangChain执行器
支持SSE实时事件推送的任务执行器
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from uuid import uuid4

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManager

from .api_models import TaskResult, TaskRequest
from .client_manager import ClientManager
from .stream_models import *
from .langchain_executor import LangChainMCPExecutor
from .streaming_callbacks import StreamingToolCallbackHandler
from .message_parser import AgentMessageParser
from .streaming_agent import StreamingAgent
from .debug_logger import debug_logger
from .file_processor import FileProcessor  # 新增：文件处理器
from .metadata_injector import MetadataInjector  # 新增：Metadata注入器

logger = logging.getLogger(__name__)


# StreamingToolWrapper 已被 StreamingToolCallbackHandler 替代


class StreamingLangChainExecutor(LangChainMCPExecutor):
    """流式LangChain执行器"""
    
    def __init__(self, client_manager: ClientManager, anthropic_api_key: Optional[str] = None, debug_enabled: bool = False):
        super().__init__(client_manager, anthropic_api_key)
        self.active_tasks: Dict[str, StreamTaskStatus] = {}
        self.debug_enabled = debug_enabled
        
        # 配置调试记录器
        if debug_enabled:
            debug_logger.enable_debug()
        else:
            debug_logger.disable_debug()
    
    async def execute_task_streaming(self, task_request: TaskRequest) -> AsyncGenerator[StreamEvent, None]:
        """
        流式执行任务，生成SSE事件
        
        Args:
            task_request: 任务请求对象
            
        Yields:
            StreamEvent: 任务执行过程中的各种事件
        """
        
        print(f"🚨🚨🚨 [EXECUTOR] execute_task_streaming 被调用！")
        print(f"🚨🚨🚨 [EXECUTOR] 任务描述: {task_request.task_description}")
        
        # 生成任务ID
        task_id = f"task_{uuid4().hex[:8]}"
        
        # 创建事件队列
        event_queue = asyncio.Queue()
        
        # 创建任务状态
        task_status = StreamTaskStatus(
            task_id=task_id,
            vm_id=task_request.vm_id,
            session_id=task_request.session_id,
            mcp_server_name=task_request.mcp_server_name,
            task_description=task_request.task_description,
            status="pending",
            start_time=datetime.now()
        )
        
        self.active_tasks[task_id] = task_status
        
        try:
            # 发送任务开始事件
            await self._send_task_start_event(event_queue, task_request, task_id)
            
            # 异步执行任务
            task = asyncio.create_task(
                self._execute_task_with_events(task_request, task_id, event_queue)
            )
            
            # 流式生成事件
            async for event in self._stream_events(event_queue, task):
                yield event
                
        except Exception as e:
            logger.error(f"流式任务执行失败: {e}")
            
            # 发送错误事件
            error_event = TaskErrorEvent(
                task_id=task_id,
                error_message=str(e),
                error_type=type(e).__name__
            )
            
            yield StreamEvent(type="error", data=error_event.model_dump())
        
        finally:
            # 清理任务状态
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    async def _execute_task_with_events(self, task_request: TaskRequest, task_id: str, event_queue: asyncio.Queue):
        """执行任务并发送事件"""

        try:
            logger.info(f"开始执行流式任务 {task_id}")

            # 更新任务状态
            self.active_tasks[task_id].status = "running"

            # 0. 处理文件输入和构建metadata（新增）
            auto_inject_metadata = await self._process_files_and_metadata(
                task_request,
                task_id,
                event_queue
            )

            # 1. 获取或创建流式Agent（传递metadata）
            logger.info(f"创建流式Agent for {task_request.vm_id}/{task_request.session_id}")
            print(f"🎯🎯🎯 [DEBUG] 使用新的流式Agent代码！任务ID: {task_id}")
            print(f"🎯🎯🎯 [DEBUG] 即将调用 _get_streaming_agent_v2")

            streaming_agent = await self._get_streaming_agent_v2(
                task_request.vm_id,
                task_request.session_id,
                task_request.mcp_server_name,
                auto_inject_metadata=auto_inject_metadata  # 传递metadata
            )
            
            # 2. 构建任务消息
            messages = self._build_task_messages(task_request)
            logger.info(f"构建了 {len(messages)} 个消息")
            
            # 记录AI输入（如果开启调试）
            if self.debug_enabled:
                tools = streaming_agent.tools_list if hasattr(streaming_agent, 'tools_list') else []
                await debug_logger.log_ai_input(
                    messages=messages,
                    tools=tools,
                    metadata={
                        "task_id": task_id,
                        "vm_id": task_request.vm_id,
                        "session_id": task_request.session_id,
                        "task_description": task_request.task_description
                    }
                )
            
            # 3. 执行任务（流式，实时发送工具事件）
            start_time = asyncio.get_event_loop().time()
            logger.info(f"开始执行流式Agent任务")
            
            result = await streaming_agent.astream_invoke(
                messages=messages,
                event_queue=event_queue,
                task_id=task_id,
                max_iterations=10
            )
            end_time = asyncio.get_event_loop().time()
            
            logger.info(f"流式Agent任务执行完成，耗时 {end_time - start_time:.2f}秒")
            logger.info(f"总共执行了 {result.get('total_steps', 0)} 个工具步骤")
            
            # 记录AI输出（如果开启调试）
            if self.debug_enabled:
                await debug_logger.log_ai_output(
                    response=result,
                    tool_calls=result.get('tool_calls', []),
                    metadata={
                        "task_id": task_id,
                        "execution_time": end_time - start_time,
                        "total_steps": result.get('total_steps', 0),
                        "success": result.get('success', False)
                    }
                )
                
                # 记录任务执行完成后的最终conversation状态
                final_messages = result.get('messages', [])
                if final_messages:
                    await debug_logger.log_conversation_state(
                        final_messages,
                        9999,  # 使用9999作为最终conversation的step_number
                        metadata={
                            "type": "task_complete",
                            "task_id": task_id,
                            "execution_time": end_time - start_time,
                            "total_steps": result.get('total_steps', 0),
                            "total_iterations": result.get('iterations', 0),
                            "final_conversation_length": len(final_messages)
                        }
                    )
            
            # 4. 处理结果并发送完成事件
            task_result = await self._process_streaming_result(
                result, 
                task_request, 
                task_id,
                end_time - start_time
            )
            
            logger.info(f"处理任务结果完成，成功: {task_result.success}")
            
            # 获取总token使用量
            total_token_usage = result.get('total_token_usage', {})
            if total_token_usage:
                logger.info(f"总token使用量: {total_token_usage}")
            
            # 发送任务完成事件
            await self._send_task_complete_event(event_queue, task_result, task_id, total_token_usage)
            
            logger.info(f"任务完成事件已发送")
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}", exc_info=True)
            
            # 发送错误事件
            error_event = TaskErrorEvent(
                task_id=task_id,
                error_message=str(e),
                error_type=type(e).__name__
            )
            
            await event_queue.put(StreamEvent(type="error", data=error_event.model_dump()))
            logger.info(f"错误事件已发送")
    
    async def _get_streaming_agent(self, vm_id: str, session_id: str, task_id: str, event_queue: asyncio.Queue):
        """获取带流式事件的Agent（使用回调机制）"""
        
        # 1. 构建MCP服务器配置
        mcp_config = await self._build_mcp_config(vm_id, session_id)
        
        # 2. 创建MCP客户端
        mcp_client = MultiServerMCPClient(mcp_config)
        
        # 3. 获取原始工具
        tools = await mcp_client.get_tools()
        
        # 4. 创建流式回调处理器
        callback_handler = StreamingToolCallbackHandler(event_queue, task_id)
        
        # 5. 创建回调管理器
        callback_manager = CallbackManager([callback_handler])
        
        # 6. 创建带回调的模型
        model = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=self.anthropic_api_key,
            temperature=0,
            callbacks=[callback_handler]  # 添加回调处理器
        )
        
        # 7. 创建系统提示
        system_prompt = self._build_system_prompt(tools)
        
        # 8. 创建Agent，配置回调
        agent = create_react_agent(
            model=model,
            tools=tools,
            prompt=system_prompt
        )
        
        # 9. 配置Agent参数和回调
        agent = agent.with_config({
            "recursion_limit": 10,
            "max_execution_time": 120,
            "callbacks": [callback_handler],  # Agent级别的回调
            "configurable": {
                "thread_id": f"stream_thread_{task_id}",
            }
        })
        
        logger.info(f"为任务 {task_id} 创建了流式Agent，包含 {len(tools)} 个工具和回调处理器")
        
        return agent, callback_handler
    
    async def _get_simple_agent(self, vm_id: str, session_id: str):
        """获取简单的Agent（不使用回调机制）"""
        
        # 1. 构建MCP服务器配置
        mcp_config = await self._build_mcp_config(vm_id, session_id)
        
        # 2. 创建MCP客户端
        mcp_client = MultiServerMCPClient(mcp_config)
        
        # 3. 获取工具
        tools = await mcp_client.get_tools()
        
        # 4. 创建模型
        model = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=self.anthropic_api_key,
            temperature=0
        )
        
        # 5. 创建系统提示
        system_prompt = self._build_system_prompt(tools)
        
        # 6. 创建Agent
        agent = create_react_agent(
            model=model,
            tools=tools,
            prompt=system_prompt
        )
        
        logger.info(f"创建了简单Agent，包含 {len(tools)} 个工具")
        
        return agent
    
    async def _get_streaming_agent_v2(
        self,
        vm_id: str,
        session_id: str,
        mcp_server_name: Optional[str] = None,
        auto_inject_metadata: Optional[Dict[str, Any]] = None  # 新增参数
    ) -> StreamingAgent:
        """获取流式Agent（v2版本，使用自定义流式执行，支持metadata注入）"""

        # 1. 构建MCP服务器配置（可选过滤特定服务器）
        mcp_config = await self._build_mcp_config(vm_id, session_id, mcp_server_name)

        if mcp_server_name:
            print(f"🎯 [DEBUG] 过滤到指定MCP服务器: {mcp_server_name}")
            print(f"🎯 [DEBUG] MCP配置包含服务器: {list(mcp_config.keys())}")
        else:
            print(f"🎯 [DEBUG] 使用所有可用MCP服务器: {list(mcp_config.keys())}")

        # 2. 创建MCP客户端
        mcp_client = MultiServerMCPClient(mcp_config)

        # 3. 获取工具并包装以处理参数格式
        raw_tools = await mcp_client.get_tools()

        # Debug: 检查原始工具信息
        print(f"🔍 [DEBUG] 原始工具数量: {len(raw_tools)}")
        for i, tool in enumerate(raw_tools[:3]):  # 只显示前3个
            print(f"🔍 [DEBUG] 原始工具 {i}: name={getattr(tool, 'name', 'NO_NAME')}, desc={getattr(tool, 'description', 'NO_DESC')[:50]}")

        tools = self._wrap_mcp_tools_for_langchain(raw_tools)

        # Debug: 检查包装后工具信息
        print(f"🔍 [DEBUG] 包装后工具数量: {len(tools)}")
        for i, tool in enumerate(tools[:3]):  # 只显示前3个
            print(f"🔍 [DEBUG] 包装后工具 {i}: name={getattr(tool, 'name', 'NO_NAME')}, desc={getattr(tool, 'description', 'NO_DESC')[:50]}")

        # 3.5 注入metadata到工具（新增）
        if auto_inject_metadata:
            logger.info(f"为工具注入metadata: {list(auto_inject_metadata.keys())}")
            tools = MetadataInjector.wrap_tools_with_metadata(tools, auto_inject_metadata)
            print(f"🔧 [DEBUG] 已注入metadata到所有工具")
        
        # 4. 创建模型
        model = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=self.anthropic_api_key,
            temperature=0
        )
        
        # 5. 创建系统提示
        system_prompt_obj = self._build_system_prompt(tools)
        system_prompt_text = system_prompt_obj.content
        
        # 6. 创建流式Agent
        streaming_agent = StreamingAgent(
            model=model,
            tools=tools,
            system_prompt=system_prompt_text
        )
        
        logger.info(f"创建了流式Agent，包含 {len(tools)} 个工具")
        
        return streaming_agent
    
    async def _stream_events(self, event_queue: asyncio.Queue, task: asyncio.Task) -> AsyncGenerator[StreamEvent, None]:
        """流式生成事件"""
        
        while not task.done():
            try:
                # 等待事件，超时时间短以保持响应性
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                # 超时继续循环
                continue
        
        # 等待任务完成
        try:
            await task
        except Exception as e:
            logger.error(f"任务执行异常: {e}")
        
        # 任务完成后，处理队列中剩余的事件
        remaining_events = 0
        while not event_queue.empty():
            try:
                event = event_queue.get_nowait()
                yield event
                remaining_events += 1
            except asyncio.QueueEmpty:
                break
        
        # 短暂等待确保所有事件都被处理
        await asyncio.sleep(0.1)
        
        # 再次检查是否有新事件
        while not event_queue.empty():
            try:
                event = event_queue.get_nowait()
                yield event
                remaining_events += 1
            except asyncio.QueueEmpty:
                break
        
        logger.info(f"流式事件处理完成，处理了 {remaining_events} 个剩余事件")
    
    async def _send_task_start_event(self, event_queue: asyncio.Queue, task_request: TaskRequest, task_id: str):
        """发送任务开始事件"""
        event_data = TaskStartEvent(
            task_id=task_id,
            vm_id=task_request.vm_id,
            session_id=task_request.session_id,
            mcp_server_name=task_request.mcp_server_name,
            task_description=task_request.task_description,
            context=getattr(task_request, 'context', None)
        )
        
        stream_event = StreamEvent(
            type="start",
            data=event_data.model_dump()
        )
        
        await event_queue.put(stream_event)
    
    async def _send_task_complete_event(self, event_queue: asyncio.Queue, task_result: TaskResult, task_id: str, total_token_usage: Optional[Dict[str, int]] = None):
        """发送任务完成事件"""
        event_data = TaskCompleteEvent(
            task_id=task_id,
            success=task_result.success,
            final_result=task_result.final_result,
            summary=task_result.summary,
            execution_time=task_result.execution_time_seconds,
            total_steps=len(task_result.execution_steps),
            successful_steps=sum(1 for step in task_result.execution_steps if step.get("status") == "success"),
            new_files=task_result.new_files,
            total_token_usage=total_token_usage
        )
        
        stream_event = StreamEvent(
            type="complete",
            data=event_data.model_dump()
        )
        
        await event_queue.put(stream_event)
    
    async def _process_streaming_result(self, result: Dict, task_request: TaskRequest, 
                                      task_id: str, execution_time: float) -> TaskResult:
        """处理流式结果，复用父类逻辑"""
        
        # 复用父类的结果处理逻辑
        task_result = await self._process_result(result, task_request, execution_time)
        
        # 更新任务ID
        task_result.task_id = task_id
        
        return task_result
    
    def _extract_final_result(self, message) -> str:
        """从消息中提取最终结果，处理不同的内容格式"""
        
        if not message or not hasattr(message, 'content'):
            return "任务完成"
        
        content = message.content
        
        # 如果content是字符串，直接返回
        if isinstance(content, str):
            return content
        
        # 如果content是列表，提取文本内容
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    # 处理 {'text': '...', 'type': '...'} 格式
                    if 'text' in item:
                        text_parts.append(item['text'])
                    elif 'content' in item:
                        text_parts.append(str(item['content']))
                elif isinstance(item, str):
                    text_parts.append(item)
                else:
                    text_parts.append(str(item))
            
            if text_parts:
                return ' '.join(text_parts)
        
        # 如果content是字典，尝试提取文本
        if isinstance(content, dict):
            if 'text' in content:
                return content['text']
            elif 'content' in content:
                return str(content['content'])
        
        # 最后兜底，转换为字符串
        try:
            return str(content)
        except Exception:
            return "任务完成"
    
    def get_active_tasks(self) -> Dict[str, StreamTaskStatus]:
        """获取活跃任务状态"""
        return self.active_tasks.copy()
    
    def _wrap_mcp_tools_for_langchain(self, raw_tools: List[BaseTool]) -> List[BaseTool]:
        """包装MCP工具以处理LangChain和MCP之间的参数格式差异"""
        from langchain_core.tools import StructuredTool
        from typing import Type
        from pydantic import BaseModel, Field
        
        wrapped_tools = []
        
        for tool in raw_tools:
            # 如果工具已经是正确格式，直接使用
            if not self._tool_needs_wrapping(tool):
                wrapped_tools.append(tool)
                continue
            
            # 为需要参数包装的工具创建包装版本
            try:
                # 获取原始工具的schema
                original_schema = tool.args_schema
                if not original_schema:
                    wrapped_tools.append(tool)
                    continue
                
                # 检查是否有嵌套的"req"结构
                if hasattr(original_schema, 'model_fields') and 'req' in original_schema.model_fields:
                    # 创建扁平化的参数模型
                    req_field = original_schema.model_fields['req']
                    if hasattr(req_field, 'annotation') and hasattr(req_field.annotation, 'model_fields'):
                        inner_fields = req_field.annotation.model_fields
                        
                        # 创建新的扁平化模型
                        flat_fields = {}
                        for field_name, field_info in inner_fields.items():
                            flat_fields[field_name] = (field_info.annotation, field_info)
                        
                        # 动态创建Pydantic模型
                        FlatArgsModel = type(
                            f"{tool.name}FlatArgs",
                            (BaseModel,),
                            {'__annotations__': {k: v[0] for k, v in flat_fields.items()}}
                        )
                        
                        # 为每个字段设置默认值
                        for field_name, (field_type, field_info) in flat_fields.items():
                            if hasattr(field_info, 'default'):
                                setattr(FlatArgsModel, field_name, field_info.default)
                        
                        # 创建包装函数
                        async def wrapped_func(**kwargs):
                            # 直接传递平级参数（MCP Server 端现在期望平级参数）
                            if hasattr(tool, 'ainvoke'):
                                return await tool.ainvoke(kwargs)
                            else:
                                return tool.invoke(kwargs)
                        
                        # 创建新的StructuredTool
                        wrapped_tool = StructuredTool(
                            name=tool.name,
                            description=tool.description,
                            func=wrapped_func,
                            args_schema=FlatArgsModel,
                            coroutine=True
                        )
                        
                        print(f"🔧 [WRAPPER] 包装了工具: {tool.name}")
                        wrapped_tools.append(wrapped_tool)
                    else:
                        wrapped_tools.append(tool)
                else:
                    wrapped_tools.append(tool)
                    
            except Exception as e:
                print(f"❌ [WRAPPER] 包装工具 {tool.name} 时出错: {e}")
                # 出错时使用原始工具
                wrapped_tools.append(tool)
        
        print(f"🔧 [WRAPPER] 总共包装了 {len(wrapped_tools)} 个工具")
        return wrapped_tools
    
    def _tool_needs_wrapping(self, tool: BaseTool) -> bool:
        """检查工具是否需要参数包装"""
        # 现在 MCP Server 端工具使用平级参数，大多数情况下不需要包装
        # 只有当工具schema明确包含嵌套req结构时才需要包装
        if not hasattr(tool, 'args_schema') or not tool.args_schema:
            return False

        # 检查是否有嵌套的req结构
        if hasattr(tool.args_schema, 'model_fields') and 'req' in tool.args_schema.model_fields:
            return True

        return False

    async def _process_files_and_metadata(
        self,
        task_request: TaskRequest,
        task_id: str,
        event_queue: asyncio.Queue
    ) -> Optional[Dict[str, Any]]:
        """
        处理文件输入和构建metadata

        Args:
            task_request: 任务请求
            task_id: 任务ID
            event_queue: 事件队列

        Returns:
            构建的metadata对象，如果没有则返回None
        """
        metadata_obj = {}

        # 1. 处理文件输入
        if task_request.files_input:
            try:
                logger.info("处理文件输入...")

                # 发送文件处理开始事件
                await event_queue.put(StreamEvent(
                    type="file_processing_start",
                    data={
                        "task_id": task_id,
                        "files_directory": task_request.files_input.files_directory
                    }
                ))

                # 处理文件
                files_data = await FileProcessor.process_files_input(
                    files_config=task_request.files_input,
                    task_description=task_request.task_description if task_request.files_input.auto_select else None,
                    anthropic_api_key=self.anthropic_api_key
                )

                metadata_obj["files"] = files_data

                logger.info(f"处理了 {len(files_data)} 个文件")

                # 发送文件处理完成事件
                await event_queue.put(StreamEvent(
                    type="file_processing_complete",
                    data={
                        "task_id": task_id,
                        "files_count": len(files_data)
                    }
                ))

            except Exception as e:
                logger.error(f"文件处理失败: {e}")

                # 发送错误事件
                await event_queue.put(StreamEvent(
                    type="error",
                    data={
                        "task_id": task_id,
                        "error_message": f"文件处理失败: {str(e)}"
                    }
                ))

                # 继续执行，但不包含文件数据

        # 2. 合并用户提供的metadata
        if task_request.metadata:
            metadata_obj.update(task_request.metadata)
            logger.info(f"合并用户metadata: {list(task_request.metadata.keys())}")

        # 3. 返回metadata（如果有）
        if metadata_obj:
            logger.info(f"最终metadata keys: {list(metadata_obj.keys())}")
            return metadata_obj
        else:
            logger.info("没有metadata需要注入")
            return None