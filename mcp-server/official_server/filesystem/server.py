"""
Filesystem FastMCP Server (sandboxed)

功能：
- 列目录、查询文件信息、读写文本、读写二进制（以 base64 返回）、创建目录、复制/移动/删除文件
- 提取 Office 文本：PDF / DOCX / PPTX

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
import requests
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Dict, List, Tuple

from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from base_server import StandardMCPServer, ServerConfigs


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


class StatRequest(BaseModel):
    path: str
    session_id: str | None = Field(default=None, description="会话ID")


class OfficeReadRequest(BaseModel):
    path: str
    session_id: str | None = Field(default=None, description="会话ID")


class SyncRequest(BaseModel):
    vm_id: str = Field(description="虚拟机ID")
    session_id: str = Field(description="会话ID")
    target_base_path: str = Field(description="目标基础路径，如 /mnt/efs/data/useit/users_workspace")
    force_sync: bool = Field(default=False, description="强制同步所有文件，忽略哈希比较")
    dry_run: bool = Field(default=False, description="预演模式，只列出待同步文件不实际同步")
    sync_strategy: str = Field(default="size_hash", description="同步策略: hash(哈希比较), size_hash(大小+哈希), etag(ETag)")
    chunk_size: int = Field(default=8192, description="文件读取块大小，用于哈希计算")


class SyncResult(BaseModel):
    success: bool
    message: str
    synced_files: List[str] = Field(default_factory=list)
    skipped_files: List[str] = Field(default_factory=list)
    error_files: List[Dict[str, str]] = Field(default_factory=list)
    total_size: int = 0
    sync_summary: Dict[str, Any] = Field(default_factory=dict)


def to_file_info(p: Path, sandbox_root: Path = None) -> FileInfo:
    stat = p.stat()
    if sandbox_root is None:
        sandbox_root = BASE_DIR
    
    # 计算相对路径
    try:
        rel = p.relative_to(sandbox_root) if p != sandbox_root and sandbox_root in p.parents else Path(".")
    except ValueError:
        # 如果路径不在sandbox_root下，尝试相对于BASE_DIR
        try:
            rel = p.relative_to(BASE_DIR) if p != BASE_DIR and BASE_DIR in p.parents else Path(".")
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

# 使用原有架构，直接创建FastMCP实例
mcp = FastMCP(
    "filesystem",
    title="文件系统服务", 
    description="提供文件系统操作功能，包括文件读写、目录管理等",
    port=8003
)
def get_base(session_id: str = None) -> str:
    """获取沙箱根目录。"""
    return str(BASE_DIR)


@mcp.tool()
def list_all_paths(session_id: str = None) -> List[str]:
    """获取base_dir下所有文件和文件夹的绝对路径列表。
    
    返回base_dir及其子目录下所有文件和文件夹的绝对路径。
    路径格式会根据操作系统自动调整（Windows/Linux）。
    """
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
        def sort_key(p):
            path_obj = Path(p)
            return (not path_obj.is_dir(), p.lower())
        
        paths.sort(key=sort_key)
        return paths
    
    except Exception as e:
        raise RuntimeError(f"列出路径失败: {e}")


@mcp.tool()
def list_dir(req: ListDirRequest) -> ListDirResult:
    """列目录（支持递归与模式）。
    
    默认行为：如果路径为"."或空，则列出BASE_DIR下所有文件和文件夹，
    包括子目录，但忽略.useit文件夹，最多返回300个条目。
    """
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
        raise FileNotFoundError(f"Not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

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
    
    return ListDirResult(base_dir=str(BASE_DIR), entries=entries)


@mcp.tool()
def stat(req: StatRequest) -> FileInfo:
    """查询文件/目录信息。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {p}")
    return to_file_info(p, BASE_DIR)


@mcp.tool()
def read_text(req: ReadTextRequest) -> str:
    """读取文本文件。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")
    return p.read_text(encoding=req.encoding)


@mcp.tool()
def write_text(req: WriteTextRequest) -> dict[str, str]:
    """写入文本文件（可 append）。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    base_path = BASE_DIR
    p.parent.mkdir(parents=True, exist_ok=True)
    
    is_new_file = not p.exists()
    if req.append and p.exists():
        with p.open("a", encoding=req.encoding) as f:
            f.write(req.content)
    else:
        p.write_text(req.content, encoding=req.encoding)
    
    # 构建相对路径
    try:
        relative_path = p.relative_to(base_path)
    except ValueError:
        relative_path = p
    
    result = {"status": "ok", "path": str(p)}
    
    # 如果是新文件或写入操作，添加文件信息
    if is_new_file or not req.append:
        result["new_files"] = {
            str(relative_path): "文本文件" if is_new_file else "更新的文本文件"
        }
    
    return result


@mcp.tool()
def read_binary(req: ReadBinaryRequest) -> ReadBinaryResult:
    """读取二进制文件，返回 base64。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")
    data = p.read_bytes()
    if req.max_bytes is not None and req.max_bytes >= 0:
        data = data[: req.max_bytes]
    return ReadBinaryResult(base64=base64.b64encode(data).decode("ascii"), size=len(data))


@mcp.tool()
def write_binary(req: WriteBinaryRequest) -> dict[str, str]:
    """写入二进制文件（输入 base64）。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    base_path = BASE_DIR
    
    is_new_file = not p.exists()
    if p.exists() and not req.overwrite:
        raise FileExistsError(f"Exists: {p}")
    
    p.parent.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(req.base64)
    p.write_bytes(data)
    
    # 构建相对路径
    try:
        relative_path = p.relative_to(base_path)
    except ValueError:
        relative_path = p
    
    # 判断文件类型
    file_ext = p.suffix.lower()
    file_type_map = {
        '.jpg': 'JPEG图片', '.jpeg': 'JPEG图片', '.png': 'PNG图片', 
        '.gif': 'GIF图片', '.pdf': 'PDF文档', '.zip': '压缩文件',
        '.wav': '音频文件', '.mp3': 'MP3音频'
    }
    file_description = file_type_map.get(file_ext, '二进制文件')
    
    result = {"status": "ok", "path": str(p), "size": str(len(data))}
    result["new_files"] = {
        str(relative_path): file_description + ("" if is_new_file else " (已更新)")
    }
    
    return result


@mcp.tool()
def mkdir(req: MkdirRequest) -> dict[str, str]:
    """创建目录。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    is_new_dir = not p.exists()
    p.mkdir(parents=req.parents, exist_ok=req.exist_ok)
    
    # 构建相对路径
    try:
        relative_path = p.relative_to(BASE_DIR)
    except ValueError:
        relative_path = p
    
    result = {"status": "ok", "path": str(p)}
    
    # 如果创建了新目录，添加到new_files中
    if is_new_dir:
        result["new_files"] = {
            str(relative_path): "目录"
        }
    
    return result


@mcp.tool()
def move(req: MoveCopyRequest) -> dict[str, str]:
    """移动文件/目录。"""
    src = resolve_in_sandbox(req.src, req.session_id)
    dst = resolve_in_sandbox(req.dst, req.session_id)
    if not src.exists():
        raise FileNotFoundError(f"Not found: {src}")
    
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
            raise FileExistsError(f"Exists: {dst}")
    
    shutil.move(str(src), str(dst))
    
    # 构建相对路径
    try:
        relative_dst = dst.relative_to(BASE_DIR)
    except ValueError:
        relative_dst = dst
    
    result = {"status": "ok", "src": str(src), "dst": str(dst)}
    
    # 移动操作在目标位置创建了新文件/目录
    if not dst_existed or req.overwrite:
        result["new_files"] = {
            str(relative_dst): "目录" if is_src_dir else "文件"
        }
    
    return result


@mcp.tool()
def copy(req: MoveCopyRequest) -> dict[str, str]:
    """复制文件/目录。"""
    src = resolve_in_sandbox(req.src, req.session_id)
    dst = resolve_in_sandbox(req.dst, req.session_id)
    if not src.exists():
        raise FileNotFoundError(f"Not found: {src}")
    
    # 检查目标是否已存在以及源的类型
    dst_existed = dst.exists()
    is_src_dir = src.is_dir()
    
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not req.overwrite:
        raise FileExistsError(f"Exists: {dst}")
    
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    
    # 构建相对路径
    try:
        relative_dst = dst.relative_to(BASE_DIR)
    except ValueError:
        relative_dst = dst
    
    result = {"status": "ok", "src": str(src), "dst": str(dst)}
    
    # 复制操作总是在目标位置创建新文件/目录
    result["new_files"] = {
        str(relative_dst): "目录" if is_src_dir else "文件"
    }
    
    return result


@mcp.tool()
def delete(req: DeleteRequest) -> dict[str, str]:
    """删除文件/目录。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    if not p.exists():
        return {"status": "ok", "path": str(p), "message": "not found", "new_files": {}}
    if p.is_dir():
        if req.recursive:
            shutil.rmtree(p)
        else:
            p.rmdir()
    else:
        p.unlink()
    return {"status": "ok", "path": str(p), "new_files": {}}


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
def read_office_text(req: OfficeReadRequest) -> dict[str, str]:
    """读取 Office 文本（PDF/DOCX/PPTX）。"""
    p = resolve_in_sandbox(req.path, req.session_id)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")
    ext = p.suffix.lower()
    if ext == ".pdf":
        text = _read_pdf_text(p)
    elif ext == ".docx":
        text = _read_docx_text(p)
    elif ext == ".pptx":
        text = _read_pptx_text(p)
    else:
        raise ValueError("仅支持 .pdf/.docx/.pptx")
    return {"path": str(p), "text": text, "new_files": {}}


# -----------------------------------------------------------------------------
# 文件同步功能
# -----------------------------------------------------------------------------

def _is_supported_file_type(file_path: Path) -> bool:
    """检查文件类型是否支持同步"""
    supported_extensions = {'.txt', '.md', '.pdf', '.doc', '.docx', '.ppt', '.pptx', 
                          '.xls', '.xlsx', '.json', '.yaml', '.yml', '.csv', '.rtf'}
    return file_path.suffix.lower() in supported_extensions


def _get_file_hash(file_path: Path, algorithm: str = "md5", chunk_size: int = 8192) -> str:
    """
    计算文件哈希值，支持多种算法
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法 (md5, sha1, sha256)
        chunk_size: 读取块大小
    """
    if algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        hasher = hashlib.md5()  # 默认使用MD5
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _get_file_etag(file_path: Path, chunk_size: int = 8192) -> str:
    """
    生成文件ETag (类似AWS S3的ETag算法)
    对于单个文件，使用MD5哈希
    对于大文件，可以使用分块MD5然后再哈希
    """
    file_size = file_path.stat().st_size
    
    # 对于小文件（<50MB），直接使用MD5
    if file_size < 50 * 1024 * 1024:
        return _get_file_hash(file_path, "md5", chunk_size)
    
    # 对于大文件，使用分块哈希
    chunk_count = 0
    chunk_hashes = []
    
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunk_hashes.append(hashlib.md5(chunk).hexdigest())
            chunk_count += 1
    
    # 将所有块的哈希组合，再次哈希
    combined = "".join(chunk_hashes)
    final_hash = hashlib.md5(combined.encode()).hexdigest()
    return f"{final_hash}-{chunk_count}"


def _get_file_fingerprint(file_path: Path, strategy: str = "hash", chunk_size: int = 8192) -> Dict[str, Any]:
    """
    获取文件指纹，用于比较文件是否相同
    
    Args:
        file_path: 文件路径
        strategy: 指纹策略
    
    Returns:
        包含文件指纹信息的字典
    """
    stat_info = file_path.stat()
    base_info = {
        "size": int(stat_info.st_size),
        "name": file_path.name
    }
    
    if strategy == "size_only":
        return base_info
    
    elif strategy == "size_hash":
        # 先比较大小，如果大小相同再计算哈希
        base_info.update({
            "hash": _get_file_hash(file_path, "md5", chunk_size),
            "algorithm": "md5"
        })
        return base_info
    
    elif strategy == "hash":
        # 直接使用SHA256哈希（更安全）
        base_info.update({
            "hash": _get_file_hash(file_path, "sha256", chunk_size),
            "algorithm": "sha256"
        })
        return base_info
    
    elif strategy == "etag":
        # 使用ETag策略
        base_info.update({
            "etag": _get_file_etag(file_path, chunk_size),
            "algorithm": "etag"
        })
        return base_info
    
    else:
        # 默认策略：大小 + SHA256
        base_info.update({
            "hash": _get_file_hash(file_path, "sha256", chunk_size),
            "algorithm": "sha256"
        })
        return base_info


