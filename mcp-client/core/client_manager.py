"""
简化的客户机管理器
专注于核心MCP客户机管理功能，基于vm_id+session_id的新存储结构
每个客户机包含多个服务器
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .api_models import ClientStatus, ToolInfo, ResourceInfo

logger = logging.getLogger(__name__)


class MCPServer:
    """单个MCP服务器连接封装"""
    
    def __init__(self, name: str, remote_url: str, description: str = "", timeout: int = 30):
        self.name = name
        self.remote_url = remote_url.rstrip('/')
        self.description = description
        self.timeout = timeout
        
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
            logger.info(f"🔌 连接到 {self.name}: {self.remote_url}")
            
            # 创建客户端连接  
            client_result = await self.exit_stack.enter_async_context(
                streamablehttp_client(self.remote_url)
            )
            
            # 创建会话
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(client_result[0], client_result[1])
            )
            
            # 测试连接 (增加超时处理)
            try:
                await asyncio.wait_for(self.session.initialize(), timeout=10.0)
                
                self.connected = True
                self.last_seen = datetime.now()
                logger.info(f"✅ 成功连接到服务器 {self.name}")
                
                # 清空缓存
                self._tools_cache = None
                self._resources_cache = None
                
            except asyncio.TimeoutError:
                logger.error(f"连接超时: {self.name} - {self.remote_url}")
                await self.disconnect()
                raise RuntimeError(f"连接超时: {self.name}")
            except Exception as init_error:
                logger.error(f"初始化失败: {self.name} - {init_error}")
                await self.disconnect() 
                raise RuntimeError(f"初始化失败: {self.name} - {init_error}")
            
        except Exception as e:
            logger.error(f"❌ 连接失败 {self.name}: {e}")
            await self.disconnect()
            raise
    
    async def disconnect(self) -> None:
        """断开连接"""
        if not self.connected:
            return
        
        logger.info(f"🔌 断开连接 {self.name}")
        
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.warning(f"断开连接时出错 {self.name}: {e}")
        finally:
            self.session = None
            self.connected = False
            self._tools_cache = None
            self._resources_cache = None
    
    async def get_tools(self, vm_id: str, session_id: str) -> List[ToolInfo]:
        """获取工具列表"""
        if not self.connected or not self.session:
            raise RuntimeError(f"服务器 {self.name} 未连接")
        
        # 使用缓存
        if self._tools_cache is not None:
            return self._tools_cache
        
        try:
            result = await self.session.list_tools()
            tools = [
                ToolInfo(
                    name=tool.name,
                    description=tool.description or "暂无描述",
                    vm_id=vm_id,
                    session_id=session_id,
                    server_name=self.name,
                    input_schema=tool.inputSchema or {}
                )
                for tool in result.tools
            ]
            self._tools_cache = tools
            self.last_seen = datetime.now()
            return tools
        except Exception as e:
            logger.error(f"获取工具列表失败 {self.name}: {e}")
            raise
    
    async def get_resources(self, vm_id: str, session_id: str) -> List[ResourceInfo]:
        """获取资源列表"""
        if not self.connected or not self.session:
            raise RuntimeError(f"服务器 {self.name} 未连接")
        
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
                    vm_id=vm_id,
                    session_id=session_id,
                    server_name=self.name,
                    mimeType=getattr(resource, 'mimeType', None)
                )
                for resource in result.resources
            ]
            self._resources_cache = resources
            self.last_seen = datetime.now()
            return resources
        except Exception as e:
            logger.error(f"获取资源列表失败 {self.name}: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用工具"""
        if not self.connected or not self.session:
            raise RuntimeError(f"服务器 {self.name} 未连接")
        
        try:
            logger.info(f"🔧 调用工具 {tool_name} on {self.name}")
            result = await self.session.call_tool(tool_name, arguments)
            self.last_seen = datetime.now()
            
            # 返回结果内容
            if hasattr(result, 'content') and result.content:
                return [item.model_dump() if hasattr(item, 'model_dump') else (item.dict() if hasattr(item, 'dict') else item) for item in result.content]
            else:
                return result
                
        except Exception as e:
            logger.error(f"调用工具失败 {tool_name} on {self.name}: {e}")
            raise


class MCPClient:
    """MCP客户机组合（包含多个服务器）"""
    
    def __init__(self, vm_id: str, session_id: str):
        self.vm_id = vm_id
        self.session_id = session_id
        self.client_id = f"{vm_id}/{session_id}"
        self.servers: Dict[str, MCPServer] = {}  # server_name -> MCPServer
        self.last_seen = datetime.now()
    
    async def add_server(self, name: str, remote_url: str, description: str = "") -> None:
        """添加服务器到客户机组合"""
        if name in self.servers:
            # 如果服务器已存在，先断开连接
            await self.servers[name].disconnect()
        
        server = MCPServer(name, remote_url, description)
        self.servers[name] = server
        await server.connect()
        self.last_seen = datetime.now()
        logger.info(f"✅ 服务器 {name} 添加到客户机 {self.client_id}")
    
    async def remove_server(self, name: str) -> bool:
        """从客户机组合中移除服务器"""
        if name in self.servers:
            await self.servers[name].disconnect()
            del self.servers[name]
            self.last_seen = datetime.now()
            logger.info(f"🗑️ 服务器 {name} 从客户机 {self.client_id} 中移除")
            return True
        return False
    
    async def get_server(self, name: str) -> Optional[MCPServer]:
        """获取指定服务器"""
        return self.servers.get(name)
    
    def get_connected_servers(self) -> List[str]:
        """获取已连接的服务器名称列表"""
        return [name for name, server in self.servers.items() if server.connected]
    
    def is_any_server_connected(self) -> bool:
        """检查是否有任何服务器连接"""
        return any(server.connected for server in self.servers.values())
    
    async def get_all_tools(self) -> List[ToolInfo]:
        """获取客户机所有服务器的工具列表"""
        all_tools = []
        for server in self.servers.values():
            if server.connected:
                try:
                    tools = await server.get_tools(self.vm_id, self.session_id)
                    all_tools.extend(tools)
                except Exception as e:
                    logger.warning(f"获取服务器 {server.name} 工具失败: {e}")
        return all_tools
    
    async def get_all_resources(self) -> List[ResourceInfo]:
        """获取客户机所有服务器的资源列表"""
        all_resources = []
        for server in self.servers.values():
            if server.connected:
                try:
                    resources = await server.get_resources(self.vm_id, self.session_id)
                    all_resources.extend(resources)
                except Exception as e:
                    logger.warning(f"获取服务器 {server.name} 资源失败: {e}")
        return all_resources
    
    async def call_tool_on_server(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """在指定服务器上调用工具"""
        server = self.servers.get(server_name)
        if not server:
            raise RuntimeError(f"服务器不存在: {server_name}")
        
        return await server.call_tool(tool_name, arguments)
    
    async def find_tool_and_call(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[Any, str]:
        """在客户机内查找工具并调用，返回结果和服务器名称"""
        for server_name, server in self.servers.items():
            if not server.connected:
                continue
            
            try:
                tools = await server.get_tools(self.vm_id, self.session_id)
                if any(tool.name == tool_name for tool in tools):
                    result = await server.call_tool(tool_name, arguments)
                    return result, server_name
            except Exception as e:
                logger.warning(f"在服务器 {server_name} 查找工具时出错: {e}")
        
        raise RuntimeError(f"未找到工具: {tool_name}")
    
    async def disconnect_all(self) -> None:
        """断开所有服务器连接"""
        for server in self.servers.values():
            await server.disconnect()
        logger.info(f"🔌 客户机 {self.client_id} 所有服务器已断开连接")
    
    def get_status(self) -> ClientStatus:
        """获取客户机状态"""
        connected_servers = self.get_connected_servers()
        total_tools = 0
        total_resources = 0
        
        for server in self.servers.values():
            if server._tools_cache:
                total_tools += len(server._tools_cache)
            if server._resources_cache:
                total_resources += len(server._resources_cache)
        
        return ClientStatus(
            vm_id=self.vm_id,
            session_id=self.session_id,
            status="connected" if connected_servers else "disconnected",
            last_seen=self.last_seen.isoformat() if self.last_seen else None,
            tool_count=total_tools,
            resource_count=total_resources,
            server_count=len(self.servers),
            connected_servers=connected_servers
        )


class ClientManager:
    """简化的客户机管理器"""
    
    def __init__(self):
        """初始化客户机管理器"""
        self.clients: Dict[str, MCPClient] = {}  # client_id -> MCPClient(包含多个servers)
        self._lock = asyncio.Lock()
        logger.info("🚀 简化客户机管理器已启动")
    
    def _make_client_id(self, vm_id: str, session_id: str) -> str:
        """生成客户机ID"""
        return f"{vm_id}/{session_id}"
    
    async def add_server_to_client(self, vm_id: str, session_id: str, server_name: str, remote_url: str, description: str = "") -> None:
        """添加服务器到指定客户机"""
        async with self._lock:
            client_id = self._make_client_id(vm_id, session_id)
            
            # 如果客户机不存在，创建新的
            if client_id not in self.clients:
                self.clients[client_id] = MCPClient(vm_id, session_id)
            
            client = self.clients[client_id]
            
            # 添加服务器
            try:
                await client.add_server(server_name, remote_url, description)
                logger.info(f"✅ 服务器添加成功: {server_name} -> {client_id}")
            except Exception as e:
                # 如果这是客户机的第一个服务器且连接失败，移除客户机
                if not client.servers:
                    del self.clients[client_id]
                raise RuntimeError(f"连接失败: {e}")
    
    async def add_client(self, vm_id: str, session_id: str, remote_url: str, name: str = "default", description: str = "") -> None:
        """添加客户机（兼容旧接口）"""
        await self.add_server_to_client(vm_id, session_id, name, remote_url, description)
    
    async def remove_server_from_client(self, vm_id: str, session_id: str, server_name: str) -> bool:
        """从客户机中移除指定服务器"""
        async with self._lock:
            client_id = self._make_client_id(vm_id, session_id)
            
            if client_id in self.clients:
                client = self.clients[client_id]
                success = await client.remove_server(server_name)
                
                # 如果客户机没有任何服务器了，移除客户机
                if not client.servers:
                    del self.clients[client_id]
                    logger.info(f"🗑️ 客户机移除成功 (无服务器): {client_id}")
                
                return success
            return False
    
    async def remove_client(self, vm_id: str, session_id: str) -> bool:
        """移除整个客户机（兼容旧接口）"""
        async with self._lock:
            client_id = self._make_client_id(vm_id, session_id)
            
            if client_id in self.clients:
                await self.clients[client_id].disconnect_all()
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
        """获取所有客户机的工具列表 - 过滤掉专用于直接调用的工具"""
        all_tools = []
        
        # 专用于直接调用的工具，不应该暴露给AI
        direct_call_only_tools = {"list_all_paths"}
        
        for client in self.clients.values():
            if not client.is_any_server_connected():
                continue
                
            try:
                tools = await client.get_all_tools()
                for tool in tools:
                    # 过滤掉专用于直接调用的工具
                    if tool.name in direct_call_only_tools:
                        logger.debug(f"过滤直接调用专用工具: {tool.name}")
                        continue
                        
                    all_tools.append({
                        "client_id": client.client_id,
                        "vm_id": client.vm_id,
                        "session_id": client.session_id,
                        "server_name": tool.server_name,
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
            if not client.is_any_server_connected():
                continue
                
            try:
                resources = await client.get_all_resources()
                for resource in resources:
                    all_resources.append({
                        "client_id": client.client_id,
                        "vm_id": client.vm_id,
                        "session_id": client.session_id,
                        "server_name": resource.server_name,
                        "uri": resource.uri,
                        "name": resource.name,
                        "description": resource.description,
                        "mimeType": resource.mimeType
                    })
            except Exception as e:
                logger.warning(f"获取资源列表失败 {client.client_id}: {e}")
        
        return all_resources
    
    async def call_tool(self, vm_id: str, session_id: str, tool_name: str, 
                       arguments: Dict[str, Any], server_name: Optional[str] = None) -> Any:
        """调用指定客户机的工具"""
        client = await self.get_client(vm_id, session_id)
        if not client:
            raise RuntimeError(f"客户机不存在: {vm_id}/{session_id}")
        
        if server_name:
            # 在指定服务器上调用
            return await client.call_tool_on_server(server_name, tool_name, arguments)
        else:
            # 自动查找有该工具的服务器
            result, found_server = await client.find_tool_and_call(tool_name, arguments)
            return result
    
    async def find_tool_and_call(self, tool_name: str, arguments: Dict[str, Any], 
                                preferred_vm_id: Optional[str] = None) -> Any:
        """查找工具并调用 - 禁止AI调用专用于直接调用的工具"""
        # 专用于直接调用的工具，不允许AI调用
        direct_call_only_tools = {"list_all_paths"}
        
        if tool_name in direct_call_only_tools:
            raise RuntimeError(f"工具 '{tool_name}' 仅用于直接调用，不允许AI调用")
        
        # 查找有该工具的客户机
        candidates = []
        
        for client in self.clients.values():
            if not client.is_any_server_connected():
                continue
                
            try:
                tools = await client.get_all_tools()
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
        result, server_name = await client.find_tool_and_call(tool_name, arguments)
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        connected_count = sum(1 for c in self.clients.values() if c.is_any_server_connected())
        total_servers = sum(len(c.servers) for c in self.clients.values())
        connected_servers = sum(len(c.get_connected_servers()) for c in self.clients.values())
        total_tools = 0
        total_resources = 0
        
        for client in self.clients.values():
            for server in client.servers.values():
                if server._tools_cache:
                    total_tools += len(server._tools_cache)
                if server._resources_cache:
                    total_resources += len(server._resources_cache)
        
        return {
            "total_clients": len(self.clients),
            "connected_clients": connected_count,
            "total_servers": total_servers,
            "connected_servers": connected_servers,
            "total_tools": total_tools,
            "total_resources": total_resources,
            "discovery_enabled": False  # 简化版不支持服务发现
        }
    
    async def cleanup(self):
        """清理所有连接"""
        logger.info("🧹 清理客户机连接...")
        async with self._lock:
            for client in list(self.clients.values()):
                await client.disconnect_all()
            self.clients.clear()
        logger.info("✅ 客户机连接清理完成")