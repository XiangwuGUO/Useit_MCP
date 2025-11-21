"""
简化的API数据模型定义

专注于核心MCP功能，使用LangChain处理AI逻辑
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
    name: str = Field(..., description="服务器名称")
    url: str = Field(..., description="远程MCP服务器地址")
    description: str = Field("", description="服务器描述")
    transport: str = Field("http", description="传输协议")


class ClientStatus(BaseModel):
    """客户机状态"""
    vm_id: str
    session_id: str
    status: str  # connected, disconnected, error
    tool_count: int
    resource_count: int
    server_count: int
    connected_servers: List[str]
    last_seen: Optional[str] = None


# === 工具调用模型 ===

class ToolCall(BaseModel):
    """工具调用请求"""
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    vm_id: str = Field(..., description="虚拟机ID")
    session_id: str = Field(..., description="会话ID")
    server_name: Optional[str] = Field(None, description="指定服务器名称")


class ToolFindCall(BaseModel):
    """查找并调用工具请求"""
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    preferred_vm_id: Optional[str] = Field(None, description="优先使用的虚拟机ID")


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    vm_id: str
    session_id: str
    server_name: str
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
    server_name: str
    mimeType: Optional[str] = None


# === 服务器注册模型 ===

class ServerRegistrationInfo(BaseModel):
    """服务器注册信息"""
    name: str = Field(..., description="服务器名称")
    url: str = Field(..., description="服务器URL地址")
    description: str = Field("", description="服务器描述")


# === 文件处理模型 ===

class FileReference(BaseModel):
    """文件引用（支持图片、文本等）"""
    path: str = Field(..., description="文件相对路径")
    type: str = Field(..., description="文件类型: image, text, json, csv, etc.")
    mime_type: Optional[str] = Field(None, description="MIME类型（图片文件必需）")
    content: str = Field(..., description="文件内容（图片为base64编码，文本为原始内容）")
    description: Optional[str] = Field(None, description="文件描述")


class FilesInputConfig(BaseModel):
    """文件输入配置"""
    files_directory: str = Field(..., description="包含输入文件的目录路径")
    file_manifest_path: str = Field(..., description="文件说明JSON的路径")
    auto_select: bool = Field(False, description="是否使用AI自动选择相关文件")
    max_files: int = Field(5, description="最多选择的文件数量")


# === LangChain任务模型 ===

class TaskRequest(BaseModel):
    """智能任务请求 (由LangChain处理)"""
    vm_id: str = Field(..., description="虚拟机ID")
    session_id: str = Field(..., description="会话ID")
    mcp_server_name: str = Field(..., description="MCP服务器名称")
    task_description: str = Field(..., description="任务描述")
    context: Optional[str] = Field(None, description="任务上下文")

    # 新增：自动注入的metadata
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="自动注入到所有工具调用的metadata，LLM不可见"
    )

    # 新增：文件输入配置
    files_input: Optional[FilesInputConfig] = Field(
        None,
        description="文件输入配置，系统会自动读取并编码文件"
    )


class TaskResult(BaseModel):
    """任务执行结果"""
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
    new_files: Optional[Dict[str, str]] = None  # 新生成文件：{相对路径: 描述}


# === 简化的智能工具调用 ===

class SmartToolCall(BaseModel):
    """智能工具调用请求 (单步调用)"""
    mcp_server_name: str = Field(..., description="MCP服务器名称")
    task_description: str = Field(..., description="要执行的任务描述")
    vm_id: str = Field(..., description="虚拟机ID")
    session_id: str = Field(..., description="会话ID")


class SmartToolResult(BaseModel):
    """智能工具调用结果"""
    success: bool
    mcp_server_name: str
    selected_tool_name: Optional[str] = None
    vm_id: str
    session_id: str
    task_description: str
    result: Any
    completion_summary: str
    execution_time_seconds: float
    error_message: Optional[str] = None
    new_files: Optional[Dict[str, str]] = None


# === 直接调用模型 ===

class DirectToolCallRequest(BaseModel):
    """直接工具调用请求（跳过LLM推理）"""
    vm_id: str = Field(..., description="虚拟机ID")
    session_id: str = Field(..., description="会话ID")
    mcp_server_name: str = Field(..., description="MCP Server名称")
    tool_name: str = Field(..., description="工具名称")

    # 工具的业务参数
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具的业务参数（由调用方准备好）"
    )

    # 额外的metadata（不经过LLM）
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="额外的元数据，直接传递给MCP Server（如：user_id, session_info等）"
    )

    # 文件输入（自动处理）
    files_input: Optional[FilesInputConfig] = Field(
        None,
        description="文件输入配置，系统会自动读取并编码文件"
    )


class DirectToolCallResult(BaseModel):
    """直接工具调用结果"""
    success: bool
    tool_name: str
    mcp_server_name: str
    vm_id: str
    session_id: str
    result: Any
    execution_time_seconds: float
    metadata_included: bool
    files_count: int = 0
    error_message: Optional[str] = None