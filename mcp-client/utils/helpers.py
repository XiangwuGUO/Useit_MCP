"""
辅助函数和工具

通用的辅助功能和工具函数
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from functools import wraps

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """格式化时间间隔"""
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m{remaining_seconds:.1f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        return f"{hours}h{remaining_minutes}m"


def format_timestamp(dt: datetime = None) -> str:
    """格式化时间戳"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def safe_json_loads(data: str, default: Any = None) -> Any:
    """安全的JSON解析"""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON解析失败: {e}")
        return default


def safe_json_dumps(data: Any, indent: Optional[int] = None, ensure_ascii: bool = False) -> str:
    """安全的JSON序列化"""
    try:
        return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, default=str)
    except (TypeError, ValueError) as e:
        logger.warning(f"JSON序列化失败: {e}")
        return str(data)


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断字符串"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_bytes(bytes_count: int) -> str:
    """格式化字节数"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024:
            return f"{bytes_count:.1f}{unit}"
        bytes_count /= 1024
    return f"{bytes_count:.1f}PB"


def timing_decorator(func):
    """计时装饰器"""
    import asyncio
    
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"{func.__name__} 执行时间: {format_duration(execution_time)}")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func.__name__} 执行失败 (用时: {format_duration(execution_time)}): {e}")
                raise
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"{func.__name__} 执行时间: {format_duration(execution_time)}")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func.__name__} 执行失败 (用时: {format_duration(execution_time)}): {e}")
                raise
        return sync_wrapper


class SimpleCache:
    """简单的内存缓存"""
    
    def __init__(self, default_ttl: int = 300):  # 默认5分钟过期
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        if key not in self._cache:
            return default
        
        entry = self._cache[key]
        if datetime.now() > entry['expires']:
            del self._cache[key]
            return default
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        if ttl is None:
            ttl = self.default_ttl
        
        expires = datetime.now() + timedelta(seconds=ttl)
        self._cache[key] = {
            'value': value,
            'expires': expires
        }
    
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if now > entry['expires']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)


class RateLimiter:
    """简单的速率限制器"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        
        # 清理过期记录
        if key in self._requests:
            self._requests[key] = [
                req_time for req_time in self._requests[key]
                if now - req_time < self.time_window
            ]
        else:
            self._requests[key] = []
        
        # 检查是否超过限制
        if len(self._requests[key]) >= self.max_requests:
            return False
        
        # 记录本次请求
        self._requests[key].append(now)
        return True
    
    def get_remaining(self, key: str) -> int:
        """获取剩余请求数"""
        if key not in self._requests:
            return self.max_requests
        
        now = time.time()
        valid_requests = [
            req_time for req_time in self._requests[key]
            if now - req_time < self.time_window
        ]
        
        return max(0, self.max_requests - len(valid_requests))


def validate_vm_session_id(vm_id: str, session_id: str) -> bool:
    """验证VM ID和Session ID格式"""
    if not vm_id or not session_id:
        return False
    
    # 基本格式验证
    if len(vm_id) > 100 or len(session_id) > 100:
        return False
    
    # 不允许包含特殊字符
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        if char in vm_id or char in session_id:
            return False
    
    return True


def extract_error_message(error: Exception) -> str:
    """提取错误信息"""
    error_msg = str(error)
    
    # 截断过长的错误信息
    if len(error_msg) > 200:
        error_msg = error_msg[:197] + "..."
    
    return error_msg


def merge_dicts(*dicts: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
    """合并多个字典"""
    result = {}
    
    for d in dicts:
        if not isinstance(d, dict):
            continue
            
        for key, value in d.items():
            if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value
    
    return result


# 全局实例
cache = SimpleCache()
rate_limiter = RateLimiter(max_requests=60, time_window=60)  # 每分钟60次请求