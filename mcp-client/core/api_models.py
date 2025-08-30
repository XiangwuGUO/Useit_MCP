"""
API数据模型定义

统一管理所有FastAPI接口的数据模型
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# === 基础模型 ===

class APIResponse(BaseModel):
    """API响应基础模型"""
    success: bool
    message: str
    data: Any = None


# === 客户机管理模型 ===

class ClientInfo(BaseModel):
    """客户机信息"""
    vm_id: str = Field(..., description="虚拟机ID")
    session_id: str = Field(..., description="会话ID") 
    remote_url: str = Field(..., description="远程MCP服务器地址")
    description: str = Field("", description="客户机描述")


class ClientStatus(BaseModel):
    """客户机状态"""
    vm_id: str
    session_id: str
    status: str  # connected, disconnected, error
    tool_count: int
    resource_count: int
    remote_url: str
    last_seen: Optional[str] = None


# === 工具调用模型 ===

class ToolCall(BaseModel):
    """工具调用请求"""
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    vm_id: Optional[str] = Field(None, description="指定虚拟机ID")
    session_id: Optional[str] = Field(None, description="指定会话ID")


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    vm_id: str
    session_id: str
    input_schema: Dict[str, Any]


# === 资源模型 ===

class ResourceRead(BaseModel):
    """资源读取请求"""
    uri: str = Field(..., description="资源URI")
    vm_id: str = Field(..., description="虚拟机ID")
    session_id: str = Field(..., description="会话ID")


class ResourceInfo(BaseModel):
    """资源信息"""
    uri: str
    name: str
    description: str
    vm_id: str
    session_id: str


# === 智能任务模型 ===

class TaskRequest(BaseModel):
    """智能任务请求"""
    vm_id: str = Field(..., description="虚拟机ID")
    session_id: str = Field(..., description="会话ID") 
    mcp_server_name: str = Field(..., description="MCP服务器名称")
    task_description: str = Field(..., description="任务描述")
    max_steps: int = Field(10, description="最大执行步骤数")


class TaskResult(BaseModel):
    """智能任务结果"""
    success: bool
    task_id: str
    vm_id: str
    session_id: str
    mcp_server_name: str
    original_task: str
    execution_steps: List[Dict[str, Any]]
    final_result: str
    summary: str
    execution_time_seconds: float
    error_message: Optional[str] = None


# === 系统状态模型 ===

class HealthStatus(BaseModel):
    """健康检查状态"""
    status: str  # healthy, degraded, unhealthy
    total_clients: int
    connected_clients: int
    disconnected_clients: int
    uptime_seconds: float


class SystemMetrics(BaseModel):
    """系统指标"""
    active_sessions: int
    total_tools: int
    total_resources: int
    tasks_executed: int
    average_response_time_ms: float