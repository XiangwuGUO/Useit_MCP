"""
Filesystem FastMCP Server (sandboxed) - 标准化版本

功能：
- 列目录、查询文件信息、读写文本、读写二进制（以 base64 返回）、创建目录、复制/移动/删除文件
- 提取 Office 文本：PDF / DOCX / PPTX
- 使用标准化MCP响应格式

依赖（按需可选安装）：
- PDF:  "pypdf"
- DOCX: "python-docx"  
- PPTX: "python-pptx"

运行（开发调试，自动装依赖）：
    uv run mcp dev examples/servers/filesystem/server.py \
        --with pypdf python-docx python-pptx

生产建议：使用 streamable-http
    uv run examples/servers/filesystem/server.py

环境变量：
- FILESYSTEM_BASE_DIR：沙箱根目录（默认：用户家目录）
"""

from __future__ import annotations

import base64
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# 导入标准化组件
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from core import (
    MCPResponseBuilder, OperationType, ResponseStatus, create_file_info,
    FileSystemTool, quick_success, quick_error
)

# -----------------------------------------------------------------------------
# 配置与沙箱  
# -----------------------------------------------------------------------------

def load_resource_config() -> dict:
    """加载资源配置文件"""
    config_file = "resource_config.json"
    default_config = {
        "base_directory": "./mcp_resources",
        "auto_create_dirs": True,
        "max_file_size_mb": 100
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                default_config.update(config)
        except Exception:
            pass
    
    return default_config

def get_base_dir() -> Path:
    """获取基础目录，优先使用MCP_BASE_DIR环境变量，然后配置文件，最后默认值"""
    # 1. 优先使用MCP_BASE_DIR环境变量（由launcher设置）
    mcp_base = os.environ.get("MCP_BASE_DIR")
    if mcp_base:
        try:
            p = Path(mcp_base).expanduser().resolve()
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    
    # 2. 尝试从配置文件获取
    try:
        config = load_resource_config()
        config_path = config.get("base_directory")
        if config_path:
            p = Path(config_path).expanduser().resolve()
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
            return p
    except Exception:
        pass
    
    # 3. 尝试从FILESYSTEM_BASE_DIR环境变量获取
    env_path = os.environ.get("FILESYSTEM_BASE_DIR")
    if env_path:
        try:
            p = Path(env_path).expanduser().resolve()
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    
    # 4. 默认使用当前目录下的mcp_workspace
    default_path = Path(os.getcwd()) / "mcp_workspace"
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path.resolve()


BASE_DIR: Path = get_base_dir()
RESOURCE_CONFIG = load_resource_config()

def resolve_in_sandbox(user_path: str, session_id: str = None) -> Path:
    """将用户提供路径解析到沙箱内，拒绝越权路径。

    - 支持绝对/相对路径；相对路径相对于BASE_DIR
    - 解析后必须保证在BASE_DIR沙箱目录内
    - session_id参数保留兼容性但不影响路径解析
    """
    # 直接使用BASE_DIR作为沙箱根目录
    sandbox_root = BASE_DIR
    
    candidate = Path(user_path)
    if not candidate.is_absolute():
        candidate = sandbox_root / candidate
    abs_path = candidate.expanduser().resolve()
    
    try:
        # 允许目标等于sandbox_root本身或其子路径
        if abs_path == sandbox_root or sandbox_root in abs_path.parents:
            return abs_path
    except Exception:
        pass
    raise ValueError(f"Path out of sandbox: {abs_path} (sandbox: {sandbox_root})")

# -----------------------------------------------------------------------------
# 数据模型（结构化输出）
# -----------------------------------------------------------------------------

class FileInfo(BaseModel):
    path: str = Field(description="绝对路径")
    relative: str = Field(description="相对 BASE_DIR 的路径")
    name: str
    is_dir: bool
    size: int | None = None
    mtime: str | None = None


class ListDirRequest(BaseModel):
    path: str = Field(description="目录路径（可相对沙箱）")
    recursive: bool = Field(default=False)
    pattern: str | None = Field(default=None, description="glob 过滤，如 *.txt")
    files_only: bool = Field(default=True)
    session_id: str | None = Field(default=None, description="会话ID，用于确定沙箱目录")


class ListDirResult(BaseModel):
    base_dir: str
    entries: list[FileInfo]


class ReadTextRequest(BaseModel):
    path: str
    encoding: str = Field(default="utf-8")
    session_id: str | None = Field(default=None, description="会话ID")


class WriteTextRequest(BaseModel):
    path: str
    content: str
    encoding: str = Field(default="utf-8")
    append: bool = Field(default=False)
    session_id: str | None = Field(default=None, description="会话ID")


class ReadBinaryRequest(BaseModel):
    path: str
    max_bytes: int | None = Field(default=None, description="限制最大读取字节，None 表示不限")
    session_id: str | None = Field(default=None, description="会话ID")


class ReadBinaryResult(BaseModel):
    base64: str
    size: int
    mime_type: str = Field(default="application/octet-stream")


class WriteBinaryRequest(BaseModel):
    path: str
    base64: str
    overwrite: bool = Field(default=True)
    session_id: str | None = Field(default=None, description="会话ID")


class MoveCopyRequest(BaseModel):
    src: str
    dst: str
    overwrite: bool = Field(default=False)
    session_id: str | None = Field(default=None, description="会话ID")


class MkdirRequest(BaseModel):
    path: str
    parents: bool = Field(default=True)
    exist_ok: bool = Field(default=True)
    session_id: str | None = Field(default=None, description="会话ID")


class DeleteRequest(BaseModel):
    path: str
    recursive: bool = Field(default=False)
    session_id: str | None = Field(default=None, description="会话ID")


class OfficeReadRequest(BaseModel):
    path: str
    session_id: str | None = Field(default=None, description="会话ID")


def to_file_info(p: Path, sandbox_root: Path = None) -> FileInfo:
    stat = p.stat()
    if sandbox_root is None:
        sandbox_root = BASE_DIR
    
    # 计算相对路径
    try:
        if p == sandbox_root:
            rel = Path(".")
        else:
            rel = p.relative_to(sandbox_root)
    except ValueError:
        # 如果路径不在sandbox_root下，尝试相对于BASE_DIR
        try:
            if p == BASE_DIR:
                rel = Path(".")
            else:
                rel = p.relative_to(BASE_DIR)
        except ValueError:
            rel = Path(".")
    
    return FileInfo(
        path=str(p),
        relative=str(rel),
        name=p.name,
        is_dir=p.is_dir(),
        size=None if p.is_dir() else int(stat.st_size),
        mtime=datetime.fromtimestamp(stat.st_mtime).isoformat(),
    )

# -----------------------------------------------------------------------------
# 服务器与工具
# -----------------------------------------------------------------------------

# 创建MCP服务器和工具实例
mcp = FastMCP(
    "filesystem",
    title="标准化文件系统服务", 
    description="提供标准化响应格式的文件系统操作功能，包括文件读写、目录管理等",
    port=8003
)

# 创建文件系统工具实例
fs_tool = FileSystemTool("filesystem", BASE_DIR)

@mcp.tool()
def get_base(session_id: str = None) -> Dict[str, Any]:
    """获取沙箱根目录。"""
    return quick_success(
        tool_name="get_base",
        operation=OperationType.QUERY,
        message="成功获取基础目录",
        data={"base_directory": str(BASE_DIR)}
    )

# 专用于直接调用的路径列表函数 - 不向AI提供
# 注意：这个函数故意不使用 @mcp.tool() 装饰器，只能通过直接HTTP调用
def list_all_paths(session_id: str = None) -> Dict[str, Any]:
    """获取base_dir下所有文件和文件夹的绝对路径列表。
    
    这是一个专门用于直接工具调用的函数，不会被AI智能任务执行器调用。
    返回base_dir及其子目录下所有文件和文件夹的绝对路径。
    路径格式会根据操作系统自动调整（Windows/Linux）。
    
    重要：此函数故意不注册为MCP工具，只能通过客户端直接调用接口使用。
    """
    builder = MCPResponseBuilder("list_all_paths")
    
    try:
        paths = []
        root = BASE_DIR
        
        # 添加根目录本身
        paths.append(str(root))
        
        # 遍历所有子项（文件和文件夹）
        for path in root.rglob("*"):
            # 忽略.useit文件夹及其内容
            if ".useit" not in path.parts:
                paths.append(str(path))
        
        # 排序：目录在前，文件在后，同类型按名称排序
        def sort_key(p: str) -> tuple[bool, str]:
            path_obj = Path(p)
            return (not path_obj.is_dir(), p.lower())
        
        paths.sort(key=sort_key)
        
        return builder.success(
            operation=OperationType.QUERY,
            message=f"成功列出 {len(paths)} 个路径",
            data={"paths": paths, "total": len(paths)}
        ).to_dict()
    
    except Exception as e:
        return builder.error(
            operation=OperationType.QUERY,
            message="列出路径失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def list_dir(req: ListDirRequest) -> Dict[str, Any]:
    """列目录（支持递归与模式）。
    
    默认行为：如果路径为"."或空，则列出BASE_DIR下所有文件和文件夹，
    包括子目录，但忽略.useit文件夹，最多返回300个条目。
    """
    builder = MCPResponseBuilder("list_dir")
    
    try:
        # 如果请求路径为"."或空，使用BASE_DIR并启用递归搜索
        if req.path in (".", "", "/"):
            root = BASE_DIR
            use_recursive = True
            max_items = 300
        else:
            root = resolve_in_sandbox(req.path, req.session_id)
            use_recursive = req.recursive
            max_items = None
        
        if not root.exists():
            return builder.error(
                operation=OperationType.QUERY,
                message="目录不存在",
                error_details=f"目录 '{req.path}' 不存在"
            ).to_dict()
            
        if not root.is_dir():
            return builder.error(
                operation=OperationType.QUERY,
                message="不是目录",
                error_details=f"'{req.path}' 不是一个目录"
            ).to_dict()

        def iter_paths() -> list[Path]:
            paths = []
            count = 0
            
            if req.pattern:
                if use_recursive:
                    pattern_paths = root.rglob(req.pattern)
                else:
                    pattern_paths = root.glob(req.pattern)
            else:
                if use_recursive:
                    pattern_paths = root.rglob("*")
                else:
                    pattern_paths = root.glob("*")
            
            for p in pattern_paths:
                # 忽略.useit文件夹及其内容
                if ".useit" in p.parts:
                    continue
                    
                paths.append(p)
                count += 1
                
                # 如果设置了最大数量限制，则停止收集
                if max_items and count >= max_items:
                    break
            
            return paths

        paths = iter_paths()
        if req.files_only:
            paths = [p for p in paths if p.is_file()]

        # 使用BASE_DIR作为sandbox_root
        entries = [to_file_info(p, BASE_DIR) for p in paths]
        
        # 按类型和名称排序：先目录后文件，同类型按名称排序
        entries.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        
        result_data = ListDirResult(base_dir=str(BASE_DIR), entries=entries)
        
        # 统计信息
        file_count = sum(1 for e in entries if not e.is_dir)
        dir_count = sum(1 for e in entries if e.is_dir)
        total_size = sum(e.size or 0 for e in entries if not e.is_dir)
        
        return builder.success(
            operation=OperationType.QUERY,
            message=f"成功列出目录 '{req.path}'，共 {len(entries)} 个条目（{file_count} 个文件，{dir_count} 个目录）",
            data={
                **result_data.dict(),
                "summary": {
                    "total_entries": len(entries),
                    "file_count": file_count,
                    "directory_count": dir_count,
                    "total_size": total_size,
                    "search_params": {
                        "recursive": use_recursive,
                        "pattern": req.pattern,
                        "files_only": req.files_only
                    }
                }
            }
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.QUERY,
            message="列目录失败",
            error_details=str(e)
        ).to_dict()



@mcp.tool()
def read_text(req: ReadTextRequest) -> Dict[str, Any]:
    """读取文本文件。"""
    builder = MCPResponseBuilder("read_text")
    
    try:
        p = resolve_in_sandbox(req.path, req.session_id)
        if not p.exists() or not p.is_file():
            return builder.error(
                operation=OperationType.READ,
                message="文件不存在或不是文件",
                error_details=f"路径 '{req.path}' 不是一个有效文件"
            ).to_dict()
            
        content = p.read_text(encoding=req.encoding)
        
        content_bytes = content.encode(req.encoding)
        return builder.success(
            operation=OperationType.READ,
            message=f"成功读取文件 '{req.path}'",
            data={
                "content": content,
                "size": len(content_bytes),
                "encoding": req.encoding,
                "line_count": len(content.splitlines()),
                "character_count": len(content)
            }
        ).to_dict()
        
    except UnicodeDecodeError as e:
        return builder.error(
            operation=OperationType.READ,
            message="文件编码错误",
            error_details=f"无法使用 {req.encoding} 编码读取文件: {str(e)}"
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.READ,
            message="读取文件失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def write_text(req: WriteTextRequest) -> Dict[str, Any]:
    """写入文本文件（可 append）。"""
    builder = MCPResponseBuilder("write_text")
    
    try:
        p = resolve_in_sandbox(req.path, req.session_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        
        is_new_file = not p.exists()
        if req.append and p.exists():
            with p.open("a", encoding=req.encoding) as f:
                f.write(req.content)
            operation_type = OperationType.UPDATE
            message = f"成功追加内容到文件 '{req.path}'"
        else:
            p.write_text(req.content, encoding=req.encoding)
            operation_type = OperationType.CREATE if is_new_file else OperationType.UPDATE
            message = f"成功{'创建' if is_new_file else '更新'}文件 '{req.path}'"
        
        # 创建文件信息
        file_info = fs_tool.create_file_info_from_path(
            p, 
            "文本文件" if is_new_file else "更新的文本文件",
            encoding=req.encoding,
            operation="append" if req.append else "write"
        )
        
        return builder.success(
            operation=operation_type,
            message=message,
            data={
                "path": req.path,
                "size": p.stat().st_size,
                "encoding": req.encoding,
                "is_new_file": is_new_file,
                "append_mode": req.append
            },
            new_files=[file_info] if is_new_file else None,
            modified_files=[file_info] if not is_new_file else None
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.WRITE,
            message="写入文件失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def read_binary(req: ReadBinaryRequest) -> Dict[str, Any]:
    """读取二进制文件，返回 base64。"""
    builder = MCPResponseBuilder("read_binary")
    
    try:
        p = resolve_in_sandbox(req.path, req.session_id)
        if not p.exists() or not p.is_file():
            return builder.error(
                operation=OperationType.READ,
                message="文件不存在或不是文件",
                error_details=f"路径 '{req.path}' 不是一个有效文件"
            ).to_dict()
            
        data = p.read_bytes()
        if req.max_bytes is not None and req.max_bytes >= 0:
            data = data[:req.max_bytes]
            
        result = ReadBinaryResult(
            base64=base64.b64encode(data).decode("ascii"), 
            size=len(data)
        )
        
        return builder.success(
            operation=OperationType.READ,
            message=f"成功读取二进制文件 '{req.path}'",
            data=result.dict()
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.READ,
            message="读取二进制文件失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def write_binary(req: WriteBinaryRequest) -> Dict[str, Any]:
    """写入二进制文件（输入 base64）。"""
    builder = MCPResponseBuilder("write_binary")
    
    try:
        p = resolve_in_sandbox(req.path, req.session_id)
        
        is_new_file = not p.exists()
        if p.exists() and not req.overwrite:
            return builder.error(
                operation=OperationType.WRITE,
                message="文件已存在",
                error_details=f"文件 '{req.path}' 已存在且未设置覆盖"
            ).to_dict()
        
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        
        # 判断文件类型
        file_ext = p.suffix.lower()
        file_type_map = {
            '.jpg': 'JPEG图片', '.jpeg': 'JPEG图片', '.png': 'PNG图片', 
            '.gif': 'GIF图片', '.pdf': 'PDF文档', '.zip': '压缩文件',
            '.wav': '音频文件', '.mp3': 'MP3音频'
        }
        file_description = file_type_map.get(file_ext, '二进制文件')
        
        # 创建文件信息
        file_info = fs_tool.create_file_info_from_path(
            p, 
            file_description + ("" if is_new_file else " (已更新)"),
            operation_type="binary_write"
        )
        
        operation_type = OperationType.CREATE if is_new_file else OperationType.UPDATE
        message = f"成功{'创建' if is_new_file else '更新'}二进制文件 '{req.path}'"
        
        return builder.success(
            operation=operation_type,
            message=message,
            data={
                "path": req.path,
                "size": len(data),
                "is_new_file": is_new_file
            },
            new_files=[file_info] if is_new_file else None,
            modified_files=[file_info] if not is_new_file else None
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.WRITE,
            message="写入二进制文件失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def mkdir(req: MkdirRequest) -> Dict[str, Any]:
    """创建目录。"""
    builder = MCPResponseBuilder("mkdir")
    
    try:
        p = resolve_in_sandbox(req.path, req.session_id)
        is_new_dir = not p.exists()
        p.mkdir(parents=req.parents, exist_ok=req.exist_ok)
        
        if is_new_dir:
            # 创建目录信息
            file_info = fs_tool.create_file_info_from_path(
                p, 
                "目录",
                parents_created=req.parents
            )
            
            return builder.success(
                operation=OperationType.CREATE,
                message=f"成功创建目录 '{req.path}'",
                data={
                    "path": req.path,
                    "parents_created": req.parents
                },
                new_files=[file_info]
            ).to_dict()
        else:
            return builder.success(
                operation=OperationType.QUERY,
                message=f"目录 '{req.path}' 已存在",
                data={
                    "path": req.path,
                    "already_exists": True
                }
            ).to_dict()
            
    except FileExistsError:
        return builder.error(
            operation=OperationType.CREATE,
            message="目录已存在",
            error_details=f"目录 '{req.path}' 已存在且 exist_ok=False"
        ).to_dict()
    
    except Exception as e:
        return builder.error(
            operation=OperationType.CREATE,
            message="创建目录失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def move(req: MoveCopyRequest) -> Dict[str, Any]:
    """移动文件/目录。"""
    builder = MCPResponseBuilder("move")
    
    try:
        src = resolve_in_sandbox(req.src, req.session_id)
        dst = resolve_in_sandbox(req.dst, req.session_id)
        
        if not src.exists():
            return builder.error(
                operation=OperationType.UPDATE,
                message="源文件不存在",
                error_details=f"源路径 '{req.src}' 不存在"
            ).to_dict()
        
        # 检查目标是否已存在
        dst_existed = dst.exists()
        is_src_dir = src.is_dir()
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if req.overwrite:
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            else:
                return builder.error(
                    operation=OperationType.UPDATE,
                    message="目标已存在",
                    error_details=f"目标 '{req.dst}' 已存在，使用 overwrite=True 覆盖"
                ).to_dict()
        
        shutil.move(str(src), str(dst))
        
        # 创建文件信息
        file_info = fs_tool.create_file_info_from_path(
            dst,
            f"移动的{'目录' if is_src_dir else '文件'}",
            source=req.src,
            move_operation=True
        )
        
        return builder.success(
            operation=OperationType.UPDATE,
            message=f"成功移动{'目录' if is_src_dir else '文件'} '{req.src}' 到 '{req.dst}'",
            data={
                "source": req.src,
                "destination": req.dst,
                "type": "目录" if is_src_dir else "文件",
                "overwritten": dst_existed
            },
            new_files=[file_info] if not dst_existed else None,
            modified_files=[file_info] if dst_existed else None
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.UPDATE,
            message="移动失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def copy(req: MoveCopyRequest) -> Dict[str, Any]:
    """复制文件/目录。"""
    builder = MCPResponseBuilder("copy")
    
    try:
        src = resolve_in_sandbox(req.src, req.session_id)
        dst = resolve_in_sandbox(req.dst, req.session_id)
        
        if not src.exists():
            return builder.error(
                operation=OperationType.CREATE,
                message="源文件不存在",
                error_details=f"源路径 '{req.src}' 不存在"
            ).to_dict()
        
        # 检查目标是否已存在以及源的类型
        dst_existed = dst.exists()
        is_src_dir = src.is_dir()
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not req.overwrite:
            return builder.error(
                operation=OperationType.CREATE,
                message="目标已存在",
                error_details=f"目标 '{req.dst}' 已存在，使用 overwrite=True 覆盖"
            ).to_dict()
        
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        
        # 创建文件信息
        file_info = fs_tool.create_file_info_from_path(
            dst,
            f"复制的{'目录' if is_src_dir else '文件'}",
            source=req.src,
            copy_operation=True
        )
        
        return builder.success(
            operation=OperationType.CREATE,
            message=f"成功复制{'目录' if is_src_dir else '文件'} '{req.src}' 到 '{req.dst}'",
            data={
                "source": req.src,
                "destination": req.dst,
                "type": "目录" if is_src_dir else "文件",
                "overwritten": dst_existed
            },
            new_files=[file_info]
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.CREATE,
            message="复制失败",
            error_details=str(e)
        ).to_dict()

@mcp.tool()
def delete(req: DeleteRequest) -> Dict[str, Any]:
    """删除文件/目录。"""
    builder = MCPResponseBuilder("delete")
    
    try:
        p = resolve_in_sandbox(req.path, req.session_id)
        
        if not p.exists():
            return builder.success(
                operation=OperationType.DELETE,
                message=f"目标 '{req.path}' 不存在，无需删除",
                data={
                    "path": req.path,
                    "existed": False
                }
            ).to_dict()
        
        # 记录删除的信息
        is_directory = p.is_dir()
        size = p.stat().st_size if p.is_file() else None
        
        # 执行删除
        if p.is_dir():
            if req.recursive:
                shutil.rmtree(p)
                item_type = "目录"
            else:
                p.rmdir()  # 只能删除空目录
                item_type = "空目录"
        else:
            p.unlink()
            item_type = "文件"
        
        return builder.success(
            operation=OperationType.DELETE,
            message=f"成功删除{item_type} '{req.path}'",
            data={
                "path": req.path,
                "type": item_type,
                "was_directory": is_directory,
                "size": size,
                "recursive": req.recursive
            },
            deleted_files=[fs_tool.get_relative_path(p)]
        ).to_dict()
        
    except OSError as e:
        return builder.error(
            operation=OperationType.DELETE,
            message="删除失败",
            error_details=f"无法删除 '{req.path}': {str(e)}"
        ).to_dict()
    
    except Exception as e:
        return builder.error(
            operation=OperationType.DELETE,
            message="删除操作失败",
            error_details=str(e)
        ).to_dict()

# ----------------------------- Office 文本提取 -------------------------------

def _read_pdf_text(p: Path) -> str:
    try:
        import pypdf  # type: ignore
    except Exception as e:  # pragma: no cover - 仅在未安装时触发
        raise RuntimeError("缺少依赖 pypdf，请使用: uv run ... --with pypdf") from e

    reader = pypdf.PdfReader(str(p))
    texts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t:
            texts.append(t)
    return "\n\n".join(texts)


def _read_docx_text(p: Path) -> str:
    try:
        import docx  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("缺少依赖 python-docx，请使用: uv run ... --with python-docx") from e

    d = docx.Document(str(p))
    parts: list[str] = []
    for para in d.paragraphs:
        if para.text:
            parts.append(para.text)
    return "\n".join(parts)


def _read_pptx_text(p: Path) -> str:
    try:
        from pptx import Presentation  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("缺少依赖 python-pptx，请使用: uv run ... --with python-pptx") from e

    prs = Presentation(str(p))
    texts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            txt = None
            if hasattr(shape, "text"):
                txt = getattr(shape, "text")
            elif hasattr(shape, "has_text_frame") and getattr(shape, "has_text_frame"):
                tf = getattr(shape, "text_frame", None)
                if tf and hasattr(tf, "text"):
                    txt = tf.text
            if txt:
                texts.append(str(txt))
    return "\n\n".join(texts)


@mcp.tool()
def read_office_text(req: OfficeReadRequest) -> Dict[str, Any]:
    """读取 Office 文本（PDF/DOCX/PPTX）。"""
    builder = MCPResponseBuilder("read_office_text")
    
    try:
        p = resolve_in_sandbox(req.path, req.session_id)
        if not p.exists() or not p.is_file():
            return builder.error(
                operation=OperationType.READ,
                message="文件不存在或不是文件",
                error_details=f"路径 '{req.path}' 不是一个有效文件"
            ).to_dict()
            
        ext = p.suffix.lower()
        if ext == ".pdf":
            text = _read_pdf_text(p)
            doc_type = "PDF文档"
        elif ext == ".docx":
            text = _read_docx_text(p)
            doc_type = "Word文档"
        elif ext == ".pptx":
            text = _read_pptx_text(p)
            doc_type = "PowerPoint文档"
        else:
            return builder.error(
                operation=OperationType.READ,
                message="不支持的文件格式",
                error_details="仅支持 .pdf/.docx/.pptx 文件"
            ).to_dict()
        
        return builder.success(
            operation=OperationType.PROCESS,
            message=f"成功提取{doc_type}文本内容",
            data={
                "path": req.path,
                "text": text,
                "document_type": doc_type,
                "text_length": len(text),
                "line_count": len(text.splitlines())
            }
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.PROCESS,
            message="提取文本失败",
            error_details=str(e)
        ).to_dict()

# 保留同步功能但简化，因为它更多是系统功能而非核心MCP功能
# 这里只保留简化版本，重点在于展示如何将复杂功能适配到标准格式

# 简化的同步请求和结果模型
class SyncRequest(BaseModel):
    vm_id: str = Field(description="虚拟机ID")
    session_id: str = Field(description="会话ID") 
    target_base_path: str = Field(description="目标基础路径")

class SyncResult(BaseModel):
    success: bool
    message: str
    synced_files: List[str] = Field(default_factory=list)

@mcp.tool()
def sync_files_to_target(req: SyncRequest) -> Dict[str, Any]:
    """将本地BASE_DIR中的文件同步到目标路径。"""
    builder = MCPResponseBuilder("sync_files_to_target")
    
    try:
        # 这里是简化版本，实际可以根据需要扩展
        target_base_path = Path(req.target_base_path) / f"{req.vm_id}_{req.session_id}"
        
        # 创建目标目录
        target_base_path.mkdir(parents=True, exist_ok=True)
        
        # 扫描本地文件 - 简化版本只同步文本文件
        synced_files = []
        text_extensions = {'.txt', '.md', '.json', '.yaml', '.yml'}
        
        for file_path in BASE_DIR.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in text_extensions:
                try:
                    relative_path = file_path.relative_to(BASE_DIR)
                    target_file_path = target_base_path / relative_path
                    
                    # 确保目标父目录存在
                    target_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 复制文件
                    shutil.copy2(file_path, target_file_path)
                    synced_files.append(str(relative_path))
                    
                    if len(synced_files) >= 50:  # 限制同步数量
                        break
                        
                except Exception:
                    continue
        
        result = SyncResult(
            success=True,
            message=f"成功同步 {len(synced_files)} 个文件到 {target_base_path}",
            synced_files=synced_files
        )
        
        return builder.success(
            operation=OperationType.SYSTEM,
            message=result.message,
            data=result.dict()
        ).to_dict()
        
    except Exception as e:
        return builder.error(
            operation=OperationType.SYSTEM,
            message="同步失败",
            error_details=str(e)
        ).to_dict()

# -----------------------------------------------------------------------------
# 启动
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # 保持兼容性，使用原有启动方式
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from server_base import start_mcp_server
    
    # 添加自定义HTTP端点 - 正确的异步版本
    @mcp.custom_route("/direct/list-all-paths", ["GET"])
    async def http_list_all_paths(request):
        """HTTP端点：获取所有路径列表 - 专用于直接调用"""
        from fastapi.responses import JSONResponse
        
        try:
            # 调用完整的list_all_paths函数
            result = list_all_paths()
            
            # 简化返回格式，只返回必要的字段以确保兼容性
            if isinstance(result, dict) and result.get('status') == 'success':
                response_data = {
                    "success": True,
                    "data": result.get('data', {}),
                    "message": result.get('message', '')
                }
            else:
                response_data = {
                    "success": False,
                    "data": {},
                    "message": "获取路径列表失败"
                }
                
            return JSONResponse(content=response_data)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            # 返回JSON格式的错误
            error_response = {
                "success": False,
                "data": {},
                "message": f"获取路径列表失败: {str(e)}"
            }
            return JSONResponse(content=error_response, status_code=500)
    
    print(f"🚀 启动标准化文件系统服务器")
    print(f"📁 基础目录: {BASE_DIR}")
    print(f"🌐 端口: 8003")
    print(f"📋 使用标准响应格式")
    print(f"🔗 HTTP端点: /direct/list-all-paths (专用于直接调用)")
    
    start_mcp_server(mcp, 8003, "filesystem")