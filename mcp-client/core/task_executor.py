"""
智能任务执行器

使用Claude API理解自然语言任务描述，自动生成并执行MCP工具调用序列
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import httpx

from .api_models import TaskRequest, TaskResult, ToolInfo, SmartToolResult
from .client_manager import ClientManager

logger = logging.getLogger(__name__)

# Claude API 配置
import sys
from pathlib import Path
# 添加父目录到sys.path以支持绝对导入
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config.settings import settings

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"


@dataclass
class ExecutionStep:
    """执行步骤"""
    tool_name: str
    arguments: Dict[str, Any]
    reasoning: str


class TaskExecutor:
    """智能任务执行器"""
    
    def __init__(self, client_manager: ClientManager, anthropic_api_key: str = None):
        """初始化执行器"""
        self.client_manager = client_manager
        self.api_key = anthropic_api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("需要设置 ANTHROPIC_API_KEY 环境变量")
        
        self.http_client = httpx.AsyncClient(timeout=300.0)
    
    async def execute_task(self, task_request: TaskRequest) -> TaskResult:
        """执行智能任务"""
        start_time = datetime.now()
        task_id = f"task_{task_request.vm_id}_{task_request.session_id}_{int(start_time.timestamp())}"
        
        try:
            # 1. 获取可用工具
            available_tools = await self._get_available_tools(task_request.vm_id, task_request.session_id)
            if not available_tools:
                raise Exception(f"客户机 {task_request.vm_id}/{task_request.session_id} 没有可用工具")
            
            # 2. 使用Claude API分析任务
            execution_steps, token_usage = await self._analyze_task_with_claude(task_request, available_tools)
            
            # 3. 执行步骤
            results = await self._execute_steps(task_request, execution_steps)
            
            # 4. 生成摘要
            summary = self._generate_summary(task_request, results)
            
            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return TaskResult(
                success=True,
                task_id=task_id,
                vm_id=task_request.vm_id,
                session_id=task_request.session_id,
                mcp_server_name=task_request.mcp_server_name,
                original_task=task_request.task_description,
                execution_steps=results,
                final_result=results[-1].get("result", "") if results else "",
                summary=summary,
                execution_time_seconds=execution_time,
                token_usage=token_usage
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_summary = f"任务执行失败: {str(e)}"
            
            return TaskResult(
                success=False,
                task_id=task_id,
                vm_id=task_request.vm_id,
                session_id=task_request.session_id,
                mcp_server_name=task_request.mcp_server_name,
                original_task=task_request.task_description,
                execution_steps=[],
                final_result="",
                summary=error_summary,
                execution_time_seconds=execution_time,
                error_message=str(e)
            )
    
    async def _get_available_tools(self, vm_id: str, session_id: str) -> List[ToolInfo]:
        """获取指定客户机的可用工具"""
        client = await self.client_manager.get_client(vm_id, session_id)
        if not client:
            raise Exception(f"客户机不存在: {vm_id}/{session_id}")
        
        return await client.get_all_tools()
    
    async def _analyze_task_with_claude(self, task_request: TaskRequest, available_tools: List[ToolInfo]) -> Tuple[List[ExecutionStep], Dict[str, int]]:
        """使用Claude API分析任务"""
        
        # 构建工具描述
        tools_description = self._format_tools_description(available_tools)
        
        # 构建提示
        prompt = f"""你是一个智能任务执行助手，需要将用户的自然语言任务描述转换为具体的MCP工具调用序列。

**用户任务**: {task_request.task_description}

**目标客户机**: {task_request.vm_id}/{task_request.session_id} ({task_request.mcp_server_name})

**可用工具**:
{tools_description}

**要求**:
1. 仔细分析任务描述，理解用户的真正意图
2. 将复杂任务分解为可执行的步骤
3. 为每个步骤选择最合适的工具
4. 生成具体的工具调用参数
5. 确保步骤之间的逻辑连贯性
6. 如果涉及文件操作，自动包含session_id参数

**输出格式** (严格按照JSON格式):
```json
[
  {{
    "tool_name": "工具名称",
    "arguments": {{
      "参数名": "参数值",
      "session_id": "{task_request.session_id}"
    }},
    "reasoning": "选择此工具的原因和预期效果"
  }},
  ...
]
```

**重要提示**:
- 如果是文件系统操作，参数通常需要包装在"req"对象中
- 所有涉及文件的操作都要包含session_id参数
- 确保参数格式与工具定义完全匹配
- 步骤顺序要合理（比如先创建目录再写文件）
- 最多生成{task_request.max_steps}个步骤

