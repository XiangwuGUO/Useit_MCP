#!/usr/bin/env python3
"""
SSE流式响应数据模型
定义流式任务执行过程中的各种事件类型
"""

from typing import Dict, Any, Literal, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field


class StreamEvent(BaseModel):
    """基础流式事件"""
    type: Literal["start", "tool_start", "tool_result", "progress", "complete", "error"]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    data: Dict[str, Any]


class TaskStartEvent(BaseModel):
    """任务开始事件"""
    task_id: str
    vm_id: str
    session_id: str
    mcp_server_name: str
    task_description: str
    context: Optional[str] = None
    estimated_steps: Optional[int] = None


class ToolStartEvent(BaseModel):
    """工具开始执行事件"""
    task_id: str
    step_number: int
    tool_name: str
    server_name: str
    arguments: Dict[str, Any]
    reasoning: Optional[str] = None


class ToolResultEvent(BaseModel):
    """工具执行结果事件"""
    task_id: str
    step_number: int
    tool_name: str
    server_name: str
    result: Any
    status: Literal["success", "error", "timeout"]
    execution_time: float
    error_message: Optional[str] = None


class ProgressEvent(BaseModel):
    """进度更新事件"""
    task_id: str
    current_step: int
    total_steps: int
    status: str
    message: str
    completion_percentage: int


class TaskCompleteEvent(BaseModel):
    """任务完成事件"""
    task_id: str
    success: bool
    final_result: str
    summary: str
    execution_time: float
    total_steps: int
    successful_steps: int
    new_files: Dict[str, str]
    error_message: Optional[str] = None


class TaskErrorEvent(BaseModel):
    """任务错误事件"""
    task_id: str
    error_message: str
    error_type: str
    step_number: Optional[int] = None
    tool_name: Optional[str] = None


# SSE消息包装器
class SSEMessage(BaseModel):
    """SSE消息包装"""
    id: Optional[str] = None
    event: Optional[str] = None
    data: str
    retry: Optional[int] = None

    def to_sse_string(self) -> str:
        """转换为SSE格式字符串"""
        lines = []
        
        if self.id:
            lines.append(f"id: {self.id}")
        if self.event:
            lines.append(f"event: {self.event}")
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        # 数据可能包含多行
        for line in self.data.split('\n'):
            lines.append(f"data: {line}")
        
        lines.append('')  # 空行表示消息结束
        return '\n'.join(lines)


# 流式任务状态
class StreamTaskStatus(BaseModel):
    """流式任务状态"""
    task_id: str
    vm_id: str
    session_id: str
    mcp_server_name: str
    task_description: str
    status: Literal["pending", "running", "completed", "error"]
    start_time: datetime
    end_time: Optional[datetime] = None
    current_step: int = 0
    total_steps: int = 0
    execution_steps: list = Field(default_factory=list)
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }