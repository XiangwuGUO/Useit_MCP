#!/usr/bin/env python3
"""
MCP工具标准响应格式规范

为开源社区提供统一、可扩展的MCP工具响应格式，确保：
1. 一致性：所有工具返回统一格式
2. 可扩展性：支持未来功能扩展
3. 可读性：清晰的结构和文档
4. 兼容性：向后兼容现有实现
"""

from typing import Dict, List, Any, Optional, Union, Literal
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
import json


class OperationType(Enum):
    """操作类型枚举"""
    READ = "read"           # 读取操作（文件读取、数据查询等）
    WRITE = "write"         # 写入操作（文件写入、数据保存等）
    CREATE = "create"       # 创建操作（新建文件、目录等）
    UPDATE = "update"       # 更新操作（修改文件、更新数据等）
    DELETE = "delete"       # 删除操作（删除文件、清除数据等）
    PROCESS = "process"     # 处理操作（转换、计算、分析等）
    QUERY = "query"         # 查询操作（搜索、列表等）
    SYSTEM = "system"       # 系统操作（配置、状态检查等）


class ResponseStatus(Enum):
    """响应状态枚举"""
    SUCCESS = "success"     # 操作成功
    ERROR = "error"         # 操作失败
    WARNING = "warning"     # 操作成功但有警告
    PARTIAL = "partial"     # 部分成功


@dataclass
class FileInfo:
    """文件信息标准结构"""
    path: str                           # 相对于base_dir的路径
    description: str                    # 文件描述（如：文本文件、图片、音频片段等）
    size: Optional[int] = None          # 文件大小（字节）
    created_at: Optional[str] = None    # 创建时间（ISO格式）
    mime_type: Optional[str] = None     # MIME类型
    metadata: Optional[Dict[str, Any]] = None  # 额外元数据


@dataclass
class ExecutionMetrics:
    """执行指标"""
    execution_time: float               # 执行时间（秒）
    memory_usage: Optional[float] = None # 内存使用量（MB）
    cpu_usage: Optional[float] = None   # CPU使用率
    items_processed: Optional[int] = None # 处理项目数量