def _get_target_file_info(target_path: Path) -> Dict[str, Any] | None:
    """获取目标文件信息"""
    try:
        if not target_path.exists():
            return None
        
        stat_info = target_path.stat()
        return {
            "size": int(stat_info.st_size),
            "mtime": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "path": str(target_path)
        }
    except Exception as e:
        print(f"获取目标文件信息失败 {target_path}: {e}")
        return None


def _get_target_file_hash(target_path: Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str | None:
    """
    获取目标文件的哈希值
    直接读取文件计算哈希
    """
    try:
        if not target_path.exists():
            return None
        
        return _get_file_hash(target_path, algorithm, chunk_size)
        
    except Exception as e:
        print(f"获取目标文件哈希失败 {target_path}: {e}")
        return None


def _is_text_file_by_extension(file_path: str) -> bool:
    """根据文件扩展名判断是否为文本文件"""
    text_extensions = {'.txt', '.md', '.json', '.yaml', '.yml', '.csv', '.rtf'}
    return Path(file_path).suffix.lower() in text_extensions


def _files_are_identical(local_fingerprint: Dict[str, Any], 
                        target_info: Dict[str, Any] | None,
                        target_hash: str | None = None) -> bool:
    """
    比较本地和目标文件是否相同
    使用多层比较策略提高效率
    """
    if target_info is None:
        return False  # 目标文件不存在
    
    # 1. 首先比较文件大小（最快）
    target_size = target_info.get("size")
    if target_size is None or int(target_size) != local_fingerprint["size"]:
        return False
    
    # 2. 如果大小相同，比较哈希（如果有的话）
    if "hash" in local_fingerprint and target_hash:
        return local_fingerprint["hash"] == target_hash
    
    # 3. 如果使用ETag策略
    if "etag" in local_fingerprint:
        return target_hash is not None and local_fingerprint["etag"] == target_hash
    
    # 4. 如果没有哈希信息，只能认为不同（安全起见）
    return False


def _copy_file_to_target(local_file_path: Path, target_path: Path) -> bool:
    """复制文件到目标路径，确保保持目录结构"""
    try:
        # 检查文件大小限制 (50MB)
        file_size = local_file_path.stat().st_size
        if file_size > 50 * 1024 * 1024:  # 50MB
            print(f"文件过大，跳过: {local_file_path} ({file_size / 1024 / 1024:.1f}MB)")
            return False
        
        # 确保目标文件的父目录存在（保持原有目录结构）
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 复制文件，保持文件时间戳和权限
        shutil.copy2(local_file_path, target_path)
        return True
            
    except Exception as e:
        print(f"复制文件异常 {local_file_path} -> {target_path}: {e}")
        return False


def _is_text_file(file_path: Path) -> bool:
    """判断是否为文本文件"""
    text_extensions = {'.txt', '.md', '.json', '.yaml', '.yml', '.csv', '.rtf'}
    return file_path.suffix.lower() in text_extensions




@mcp.tool()
def sync_files_to_target(req: SyncRequest) -> SyncResult:
    """
    将本地BASE_DIR中的支持文件同步到目标路径，保持完整的目录结构。
    
    同步结构: BASE_DIR/* -> target_base_path/vm_id_session_id/*
    例如: BASE_DIR/.useit/123.txt -> target_base_path/vm_id_session_id/.useit/123.txt
    
    支持的文件类型: txt, md, pdf, doc, docx, ppt, pptx, xls, xlsx, json, yaml, csv, rtf
    文件大小限制: 50MB
    同步策略: 基于内容哈希的增量同步
    """
    try:
        result = SyncResult(success=False, message="")
        
        # 构造目标路径 - 直接保持base_dir的完整目录结构
        target_base_path = Path(req.target_base_path) / f"{req.vm_id}_{req.session_id}"
        
        # 无论是否dry_run都创建基础目录结构，用于验证路径和权限
        try:
            target_base_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            result.message = f"无法创建目标目录: {e}"
            return result
        
        # 扫描本地文件
        local_files = []
        for file_path in BASE_DIR.rglob("*"):
            if file_path.is_file() and _is_supported_file_type(file_path):
                try:
                    relative_path = file_path.relative_to(BASE_DIR)
                    local_files.append((file_path, str(relative_path)))
                except ValueError:
                    continue
        
        if not local_files:
            result.success = True
            result.message = "没有找到需要同步的文件"
            return result
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        total_size = 0
        
        for local_file, relative_path in local_files:
            try:
                # 检查文件大小
                file_size = local_file.stat().st_size
                if file_size > 50 * 1024 * 1024:  # 50MB限制
                    result.error_files.append({
                        "file": relative_path,
                        "error": f"文件过大: {file_size / 1024 / 1024:.1f}MB > 50MB"
                    })
                    error_count += 1
                    continue
                
                # 构造目标路径 - 直接在目标基础路径下保持原有目录结构
                target_file_path = target_base_path / relative_path
                
                # 检查是否需要同步
                need_sync = req.force_sync
                if not need_sync:
                    # 获取本地文件指纹
                    local_fingerprint = _get_file_fingerprint(
                        local_file, req.sync_strategy, req.chunk_size
                    )
                    
                    # 获取目标文件信息
                    target_file_info = _get_target_file_info(target_file_path)
                    
                    if target_file_info is None:
                        # 目标文件不存在，需要同步
                        need_sync = True
                    else:
                        # 使用不同策略比较文件
                        if req.sync_strategy == "size_only":
                            # 只比较大小
                            target_size = target_file_info.get("size", 0)
                            need_sync = local_fingerprint["size"] != int(target_size)
                            
                        elif req.sync_strategy in ["hash", "size_hash", "etag"]:
                            # 基于内容哈希的比较
                            if local_fingerprint["size"] != int(target_file_info.get("size", 0)):
                                # 大小不同，肯定需要同步
                                need_sync = True
                            else:
                                # 大小相同，需要获取目标文件哈希进行比较
                                algorithm = "sha256" if req.sync_strategy == "hash" else "md5"
                                target_hash = _get_target_file_hash(
                                    target_file_path, algorithm, req.chunk_size
                                )
                                
                                need_sync = not _files_are_identical(
                                    local_fingerprint, target_file_info, target_hash
                                )
                        else:
                            # 未知策略，fallback到哈希比较
                            target_hash = _get_target_file_hash(
                                target_file_path, "sha256", req.chunk_size
                            )
                            need_sync = not _files_are_identical(
                                local_fingerprint, target_file_info, target_hash
                            )
                
                if not need_sync:
                    result.skipped_files.append(relative_path)
                    skipped_count += 1
                    continue
                
                if req.dry_run:
                    result.synced_files.append(relative_path)
                    synced_count += 1
                    total_size += file_size
                    continue
                
                # 执行实际同步
                if _copy_file_to_target(local_file, target_file_path):
                    result.synced_files.append(relative_path)
                    synced_count += 1
                    total_size += file_size
                else:
                    result.error_files.append({
                        "file": relative_path,
                        "error": "复制失败"
                    })
                    error_count += 1
                    
            except Exception as e:
                result.error_files.append({
                    "file": relative_path,
                    "error": str(e)
                })
                error_count += 1
        
        # 生成同步摘要
        result.total_size = total_size
        result.sync_summary = {
            "total_files": len(local_files),
            "synced": synced_count,
            "skipped": skipped_count,
            "errors": error_count,
            "dry_run": req.dry_run,
            "target_path": str(target_base_path)
        }
        
        if req.dry_run:
            result.success = True
            result.message = f"预演完成: 将同步 {synced_count} 个文件到 {target_base_path} ({total_size / 1024 / 1024:.1f}MB)"
        else:
            result.success = error_count == 0
            if result.success:
                result.message = f"同步完成: {synced_count} 个文件已同步到 {target_base_path}，{skipped_count} 个文件跳过"
            else:
                result.message = f"同步部分失败: {synced_count} 个成功，{error_count} 个失败"
        
        return result
        
    except Exception as e:
        return SyncResult(
            success=False,
            message=f"同步异常: {str(e)}",
            sync_summary={"error": str(e)}
        )


# -----------------------------------------------------------------------------
# 启动
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # 保持兼容性，使用原有启动方式
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from server_base import start_mcp_server
    
    start_mcp_server(mcp, 8003, "filesystem")