请开始分析并生成执行计划："""

        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": settings.claude_model,
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            response = await self.http_client.post(CLAUDE_API_URL, headers=headers, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Claude API调用失败: {response.status_code} - {response.text}")
            
            result = response.json()
            claude_response = result["content"][0]["text"]
            
            # 提取token使用情况
            token_usage = {}
            if "usage" in result:
                usage = result["usage"]
                token_usage[settings.claude_model] = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            
            execution_steps = self._parse_claude_response(claude_response)
            return execution_steps, token_usage
            
        except Exception as e:
            logger.error(f"Claude API分析失败: {e}")
            raise Exception(f"任务分析失败: {str(e)}")
    
    def _format_tools_description(self, tools: List[ToolInfo]) -> str:
        """格式化工具描述"""
        if not tools:
            return "无可用工具"
        
        descriptions = []
        for tool in tools:
            desc = f"**{tool.name}**: {tool.description}"
            
            # 添加参数信息
            if tool.input_schema and "properties" in tool.input_schema:
                props = tool.input_schema["properties"]
                params = []
                for param_name, param_info in props.items():
                    param_desc = param_name
                    if "type" in param_info:
                        param_desc += f" ({param_info['type']})"
                    if "description" in param_info:
                        param_desc += f": {param_info['description']}"
                    params.append(param_desc)
                
                if params:
                    desc += f"\n  参数: {', '.join(params)}"
            
            descriptions.append(desc)
        
        return "\n\n".join(descriptions)
    
    def _parse_claude_response(self, claude_response: str) -> List[ExecutionStep]:
        """解析Claude响应"""
        try:
            # 提取JSON部分
            json_start = claude_response.find("```json")
            if json_start != -1:
                json_start += 7  # len("```json")
                json_end = claude_response.find("```", json_start)
                if json_end != -1:
                    json_str = claude_response[json_start:json_end].strip()
                else:
                    json_str = claude_response[json_start:].strip()
            else:
                # 尝试直接解析
                json_str = claude_response.strip()
            
            # 解析JSON
            steps_data = json.loads(json_str)
            
            # 转换为ExecutionStep对象
            steps = []
            for step_data in steps_data:
                step = ExecutionStep(
                    tool_name=step_data["tool_name"],
                    arguments=step_data["arguments"],
                    reasoning=step_data.get("reasoning", "")
                )
                steps.append(step)
            
            logger.info(f"解析出 {len(steps)} 个执行步骤")
            return steps
            
        except Exception as e:
            logger.error(f"Claude响应解析失败: {e}")
            logger.debug(f"Claude响应内容: {claude_response}")
            raise Exception(f"任务计划解析失败: {str(e)}")
    
    async def _execute_steps(self, task_request: TaskRequest, steps: List[ExecutionStep]) -> List[Dict[str, Any]]:
        """执行步骤序列"""
        results = []
        
        for i, step in enumerate(steps, 1):
            try:
                logger.info(f"执行步骤 {i}/{len(steps)}: {step.tool_name}")
                
                # 调用工具
                result = await self.client_manager.call_tool(
                    task_request.vm_id,
                    task_request.session_id,
                    step.tool_name,
                    step.arguments
                )
                
                step_result = {
                    "step": i,
                    "tool_name": step.tool_name,
                    "arguments": step.arguments,
                    "reasoning": step.reasoning,
                    "result": self._format_tool_result(result),
                    "status": "success"
                }
                
                results.append(step_result)
                logger.info(f"✅ 步骤 {i} 执行成功")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ 步骤 {i} 执行失败: {error_msg}")
                
                step_result = {
                    "step": i,
                    "tool_name": step.tool_name,
                    "arguments": step.arguments,
                    "reasoning": step.reasoning,
                    "error": error_msg,
                    "status": "error"
                }
                
                results.append(step_result)
                # 遇到错误时停止执行
                break
        
        return results
    
    def _format_tool_result(self, result: Any) -> str:
        """格式化工具执行结果"""
        if hasattr(result, 'content') and result.content:
            # MCP响应格式
            content = result.content[0]
            if hasattr(content, 'text'):
                return content.text
        
        if isinstance(result, dict):
            return json.dumps(result, indent=2, ensure_ascii=False)
        
        return str(result)
    
    def _generate_summary(self, task_request: TaskRequest, results: List[Dict[str, Any]]) -> str:
        """生成任务摘要"""
        if not results:
            return "任务未执行任何步骤"
        
        success_count = sum(1 for r in results if r.get("status") == "success")
        total_steps = len(results)
        
        # 状态摘要
        if success_count == total_steps:
            status_line = f"✅ 任务完成 - 所有 {total_steps} 个步骤执行成功"
        else:
            status_line = f"⚠️ 任务部分完成 - {success_count}/{total_steps} 个步骤成功"
        
        # 步骤详情
        steps_summary = []
        for result in results:
            if result.get("status") == "success":
                steps_summary.append(f"✅ 步骤{result['step']}: {result['tool_name']} - 成功")
            else:
                steps_summary.append(f"❌ 步骤{result['step']}: {result['tool_name']} - {result.get('error', '失败')}")
        
        # 最终结果
        final_result = ""
        if results and results[-1].get("status") == "success":
            final_result = f"\n\n**最终结果**: {results[-1].get('result', '执行完成')}"
        
        summary = f"""**任务摘要**