@dataclass
class StandardMCPResponse:
    """标准MCP工具响应格式"""
    
    # === 核心字段 ===
    status: ResponseStatus              # 操作状态
    operation: OperationType           # 操作类型
    message: str                       # 人类可读的结果描述
    
    # === 数据字段 ===
    data: Optional[Any] = None         # 主要返回数据
    new_files: Optional[List[FileInfo]] = None  # 新创建的文件列表
    modified_files: Optional[List[FileInfo]] = None  # 修改的文件列表
    deleted_files: Optional[List[str]] = None   # 删除的文件路径列表
    
    # === 元数据字段 ===
    tool_name: Optional[str] = None    # 工具名称
    version: str = "1.0.0"             # 响应格式版本
    timestamp: Optional[str] = None    # 响应时间戳
    request_id: Optional[str] = None   # 请求ID（用于跟踪）
    
    # === 性能和诊断 ===
    metrics: Optional[ExecutionMetrics] = None  # 执行指标
    warnings: Optional[List[str]] = None        # 警告信息列表
    debug_info: Optional[Dict[str, Any]] = None # 调试信息
    
    # === 分页和继续操作 ===
    pagination: Optional[Dict[str, Any]] = None  # 分页信息
    next_action: Optional[Dict[str, Any]] = None # 后续可执行的操作建议
    
    def __post_init__(self):
        """初始化后处理"""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        
        # 确保枚举类型正确
        if isinstance(self.status, str):
            self.status = ResponseStatus(self.status)
        if isinstance(self.operation, str):
            self.operation = OperationType(self.operation)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, Enum):
                    result[key] = value.value
                else:
                    result[key] = value
        return result
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """转换为JSON格式"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class MCPResponseBuilder:
    """MCP响应构建器 - 简化响应创建过程"""
    
    def __init__(self, tool_name: str, request_id: Optional[str] = None):
        self.tool_name = tool_name
        self.request_id = request_id
        self.start_time = datetime.utcnow()
    
    def success(
        self,
        operation: OperationType,
        message: str,
        data: Optional[Any] = None,
        new_files: Optional[List[FileInfo]] = None
    ) -> StandardMCPResponse:
        """创建成功响应"""
        return self._build_response(
            status=ResponseStatus.SUCCESS,
            operation=operation,
            message=message,
            data=data,
            new_files=new_files
        )
    
    def error(
        self,
        operation: OperationType,
        message: str,
        error_details: Optional[str] = None
    ) -> StandardMCPResponse:
        """创建错误响应"""
        debug_info = {"error_details": error_details} if error_details else None
        return self._build_response(
            status=ResponseStatus.ERROR,
            operation=operation,
            message=message,
            debug_info=debug_info
        )
    
    def warning(
        self,
        operation: OperationType,
        message: str,
        data: Optional[Any] = None,
        warnings: Optional[List[str]] = None
    ) -> StandardMCPResponse:
        """创建警告响应"""
        return self._build_response(
            status=ResponseStatus.WARNING,
            operation=operation,
            message=message,
            data=data,
            warnings=warnings
        )
    
    def partial(
        self,
        operation: OperationType,
        message: str,
        data: Optional[Any] = None,
        warnings: Optional[List[str]] = None
    ) -> StandardMCPResponse:
        """创建部分成功响应"""
        return self._build_response(
            status=ResponseStatus.PARTIAL,
            operation=operation,
            message=message,
            data=data,
            warnings=warnings
        )
    
    def _build_response(
        self,
        status: ResponseStatus,
        operation: OperationType,
        message: str,
        **kwargs
    ) -> StandardMCPResponse:
        """构建响应对象"""
        execution_time = (datetime.utcnow() - self.start_time).total_seconds()
        
        return StandardMCPResponse(
            status=status,
            operation=operation,
            message=message,
            tool_name=self.tool_name,
            request_id=self.request_id,
            metrics=ExecutionMetrics(execution_time=execution_time),
            **kwargs
        )


# === 便捷函数 ===

def create_file_info(
    path: str,
    description: str,
    size: Optional[int] = None,
    mime_type: Optional[str] = None,
    **metadata
) -> FileInfo:
    """创建文件信息对象的便捷函数"""
    return FileInfo(
        path=path,
        description=description,
        size=size,
        mime_type=mime_type,
        metadata=metadata if metadata else None,
        created_at=datetime.utcnow().isoformat() + "Z"
    )


def quick_success(
    tool_name: str,
    operation: OperationType,
    message: str,
    data: Optional[Any] = None,
    new_files: Optional[List[FileInfo]] = None
) -> Dict[str, Any]:
    """快速创建成功响应字典"""
    builder = MCPResponseBuilder(tool_name)
    response = builder.success(operation, message, data, new_files)
    return response.to_dict()


def quick_error(
    tool_name: str,
    operation: OperationType,
    message: str,
    error_details: Optional[str] = None
) -> Dict[str, Any]:
    """快速创建错误响应字典"""
    builder = MCPResponseBuilder(tool_name)
    response = builder.error(operation, message, error_details)
    return response.to_dict()


# === 向后兼容性支持 ===

def legacy_to_standard(legacy_response: Dict[str, Any], tool_name: str, operation: OperationType) -> Dict[str, Any]:
    """将旧格式响应转换为标准格式"""
    
    # 检测状态
    if "error" in legacy_response:
        status = ResponseStatus.ERROR
        message = legacy_response.get("error", "Unknown error")
    elif legacy_response.get("status") == "ok":
        status = ResponseStatus.SUCCESS
        message = legacy_response.get("message", "Operation completed successfully")
    else:
        status = ResponseStatus.SUCCESS
        message = "Operation completed"
    
    # 转换new_files格式
    new_files = None
    if "new_files" in legacy_response:
        legacy_files = legacy_response["new_files"]
        if isinstance(legacy_files, dict):
            new_files = [
                create_file_info(path=path, description=desc)
                for path, desc in legacy_files.items()
            ]
    
    # 提取数据
    data = {k: v for k, v in legacy_response.items() 
            if k not in ["status", "error", "message", "new_files"]}
    
    builder = MCPResponseBuilder(tool_name)
    if status == ResponseStatus.ERROR:
        response = builder.error(operation, message)
    else:
        response = builder.success(operation, message, data=data, new_files=new_files)
    
    return response.to_dict()


if __name__ == "__main__":
    # 示例用法
    print("=== MCP标准响应格式示例 ===\n")
    
    # 1. 文件读取成功示例
    builder = MCPResponseBuilder("read_file", "req_123")
    read_response = builder.success(
        operation=OperationType.READ,
        message="Successfully read file content",
        data={"content": "Hello, World!", "encoding": "utf-8", "lines": 1}
    )
    print("1. 文件读取成功:")
    print(read_response.to_json(indent=2))
    print()
    
    # 2. 文件创建成功示例
    create_response = builder.success(
        operation=OperationType.CREATE,
        message="Successfully created 3 files",
        new_files=[
            create_file_info("documents/report.pdf", "PDF报告", size=2048, mime_type="application/pdf"),
            create_file_info("images/chart.png", "图表图片", size=1024, mime_type="image/png"),
            create_file_info("data/results.json", "结果数据", size=512, mime_type="application/json")
        ]
    )
    print("2. 文件创建成功:")
    print(create_response.to_json(indent=2))
    print()
    
    # 3. 错误响应示例
    error_response = builder.error(
        operation=OperationType.READ,
        message="File not found",
        error_details="The specified file '/path/to/missing.txt' does not exist"
    )
    print("3. 错误响应:")
    print(error_response.to_json(indent=2))
    print()
    
    # 4. 部分成功示例
    partial_response = builder.partial(
        operation=OperationType.PROCESS,
        message="Processed 8 out of 10 files successfully",
        data={"processed": 8, "failed": 2, "total": 10},
        warnings=["File 'corrupt.txt' could not be processed", "File 'locked.doc' is read-only"]
    )
    print("4. 部分成功响应:")
    print(partial_response.to_json(indent=2))
    print()
    
    # 5. 向后兼容转换示例
    legacy_response = {
        "status": "ok",
        "path": "/home/user/test.txt",
        "new_files": {
            "test.txt": "文本文件",
            "backup.txt": "备份文件"
        }
    }
    
    converted = legacy_to_standard(legacy_response, "write_file", OperationType.CREATE)
    print("5. 向后兼容转换:")
    print(json.dumps(converted, ensure_ascii=False, indent=2))