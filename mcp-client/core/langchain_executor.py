#!/usr/bin/env python3
"""
LangChain-integrated MCP Task Executor

Uses LangChain Agent for intelligent tool selection and task execution,
replacing previous complex AI logic with better tool usage and reasoning capabilities.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic

from .api_models import TaskResult, TaskRequest
from .client_manager import ClientManager

logger = logging.getLogger(__name__)


class LangChainMCPExecutor:
    """
    LangChain-based MCP Task Executor
    
    Features:
    1. Automatically connect to registered MCP servers
    2. Use LangChain Agent for intelligent tool selection
    3. Support multi-step task execution and reasoning
    4. Provide file generation tracking
    """
    
    def __init__(self, client_manager: ClientManager, anthropic_api_key: Optional[str] = None):
        self.client_manager = client_manager
        self.anthropic_api_key = anthropic_api_key
        self.agents = {}  # Cache agents for each client
        
    async def execute_task(self, task_request: TaskRequest) -> TaskResult:
        """
        执行智能任务
        
        Args:
            task_request: 任务请求对象
            
        Returns:
            TaskResult: 任务执行结果
        """
        try:
            # 1. 获取或创建Agent（按 vm/session/server 粒度缓存）
            agent = await self._get_agent(task_request.vm_id, task_request.session_id, task_request.mcp_server_name)
            
            # 2. 构建任务消息
            messages = self._build_task_messages(task_request)
            
            # 3. 执行任务
            start_time = asyncio.get_event_loop().time()
            result = await agent.ainvoke(
                {"messages": messages},
                config={
                    "recursion_limit": 10,
                    "configurable": {
                        "thread_id": f"task_{task_request.vm_id}_{task_request.session_id}_{int(start_time)}"
                    }
                }
            )
            end_time = asyncio.get_event_loop().time()
            
            # 4. 处理结果
            return await self._process_result(
                result, 
                task_request, 
                execution_time=end_time - start_time
            )
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return TaskResult(
                success=False,
                task_id=f"task_{task_request.vm_id}_{task_request.session_id}_{int(asyncio.get_event_loop().time())}",
                vm_id=task_request.vm_id,
                session_id=task_request.session_id,
                mcp_server_name=task_request.mcp_server_name,
                original_task=task_request.task_description,
                error_message=str(e),
                execution_steps=[],
                final_result=f"任务执行失败: {e}",
                summary=f"任务执行过程中发生错误: {e}",
                execution_time_seconds=0.0
            )
    
    async def _get_agent(self, vm_id: str, session_id: str, mcp_server_name: Optional[str] = None):
        """获取或创建指定客户端(可选指定MCP服务器)的LangChain Agent"""
        
        server_key = mcp_server_name or "__ALL__"
        agent_key = f"{vm_id}_{session_id}_{server_key}"
        
        if agent_key not in self.agents:
            # 1. 构建MCP服务器配置（若指定 server，仅加载该服务器工具）
            mcp_config = await self._build_mcp_config(vm_id, session_id, mcp_server_name)
            
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
            
            # 6. 创建Agent - 配置递归限制和其他参数
            agent = create_react_agent(
                model=model,
                tools=tools,
                prompt=system_prompt
            )
            
            # 7. 配置Agent的执行参数
            agent = agent.with_config({
                "recursion_limit": 10,  # 设置递归限制为10
                "max_execution_time": 60,  # 最大执行时间60秒
                "configurable": {
                    "thread_id": f"thread_{agent_key}",
                }
            })
            
            self.agents[agent_key] = {
                "agent": agent,
                "mcp_client": mcp_client,
                "tools": tools
            }
            
            logger.info(f"为客户端 {agent_key} 创建了Agent，包含 {len(tools)} 个工具")
        
        return self.agents[agent_key]["agent"]
    
    async def _build_mcp_config(self, vm_id: str, session_id: str, mcp_server_name: Optional[str] = None) -> Dict:
        """构建MCP服务器配置（可选过滤到指定的 MCP 服务器）"""
        
        client = await self.client_manager.get_client(vm_id, session_id)
        if not client:
            raise ValueError(f"客户端 {vm_id}/{session_id} 未找到")
        
        mcp_config = {}
        
        # 可选：仅选择指定的服务器
        target_names: List[str]
        if mcp_server_name:
            target_names = [mcp_server_name]
        else:
            target_names = list(client.servers.keys())

        for server_name in target_names:
            server = client.servers.get(server_name)
            if server and server.connected:
                mcp_url = server.remote_url
                if not mcp_url.endswith("/mcp"):
                    mcp_url = f"{mcp_url}/mcp"
                mcp_config[server_name] = {
                    "transport": "streamable_http",
                    "url": mcp_url,
                }
        
        if not mcp_config:
            if mcp_server_name:
                raise ValueError(f"Client {vm_id}/{session_id} has no available MCP server '{mcp_server_name}'")
            raise ValueError(f"Client {vm_id}/{session_id} has no available MCP servers")
        
        return mcp_config
    
    def _build_system_prompt(self, tools: List) -> SystemMessage:
        """Build system prompt (English)"""
        
        tool_descriptions = []
        for tool in tools:
            # Enhanced tool description with parameter hints
            description = f"- {tool.name}: {tool.description}"
            
            # Add parameter information if available
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    schema = tool.args_schema
                    if hasattr(schema, 'model_fields'):
                        fields = schema.model_fields
                        required_fields = []
                        for field_name, field_info in fields.items():
                            if hasattr(field_info, 'is_required') and field_info.is_required():
                                required_fields.append(field_name)
                            elif hasattr(field_info, 'default') and field_info.default is ...:  # Ellipsis means required
                                required_fields.append(field_name)
                        
                        if required_fields:
                            description += f" (Required: {', '.join(required_fields)})"
                except Exception:
                    pass  # Skip if schema parsing fails
            
            tool_descriptions.append(description)
        
        prompt_text = f"""You are an intelligent assistant that can use MCP tools exposed by connected servers.
