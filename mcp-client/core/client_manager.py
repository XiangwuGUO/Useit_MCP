"""
简化的客户机管理器
专注于核心MCP客户机管理功能，移除FRP发现等复杂功能
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .api_models import ClientStatus, ToolInfo, ResourceInfo

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP客户机连接封装"""
    
    def __init__(self, vm_id: str, session_id: str, remote_url: str, timeout: int = 30):
        self.vm_id = vm_id
        self.session_id = session_id
        self.remote_url = remote_url.rstrip('/')
        self.timeout = timeout
        self.client_id = f"{vm_id}/{session_id}"
        
        # 连接状态
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.connected = False
        self.last_seen = datetime.now()
        
        # 缓存
        self._tools_cache: Optional[List[ToolInfo]] = None
        self._resources_cache: Optional[List[ResourceInfo]] = None
    
    async def connect(self) -> None:
        """连接到远程MCP服务器"""
        if self.connected:
            return
        
        try:
            logger.info(f"🔌 连接到 {self.remote_url}")
            
            # 创建客户端连接  
            client_result = await self.exit_stack.enter_async_context(
                streamablehttp_client(self.remote_url)
            )
            
            # 创建会话
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(client_result[0], client_result[1])
            )
            
            # 测试连接 (增加超时处理)
            import asyncio
            try:
                await asyncio.wait_for(self.session.initialize(), timeout=10.0)
                
                self.connected = True
                self.last_seen = datetime.now()
                logger.info(f"✅ 成功连接到 {self.remote_url}")
                
                # 清空缓存
                self._tools_cache = None
                self._resources_cache = None
                
            except asyncio.TimeoutError:
                logger.error(f"连接超时: {self.remote_url}")
                await self.disconnect()
                raise RuntimeError(f"连接超时: {self.remote_url}")
            except Exception as init_error:
                logger.error(f"初始化失败: {init_error}")
                await self.disconnect() 
                raise RuntimeError(f"初始化失败: {init_error}")
            
        except Exception as e:
            logger.error(f"❌ 连接失败 {self.remote_url}: {e}")
            await self.disconnect()
            raise
    
    async def disconnect(self) -> None:
        """断开连接"""
        if not self.connected:
            return
        
        logger.info(f"🔌 断开连接 {self.remote_url}")
        
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.warning(f"断开连接时出错: {e}")
        finally:
            self.session = None
            self.connected = False
            self._tools_cache = None
            self._resources_cache = None
    
    async def get_tools(self) -> List[ToolInfo]:
        """获取工具列表"""
        if not self.connected or not self.session:
            raise RuntimeError(f"客户机 {self.client_id} 未连接")
        
        # 使用缓存
        if self._tools_cache is not None:
            return self._tools_cache
        
        try:
            result = await self.session.list_tools()
            tools = [
                ToolInfo(
                    name=tool.name,
                    description=tool.description or "暂无描述",
                    vm_id=self.vm_id,
                    session_id=self.session_id,
                    input_schema=tool.inputSchema or {}
                )
                for tool in result.tools
            ]
            self._tools_cache = tools
            self.last_seen = datetime.now()
            return tools
        except Exception as e:
            logger.error(f"获取工具列表失败 {self.client_id}: {e}")
            raise
    
    async def get_resources(self) -> List[ResourceInfo]:
        """获取资源列表"""
        if not self.connected or not self.session:
            raise RuntimeError(f"客户机 {self.client_id} 未连接")
        
        # 使用缓存
        if self._resources_cache is not None:
            return self._resources_cache
        
        try:
            result = await self.session.list_resources()
            resources = [
                ResourceInfo(
                    uri=resource.uri,
                    name=resource.name or resource.uri,
                    description=resource.description or "暂无描述",
                    vm_id=self.vm_id,
                    session_id=self.session_id
                )
                for resource in result.resources
            ]
            self._resources_cache = resources
            self.last_seen = datetime.now()
            return resources
        except Exception as e:
            logger.error(f"获取资源列表失败 {self.client_id}: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用工具"""
        if not self.connected or not self.session:
            raise RuntimeError(f"客户机 {self.client_id} 未连接")
        
        try:
            logger.info(f"🔧 调用工具 {tool_name} on {self.client_id}")
            result = await self.session.call_tool(tool_name, arguments)
            self.last_seen = datetime.now()
            
            # 返回结果内容
            if hasattr(result, 'content') and result.content:
                return [item.dict() if hasattr(item, 'dict') else item for item in result.content]
            else:
                return result
                
        except Exception as e:
            logger.error(f"调用工具失败 {tool_name} on {self.client_id}: {e}")
            raise
    
    def get_status(self) -> ClientStatus:
        """获取客户机状态"""
        return ClientStatus(
            vm_id=self.vm_id,
            session_id=self.session_id,
            remote_url=self.remote_url,
            status="connected" if self.connected else "disconnected",
            last_seen=self.last_seen.isoformat() if self.last_seen else None,
            tool_count=len(self._tools_cache) if self._tools_cache else 0,
            resource_count=len(self._resources_cache) if self._resources_cache else 0
        )


class ClientManager:
    """简化的客户机管理器"""
    
    def __init__(self):
        """初始化客户机管理器"""
        self.clients: Dict[str, MCPClient] = {}
        self._lock = asyncio.Lock()
        logger.info("🚀 简化客户机管理器已启动")
    
    def _make_client_id(self, vm_id: str, session_id: str) -> str:
        """生成客户机ID"""
        return f"{vm_id}/{session_id}"
    
    async def add_client(self, vm_id: str, session_id: str, remote_url: str) -> None:
        """添加客户机"""
        async with self._lock:
            client_id = self._make_client_id(vm_id, session_id)
            
            # 如果已存在，先移除
            if client_id in self.clients:
                await self.clients[client_id].disconnect()
            
            # 创建新客户机
            client = MCPClient(vm_id, session_id, remote_url)
            self.clients[client_id] = client
            
            # 尝试连接
            try:
                await client.connect()
                logger.info(f"✅ 客户机添加成功: {client_id}")
            except Exception as e:
                # 连接失败时移除客户机
                del self.clients[client_id]
                raise RuntimeError(f"连接失败: {e}")
    
    async def remove_client(self, vm_id: str, session_id: str) -> bool:
        """移除客户机"""
        async with self._lock:
            client_id = self._make_client_id(vm_id, session_id)
            
            if client_id in self.clients:
                await self.clients[client_id].disconnect()
                del self.clients[client_id]
                logger.info(f"🗑️ 客户机移除成功: {client_id}")
                return True
            return False
    
    async def get_client(self, vm_id: str, session_id: str) -> Optional[MCPClient]:
        """获取客户机"""
        client_id = self._make_client_id(vm_id, session_id)
        return self.clients.get(client_id)
    
    async def get_all_clients(self) -> List[ClientStatus]:
        """获取所有客户机状态"""
        return [client.get_status() for client in self.clients.values()]
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有客户机的工具列表"""
        all_tools = []
        
        for client in self.clients.values():
            if not client.connected:
                continue
                
            try:
                tools = await client.get_tools()
                for tool in tools:
                    all_tools.append({
                        "client_id": client.client_id,
                        "vm_id": client.vm_id,
                        "session_id": client.session_id,
                        "remote_url": client.remote_url,
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema
                    })
            except Exception as e:
                logger.warning(f"获取工具列表失败 {client.client_id}: {e}")
        
        return all_tools
    
    async def get_all_resources(self) -> List[Dict[str, Any]]:
        """获取所有客户机的资源列表"""
        all_resources = []
        
        for client in self.clients.values():
            if not client.connected:
                continue
                
            try:
                resources = await client.get_resources()
                for resource in resources:
                    all_resources.append({
                        "client_id": client.client_id,
                        "vm_id": client.vm_id,
                        "session_id": client.session_id,
                        "remote_url": client.remote_url,
                        "uri": resource.uri,
                        "name": resource.name,
                        "description": resource.description,
                        "mimeType": resource.mimeType
                    })
            except Exception as e:
                logger.warning(f"获取资源列表失败 {client.client_id}: {e}")
        
        return all_resources
    
    async def call_tool(self, vm_id: str, session_id: str, tool_name: str, 
                       arguments: Dict[str, Any]) -> Any:
        """调用指定客户机的工具"""
        client = await self.get_client(vm_id, session_id)
        if not client:
            raise RuntimeError(f"客户机不存在: {vm_id}/{session_id}")
        
        return await client.call_tool(tool_name, arguments)
    
    async def find_tool_and_call(self, tool_name: str, arguments: Dict[str, Any], 
                                preferred_vm_id: Optional[str] = None) -> Any:
        """查找工具并调用"""
        # 查找有该工具的客户机
        candidates = []
        
        for client in self.clients.values():
            if not client.connected:
                continue
                
            try:
                tools = await client.get_tools()
                tool_names = [tool.name for tool in tools]
                
                if tool_name in tool_names:
                    candidates.append(client)
                    
            except Exception as e:
                logger.warning(f"检查工具时出错 {client.client_id}: {e}")
        
        if not candidates:
            raise RuntimeError(f"未找到工具: {tool_name}")
        
        # 优先选择指定的VM
        if preferred_vm_id:
            preferred_clients = [c for c in candidates if c.vm_id == preferred_vm_id]
            if preferred_clients:
                candidates = preferred_clients
        
        # 使用第一个可用的客户机
        client = candidates[0]
        return await client.call_tool(tool_name, arguments)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        connected_count = sum(1 for c in self.clients.values() if c.connected)
        total_tools = 0
        total_resources = 0
        
        for client in self.clients.values():
            if client._tools_cache:
                total_tools += len(client._tools_cache)
            if client._resources_cache:
                total_resources += len(client._resources_cache)
        
        return {
            "total_clients": len(self.clients),
            "connected_clients": connected_count,
            "total_tools": total_tools,
            "total_resources": total_resources,
            "discovery_enabled": False  # 简化版不支持服务发现
        }
    
    async def cleanup(self):
        """清理所有连接"""
        logger.info("🧹 清理客户机连接...")
        async with self._lock:
            for client in list(self.clients.values()):
                await client.disconnect()
            self.clients.clear()
        logger.info("✅ 客户机连接清理完成")