原始任务: {task_request.task_description}

**执行状态**
{status_line}

**步骤详情**
{chr(10).join(steps_summary)}{final_result}"""
        
        return summary.strip()
    
    async def _generate_tool_arguments_with_ai(self, tool: ToolInfo, task_description: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """使用AI生成工具调用参数"""
        
        # 构建工具描述
        tool_desc = f"**{tool.name}**: {tool.description}"
        if tool.input_schema and "properties" in tool.input_schema:
            props = tool.input_schema["properties"]
            params = []
            for param_name, param_info in props.items():
                param_desc = param_name
                if "type" in param_info:
                    param_desc += f" ({param_info['type']})"
                if "description" in param_info:
                    param_desc += f": {param_info['description']}"
                params.append(param_desc)
            
            if params:
                tool_desc += f"\n  参数: {', '.join(params)}"
        
        # 构建提示
        prompt = f"""你是一个智能工具调用助手，需要根据用户任务描述为指定工具生成合适的调用参数。

**工具信息**: 
{tool_desc}

**用户任务**: {task_description}

**要求**:
1. 仔细分析工具的输入参数要求
2. 根据任务描述推断合理的参数值
3. 如果是文件系统操作，参数通常需要包装在"req"对象中
4. 确保参数格式与工具定义完全匹配
5. 如果任务涉及文件路径，使用相对路径

**输出格式** (严格按照JSON格式):
```json
{{
  "参数名": "参数值"
}}
```

请生成工具调用参数："""

        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": settings.claude_model,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            response = await self.http_client.post(CLAUDE_API_URL, headers=headers, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Claude API调用失败: {response.status_code} - {response.text}")
            
            result = response.json()
            claude_response = result["content"][0]["text"]
            
            # 提取token使用情况
            token_usage = {}
            if "usage" in result:
                usage = result["usage"]
                token_usage[settings.claude_model] = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            
            # 解析参数
            arguments = self._parse_tool_arguments(claude_response)
            
            return arguments, token_usage
            
        except Exception as e:
            logger.error(f"Claude API生成参数失败: {e}")
            raise Exception(f"参数生成失败: {str(e)}")
    
    def _parse_tool_arguments(self, claude_response: str) -> Dict[str, Any]:
        """解析Claude响应的工具参数"""
        try:
            # 提取JSON部分
            json_start = claude_response.find("```json")
            if json_start != -1:
                json_start += 7  # len("```json")
                json_end = claude_response.find("```", json_start)
                if json_end != -1:
                    json_str = claude_response[json_start:json_end].strip()
                else:
                    json_str = claude_response[json_start:].strip()
            else:
                # 尝试直接解析
                json_str = claude_response.strip()
            
            # 解析JSON
            arguments = json.loads(json_str)
            
            logger.info(f"解析出工具参数: {arguments}")
            return arguments
            
        except Exception as e:
            logger.error(f"工具参数解析失败: {e}")
            logger.debug(f"Claude响应内容: {claude_response}")
            raise Exception(f"工具参数解析失败: {str(e)}")
    
    async def _select_tool_and_generate_arguments(self, available_tools: List[ToolInfo], 
                                                 task_description: str, mcp_server_name: str) -> Tuple[ToolInfo, Dict[str, Any], Dict[str, int]]:
        """使用AI选择合适的工具并生成参数"""
        
        # 构建工具列表描述
        tools_desc = self._format_tools_description(available_tools)
        
        # 构建提示
        prompt = f"""你是一个智能工具选择和参数生成助手。用户想在MCP服务器 '{mcp_server_name}' 上执行任务，你需要选择最合适的工具并生成调用参数。

**用户任务**: {task_description}

**MCP服务器**: {mcp_server_name}

**可用工具**:
{tools_desc}

**要求**:
1. 根据任务描述选择最合适的工具
2. 为选定的工具生成合适的调用参数
3. 如果是文件系统操作，参数通常需要包装在"req"对象中
4. 确保参数格式与工具定义完全匹配
5. 如果任务涉及文件路径，使用相对路径

**输出格式** (严格按照JSON格式):
```json
{{
  "selected_tool": "工具名称",
  "arguments": {{
    "参数名": "参数值"
  }}
}}
```

