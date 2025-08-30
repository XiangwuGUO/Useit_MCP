"""
智能任务执行器

使用Claude API理解自然语言任务描述，自动生成并执行MCP工具调用序列
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

import httpx

from .api_models import TaskRequest, TaskResult, ToolInfo
from .client_manager import client_manager

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
    
    def __init__(self, anthropic_api_key: str = None):
        """初始化执行器"""
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
            execution_steps = await self._analyze_task_with_claude(task_request, available_tools)
            
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
                execution_time_seconds=execution_time
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
        client = await client_manager.get_client(vm_id, session_id)
        if not client:
            raise Exception(f"客户机不存在: {vm_id}/{session_id}")
        
        return await client.list_tools()
    
    async def _analyze_task_with_claude(self, task_request: TaskRequest, available_tools: List[ToolInfo]) -> List[ExecutionStep]:
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
            
            return self._parse_claude_response(claude_response)
            
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
                result = await client_manager.call_tool(
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
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()


# 全局任务执行器实例
_task_executor = None

def get_task_executor() -> TaskExecutor:
    """获取任务执行器实例"""
    global _task_executor
    if _task_executor is None:
        _task_executor = TaskExecutor()
    return _task_executor

async def execute_intelligent_task(task_request: TaskRequest) -> TaskResult:
    """执行智能任务的便捷函数"""
    executor = get_task_executor()
    return await executor.execute_task(task_request)