"""
Base Directory Decorator for MCP Servers

统一管理所有MCP服务器的文件操作基础目录，确保所有文件操作都在指定的沙箱目录下进行。
"""

import os
import functools
from pathlib import Path
from typing import Any, Callable, Dict


class BaseDirManager:
    """基础目录管理器"""
    
    def __init__(self, base_dir: str = None):
        """
        初始化基础目录管理器
        
        Args:
            base_dir: 基础目录路径，如果为None则使用环境变量MCP_BASE_DIR或默认值
        """
        if base_dir is None:
            base_dir = os.environ.get('MCP_BASE_DIR', os.path.join(os.getcwd(), 'mcp_workspace'))
        
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 MCP基础目录管理器初始化: {self.base_dir}")
    
    def get_base_dir(self) -> Path:
        """获取基础目录"""
        return self.base_dir
    
    def resolve_path(self, user_path: str, session_id: str = None) -> Path:
        """
        解析用户路径到基础目录内的安全路径
        
        Args:
            user_path: 用户提供的路径
            session_id: 会话ID (保留兼容性，但不影响路径解析)
            
        Returns:
            解析后的安全路径
            
        Raises:
            ValueError: 如果路径超出了沙箱范围
        """
        # 直接使用base_dir作为沙箱根目录
        sandbox_root = self.base_dir
        
        # 解析用户路径
        candidate = Path(user_path)
        if not candidate.is_absolute():
            candidate = sandbox_root / candidate
        
        abs_path = candidate.expanduser().resolve()
        
        # 检查路径是否在沙箱内
        try:
            if abs_path == sandbox_root or sandbox_root in abs_path.parents:
                return abs_path
        except Exception:
            pass
        
        raise ValueError(f"路径超出沙箱范围: {abs_path} (沙箱: {sandbox_root})")


# 全局基础目录管理器实例
_global_base_dir_manager = None


def get_base_dir_manager() -> BaseDirManager:
    """获取全局基础目录管理器实例"""
    global _global_base_dir_manager
    if _global_base_dir_manager is None:
        _global_base_dir_manager = BaseDirManager()
    return _global_base_dir_manager


def with_base_dir(func: Callable) -> Callable:
    """
    装饰器：为函数注入基础目录管理功能
    
    该装饰器会：
    1. 初始化基础目录管理器
    2. 在函数执行前设置环境变量
    3. 为函数提供base_dir_manager参数
    
    被装饰的函数可以通过kwargs获取base_dir_manager实例
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 获取基础目录管理器
        manager = get_base_dir_manager()
        
        # 设置环境变量供其他组件使用
        os.environ['FILESYSTEM_BASE_DIR'] = str(manager.base_dir)
        os.environ['AUDIO_OUTPUT_DIR'] = str(manager.base_dir / 'audio_output')
        os.environ['MCP_WORKSPACE'] = str(manager.base_dir)
        
        # 注入base_dir_manager到函数参数
        kwargs['base_dir_manager'] = manager
        
        return func(*args, **kwargs)
    
    return wrapper


def with_session_base_dir(func: Callable) -> Callable:
    """
    装饰器：为需要session隔离的函数注入session基础目录
    
    该装饰器会从函数参数中提取session_id，并自动创建对应的session目录
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        manager = get_base_dir_manager()
        
        # 尝试从参数中获取session_id
        session_id = None
        if 'session_id' in kwargs:
            session_id = kwargs['session_id']
        elif hasattr(args[0], 'session_id') and args[0].session_id:
            session_id = args[0].session_id
        
        if session_id:
            session_dir = manager.get_session_dir(session_id)
            # 设置session相关的环境变量
            os.environ['CURRENT_SESSION_DIR'] = str(session_dir)
            kwargs['session_dir'] = session_dir
        
        kwargs['base_dir_manager'] = manager
        return await func(*args, **kwargs)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        manager = get_base_dir_manager()
        
        # 尝试从参数中获取session_id
        session_id = None
        if 'session_id' in kwargs:
            session_id = kwargs['session_id']
        elif hasattr(args[0], 'session_id') and args[0].session_id:
            session_id = args[0].session_id
        
        if session_id:
            session_dir = manager.get_session_dir(session_id)
            # 设置session相关的环境变量
            os.environ['CURRENT_SESSION_DIR'] = str(session_dir)
            kwargs['session_dir'] = session_dir
        
        kwargs['base_dir_manager'] = manager
        return func(*args, **kwargs)
    
    # 检查函数是否是async
    if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
        return async_wrapper
    else:
        return sync_wrapper


# 便捷函数
def set_global_base_dir(base_dir: str):
    """设置全局基础目录"""
    global _global_base_dir_manager
    _global_base_dir_manager = BaseDirManager(base_dir)


def get_workspace_path(*paths: str) -> Path:
    """
    获取工作空间中的路径
    
    Args:
        *paths: 路径组件
        
    Returns:
        完整的工作空间路径
    """
    manager = get_base_dir_manager()
    base = manager.get_base_dir()
    
    if paths:
        return base.joinpath(*paths)
    else:
        return base


def ensure_workspace_dir(*paths: str) -> Path:
    """
    确保工作空间中的目录存在
    
    Args:
        *paths: 路径组件
        
    Returns:
        确保存在的目录路径
    """
    dir_path = get_workspace_path(*paths)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path