Follow these principles and use tools directly to complete the user's request.

Available tools:
{chr(10).join(tool_descriptions)}

Execution principles:
- Call the most appropriate tool directly for each step
- IMPORTANT: Always provide ALL required parameters for each tool call
- For file operations: use filesystem tools (read, write, list, mkdir, copy, move, delete)
- For audio processing: use audio tools provided by the server
- Prefer tool results over assumptions; read/verify before writing
- Provide clear, concise results; include paths and summaries when creating files
- Think step-by-step; use multiple tools if needed to achieve the goal
- If a tool call fails due to missing parameters, review the tool requirements and retry with complete parameters

Now complete the user's task using the available tools."""
        
        return SystemMessage(content=prompt_text)
    
    def _build_task_messages(self, task_request: TaskRequest) -> List:
        """Build task messages (English)"""
        
        messages = []
        
        # Optional task-specific system context
        if task_request.context:
            messages.append(SystemMessage(content=f"Task context: {task_request.context}"))
        
        # User task message
        task_message = f"""Please complete the following task:

{task_request.task_description}

Use the available tools to accomplish the task and provide clear results (paths, summaries, and any produced artifacts)."""

        messages.append(HumanMessage(content=task_message))
        
        return messages
    
    async def _process_result(self, result: Dict, task_request: TaskRequest, execution_time: float) -> TaskResult:
        """处理LangChain Agent的执行结果"""
        
        # 提取消息
        messages = result.get("messages", [])
        
        # 构建执行步骤
        execution_steps = []
        tool_calls_count = 0
        
        for i, message in enumerate(messages):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_calls_count += 1
                    
                    # 限制总工具调用次数不超过10次（包括失败的）
                    if tool_calls_count > 10:
                        logger.warning(f"工具调用次数已达到上限(10次)，停止处理后续调用")
                        break
                    
                    # 查找对应的工具响应
                    tool_response = ""
                    tool_status = "success"  # 默认成功
                    
                    if i + 1 < len(messages):
                        next_message = messages[i + 1]
                        if hasattr(next_message, 'content'):
                            tool_response = next_message.content
                            
                            # 检测工具调用是否失败
                            # LangChain的ToolMessage在工具调用失败时会包含错误信息
                            if hasattr(next_message, 'type') and next_message.type == 'tool':
                                # 检查是否包含常见的错误关键词
                                response_str = str(tool_response).lower()
                                if any(error_keyword in response_str for error_keyword in [
                                    'error:', 'exception:', 'failed', 'field required', 
                                    'validation error', 'missing', 'invalid', 'traceback'
                                ]):
                                    tool_status = "error"
                    
                    # 只有成功的工具调用才添加到执行步骤中
                    if tool_status == "success":
                        execution_steps.append({
                            "step": len(execution_steps) + 1,  # 重新编号，只统计成功的步骤
                            "tool_name": tool_call["name"],
                            "arguments": tool_call["args"],
                            "result": tool_response,
                            "status": "success"
                        })
                
                # 如果达到调用次数上限，跳出外层循环
                if tool_calls_count > 10:
                    break
        
        # 获取最终回复
        final_message = messages[-1] if messages else None
        final_result = self._extract_final_result(final_message) if final_message else "任务完成"
        
        # Extract new files from server responses
        new_files = await self._extract_new_files_from_responses(execution_steps)
        
        # Generate summary
        summary = self._generate_summary(execution_steps, final_result)
        
        return TaskResult(
            success=True,
            task_id=f"task_{task_request.vm_id}_{task_request.session_id}_{int(asyncio.get_event_loop().time())}",
            vm_id=task_request.vm_id,
            session_id=task_request.session_id,
            mcp_server_name=task_request.mcp_server_name,
            original_task=task_request.task_description,
            execution_steps=execution_steps,
            final_result=final_result,
            summary=summary,
            execution_time_seconds=execution_time,
            new_files=new_files
        )
    
    async def _extract_new_files_from_responses(self, execution_steps: List[Dict]) -> Dict[str, str]:
        """Extract new files from MCP server responses"""
        
        new_files = {}
        
        for step in execution_steps:
            result = step.get("result", "")
            
            # Try to parse result as JSON to extract new_files from server responses
            try:
                import json
                if isinstance(result, str) and (result.startswith('{') or result.startswith('[')):
                    result_data = json.loads(result)
                    if isinstance(result_data, dict) and "new_files" in result_data:
                        server_new_files = result_data["new_files"]
                        if isinstance(server_new_files, dict):
                            new_files.update(server_new_files)
                elif isinstance(result, dict) and "new_files" in result:
                    server_new_files = result["new_files"]
                    if isinstance(server_new_files, dict):
                        new_files.update(server_new_files)
            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, continue with other detection methods
                pass
            
            # Fallback: detect from tool names and arguments (for servers that don't return new_files)
            tool_name = step.get("tool_name", "")
            arguments = step.get("arguments", {})
            
            if any(keyword in tool_name.lower() for keyword in ["write", "create", "save", "slice"]):
                if "path" in arguments:
                    file_path = arguments["path"]
                    # Convert to relative path
                    if file_path.startswith("/"):
                        file_path = Path(file_path).name
                    
                    # Determine file type based on extension
                    if file_path.endswith(".txt"):
                        file_type = "Text file"
                    elif file_path.endswith(".json"):
                        file_type = "JSON configuration file"
                    elif file_path.endswith(".md"):
                        file_type = "Markdown document"
                    elif file_path.endswith(".log"):
                        file_type = "Log file"
                    elif file_path.endswith((".mp3", ".wav", ".m4a")):
                        file_type = "Audio file"
                    else:
                        file_type = "File"
                    
                    if file_path not in new_files:
                        new_files[file_path] = file_type
        
        return new_files
    
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
    
    def _generate_summary(self, execution_steps: List[Dict], final_result: str) -> str:
        """Generate task execution summary"""
        
        # execution_steps 现在只包含成功的步骤
        total_successful_steps = len(execution_steps)
        
        tool_names = [step.get("tool_name", "unknown") for step in execution_steps]
        
        summary = f"""**Task Execution Summary**

**Execution Status**
✅ Task completed - {total_successful_steps} successful steps

**Tools Used**
Used tools: {' → '.join(tool_names) if tool_names else 'None'}

**Final Result**
{final_result}"""
        
        return summary
    
    async def cleanup(self):
        """Clean up resources"""
        for agent_data in self.agents.values():
            mcp_client = agent_data.get("mcp_client")
            if mcp_client:
                # Add MCP client cleanup logic here if needed
                pass
        
        self.agents.clear()
        logger.info("LangChain MCP Executor has been cleaned up")