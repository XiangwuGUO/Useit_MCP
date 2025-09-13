#!/usr/bin/env python3
"""
MCP标准化工具基类

提供标准化的MCP工具实现基类，简化开发过程，确保响应格式一致性。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import functools
import json
import time
import traceback
import uuid

from .standard_response import (
    StandardMCPResponse, MCPResponseBuilder, OperationType, ResponseStatus,
    FileInfo, create_file_info, legacy_to_standard
)


class BaseMCPTool(ABC):
    """MCP工具基类"""
    
    def __init__(self, tool_name: str, base_dir: Optional[Path] = None):
        self.tool_name = tool_name
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        
    @abstractmethod
    def get_operation_type(self) -> OperationType:
        """返回工具的主要操作类型"""
        pass
    
    def create_response_builder(self, request_id: Optional[str] = None) -> MCPResponseBuilder:
        """创建响应构建器"""
        return MCPResponseBuilder(self.tool_name, request_id or str(uuid.uuid4()))
    
    def get_relative_path(self, file_path: Union[str, Path]) -> str:
        """获取相对于base_dir的路径"""
        try:
            path = Path(file_path)
            if path.is_absolute():
                return str(path.relative_to(self.base_dir))
            return str(path)
        except ValueError:
            # 如果无法计算相对路径，返回文件名
            return Path(file_path).name
    
    def create_file_info_from_path(
        self, 
        file_path: Union[str, Path], 
        description: str,
        **metadata
    ) -> FileInfo:
        """从文件路径创建FileInfo对象"""
        path = Path(file_path)
        relative_path = self.get_relative_path(path)
        
        size = None
        mime_type = None
        
        if path.exists() and path.is_file():
            size = path.stat().st_size
            # 简单的MIME类型检测
            suffix = path.suffix.lower()
            mime_types = {
                '.txt': 'text/plain',
                '.json': 'application/json',
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.wav': 'audio/wav',
                '.mp3': 'audio/mpeg',
                '.mp4': 'video/mp4',
            }
            mime_type = mime_types.get(suffix)
        
        return create_file_info(
            path=relative_path,
            description=description,
            size=size,
            mime_type=mime_type,
            **metadata
        )


class FileSystemTool(BaseMCPTool):
    """文件系统工具基类"""
    
    def __init__(self, tool_name: str, base_dir: Optional[Path] = None):
        super().__init__(tool_name, base_dir)
    
    def get_operation_type(self) -> OperationType:
        """返回文件系统工具的默认操作类型"""
        return OperationType.READ
    
    def resolve_path(self, user_path: str, session_id: Optional[str] = None) -> Path:
        """解析用户路径到沙箱内的绝对路径"""
        candidate = Path(user_path)
        if not candidate.is_absolute():
            candidate = self.base_dir / candidate
        
        abs_path = candidate.expanduser().resolve()
        
        # 确保路径在沙箱内
        try:
            if abs_path == self.base_dir or self.base_dir in abs_path.parents:
                return abs_path
        except Exception:
            pass
        
        raise ValueError(f"路径超出沙箱范围: {abs_path} (沙箱: {self.base_dir})")
    
    def safe_file_operation(
        self,
        operation: OperationType,
        success_message: str,
        file_path: Optional[str] = None,
        **kwargs
    ):
        """安全的文件操作装饰器"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                builder = self.create_response_builder()
                try:
                    result = func(*args, **kwargs)
                    
                    # 如果返回的是旧格式，转换为新格式
                    if isinstance(result, dict) and "status" in result:
                        return legacy_to_standard(result, self.tool_name, operation)
                    
                    # 如果返回的已经是标准格式
                    if isinstance(result, (StandardMCPResponse, dict)):
                        return result.to_dict() if hasattr(result, 'to_dict') else result
                    
                    # 简单值返回
                    return builder.success(
                        operation=operation,
                        message=success_message,
                        data=result
                    ).to_dict()
                    
                except FileNotFoundError as e:
                    return builder.error(
                        operation=operation,
                        message="文件未找到",
                        error_details=str(e)
                    ).to_dict()
                
                except PermissionError as e:
                    return builder.error(
                        operation=operation,
                        message="权限不足",
                        error_details=str(e)
                    ).to_dict()
                
                except ValueError as e:
                    return builder.error(
                        operation=operation,
                        message="参数错误",
                        error_details=str(e)
                    ).to_dict()
                
                except Exception as e:
                    return builder.error(
                        operation=operation,
                        message="操作失败",
                        error_details=f"{type(e).__name__}: {str(e)}"
                    ).to_dict()
            
            return wrapper
        return decorator