请选择工具并生成参数："""

        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": settings.claude_model,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            response = await self.http_client.post(CLAUDE_API_URL, headers=headers, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Claude API调用失败: {response.status_code} - {response.text}")
            
            result = response.json()
            claude_response = result["content"][0]["text"]
            
            # 提取token使用情况
            token_usage = {}
            if "usage" in result:
                usage = result["usage"]
                token_usage[settings.claude_model] = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            
            # 解析选择的工具和参数
            tool_selection = self._parse_tool_selection(claude_response)
            selected_tool_name = tool_selection["selected_tool"]
            arguments = tool_selection["arguments"]
            
            # 找到选定的工具对象
            selected_tool = None
            for tool in available_tools:
                if tool.name == selected_tool_name:
                    selected_tool = tool
                    break
            
            if not selected_tool:
                raise Exception(f"AI选择的工具不存在: {selected_tool_name}")
            
            return selected_tool, arguments, token_usage
            
        except Exception as e:
            logger.error(f"工具选择和参数生成失败: {e}")
            raise Exception(f"工具选择失败: {str(e)}")
    
    def _parse_tool_selection(self, claude_response: str) -> Dict[str, Any]:
        """解析Claude响应的工具选择"""
        try:
            # 提取JSON部分
            json_start = claude_response.find("```json")
            if json_start != -1:
                json_start += 7  # len("```json")
                json_end = claude_response.find("```", json_start)
                if json_end != -1:
                    json_str = claude_response[json_start:json_end].strip()
                else:
                    json_str = claude_response[json_start:].strip()
            else:
                # 尝试直接解析
                json_str = claude_response.strip()
            
            # 解析JSON
            selection = json.loads(json_str)
            
            if "selected_tool" not in selection or "arguments" not in selection:
                raise ValueError("响应格式不正确，缺少必需字段")
            
            logger.info(f"AI选择的工具: {selection['selected_tool']}")
            logger.info(f"生成的参数: {selection['arguments']}")
            return selection
            
        except Exception as e:
            logger.error(f"工具选择解析失败: {e}")
            logger.debug(f"Claude响应内容: {claude_response}")
            raise Exception(f"工具选择解析失败: {str(e)}")
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()


# 便捷函数

async def execute_intelligent_task(
    client_manager: ClientManager,
    vm_id: str,
    session_id: str,
    mcp_server_name: str,
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> TaskResult:
    """执行智能任务的便捷函数"""
    task_request = TaskRequest(
        vm_id=vm_id,
        session_id=session_id,
        mcp_server_name=mcp_server_name,
        task_description=task_description,
        context=context
    )
    
    executor = TaskExecutor(client_manager)
    return await executor.execute_task(task_request)


async def execute_smart_tool_call(
    client_manager: ClientManager,
    mcp_server_name: str,
    task_description: str,
    vm_id: str,
    session_id: str
) -> SmartToolResult:
    """执行智能工具调用的便捷函数"""
    start_time = datetime.now()
    
    try:
        # 1. 获取指定客户机
        client = await client_manager.get_client(vm_id, session_id)
        if not client:
            raise Exception(f"客户机不存在: {vm_id}/{session_id}")
        
        # 2. 获取指定服务器的工具
        server = await client.get_server(mcp_server_name)
        if not server or not server.connected:
            raise Exception(f"服务器不存在或未连接: {mcp_server_name}")
        
        server_tools = await server.get_tools(vm_id, session_id)
        if not server_tools:
            raise Exception(f"服务器 {mcp_server_name} 没有可用工具")
        
        # 3. 使用AI选择合适的工具并生成参数
        executor = TaskExecutor(client_manager)
        selected_tool, arguments, token_usage = await executor._select_tool_and_generate_arguments(
            server_tools, task_description, mcp_server_name
        )
        
        # 4. 调用选定的工具
        result = await server.call_tool(selected_tool.name, arguments)
        
        # 5. 生成完成摘要
        summary = f"成功在服务器 '{mcp_server_name}' 上使用工具 '{selected_tool.name}' 完成任务: {task_description}"
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return SmartToolResult(
            success=True,
            mcp_server_name=mcp_server_name,
            selected_tool_name=selected_tool.name,
            vm_id=vm_id,
            session_id=session_id,
            task_description=task_description,
            result=result,
            completion_summary=summary,
            execution_time_seconds=execution_time,
            token_usage=token_usage
        )
        
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_summary = f"智能工具调用失败: {str(e)}"
        
        return SmartToolResult(
            success=False,
            mcp_server_name=mcp_server_name,
            selected_tool_name=None,
            vm_id=vm_id,
            session_id=session_id,
            task_description=task_description,
            result=None,
            completion_summary=error_summary,
            execution_time_seconds=execution_time,
            error_message=str(e)
        )