class ProcessingTool(BaseMCPTool):
    """数据处理工具基类"""
    
    def get_operation_type(self) -> OperationType:
        return OperationType.PROCESS
    
    def process_with_progress(
        self,
        items: List[Any],
        processor_func,
        success_message_template: str = "成功处理 {successful} 个项目",
        **kwargs
    ) -> Dict[str, Any]:
        """带进度跟踪的批量处理"""
        builder = self.create_response_builder()
        
        successful = 0
        failed = 0
        errors = []
        results = []
        new_files = []
        
        for i, item in enumerate(items):
            try:
                result = processor_func(item, **kwargs)
                results.append(result)
                successful += 1
                
                # 收集新文件信息
                if isinstance(result, dict) and "new_files" in result:
                    if isinstance(result["new_files"], list):
                        new_files.extend(result["new_files"])
                    elif isinstance(result["new_files"], dict):
                        for path, desc in result["new_files"].items():
                            new_files.append(create_file_info(path, desc))
                
            except Exception as e:
                failed += 1
                errors.append(f"项目 {i+1}: {str(e)}")
        
        total = len(items)
        success_rate = successful / total if total > 0 else 0
        
        # 确定响应状态
        if failed == 0:
            status = ResponseStatus.SUCCESS
            message = success_message_template.format(successful=successful)
        elif successful == 0:
            return builder.error(
                operation=OperationType.PROCESS,
                message="所有项目处理失败",
                error_details="; ".join(errors[:5])  # 最多显示5个错误
            ).to_dict()
        else:
            status = ResponseStatus.PARTIAL
            message = f"部分成功：{successful}/{total} 个项目处理成功"
        
        # 构建响应
        response = StandardMCPResponse(
            status=status,
            operation=OperationType.PROCESS,
            message=message,
            data={
                "total": total,
                "successful": successful,
                "failed": failed,
                "success_rate": success_rate,
                "results": results
            },
            new_files=new_files if new_files else None,
            warnings=errors if errors else None,
            tool_name=self.tool_name,
            metrics=builder._build_response(status, OperationType.PROCESS, message).metrics
        )
        
        return response.to_dict()


class QueryTool(BaseMCPTool):
    """查询工具基类"""
    
    def get_operation_type(self) -> OperationType:
        return OperationType.QUERY
    
    def paginated_query(
        self,
        query_func,
        page: int = 1,
        per_page: int = 50,
        max_per_page: int = 1000,
        **query_kwargs
    ) -> Dict[str, Any]:
        """分页查询支持"""
        builder = self.create_response_builder()
        
        # 验证分页参数
        per_page = min(per_page, max_per_page)
        page = max(page, 1)
        
        try:
            # 执行查询
            total_count, items = query_func(
                offset=(page - 1) * per_page,
                limit=per_page,
                **query_kwargs
            )
            
            # 计算分页信息
            total_pages = (total_count + per_page - 1) // per_page
            has_next = page < total_pages
            has_prev = page > 1
            
            return builder.success(
                operation=OperationType.QUERY,
                message=f"返回第 {page} 页结果，共 {len(items)} 项",
                data={
                    "items": items,
                    "count": len(items),
                    "total_count": total_count
                },
                pagination={
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                    "total_count": total_count,
                    "has_next": has_next,
                    "has_prev": has_prev
                }
            ).to_dict()
            
        except Exception as e:
            return builder.error(
                operation=OperationType.QUERY,
                message="查询失败",
                error_details=str(e)
            ).to_dict()


# === 装饰器工具 ===

def standard_mcp_tool(
    operation: OperationType,
    success_message: str = "操作成功",
    tool_name: Optional[str] = None
):
    """标准MCP工具装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = tool_name or func.__name__
            builder = MCPResponseBuilder(name)
            
            try:
                result = func(*args, **kwargs)
                
                # 处理不同类型的返回值
                if isinstance(result, dict):
                    # 检查是否已经是标准格式
                    if "status" in result and "operation" in result:
                        return result
                    
                    # 检查是否是旧格式
                    if "status" in result or "error" in result:
                        return legacy_to_standard(result, name, operation)
                
                # 简单返回值包装
                return builder.success(
                    operation=operation,
                    message=success_message,
                    data=result if result is not None else {}
                ).to_dict()
                
            except Exception as e:
                return builder.error(
                    operation=operation,
                    message=f"操作失败: {type(e).__name__}",
                    error_details=str(e)
                ).to_dict()
        
        return wrapper
    return decorator


# === 示例实现 ===

class ExampleFileTool(FileSystemTool):
    """文件工具示例实现"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        super().__init__("example_file_tool", base_dir)
    
    def get_operation_type(self) -> OperationType:
        return OperationType.READ
    
    @standard_mcp_tool(OperationType.READ, "成功读取文件")
    def read_file(self, file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """读取文件示例"""
        path = self.resolve_path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        content = path.read_text(encoding=encoding)
        
        return {
            "content": content,
            "size": len(content),
            "encoding": encoding,
            "line_count": len(content.splitlines())
        }
    
    def create_file(self, file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """创建文件示例"""
        builder = self.create_response_builder()
        path = self.resolve_path(file_path)
        
        # 确保父目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        path.write_text(content, encoding=encoding)
        
        # 创建文件信息
        file_info = self.create_file_info_from_path(path, "文本文件")
        
        return builder.success(
            operation=OperationType.CREATE,
            message="成功创建文件",
            data={"path": str(path), "size": len(content)},
            new_files=[file_info]
        ).to_dict()


if __name__ == "__main__":
    # 示例用法
    tool = ExampleFileTool(Path("/tmp/mcp_test"))
    
    # 创建文件
    result = tool.create_file("test.txt", "Hello, World!")
    print("创建文件结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    
    # 读取文件
    result = tool.read_file("test.txt")
    print("读取文件结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))