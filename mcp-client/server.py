#!/usr/bin/env python3
"""
简化的MCP Gateway Server
移除FRP服务发现功能，专注于核心MCP客户机管理
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# 导入核心模块
from core.api_models import *
from core.client_manager import ClientManager
from core.task_executor import execute_intelligent_task, execute_smart_tool_call
from config.settings import settings, validate_required_settings
from utils.helpers import format_duration, timing_decorator

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=settings.log_file
)
logger = logging.getLogger(__name__)

# 全局客户机管理器
client_manager = ClientManager()

# 服务器启动时间
server_start_time = datetime.now()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 MCP Gateway Server 启动 (简化版)")
    validate_required_settings()
    logger.info("✅ 客户机管理器已就绪")
    
    yield
    
    # 关闭时
    logger.info("🛑 MCP Gateway Server 关闭")
    await client_manager.cleanup()


# 创建 FastAPI 应用
app = FastAPI(
    title="MCP Gateway Server",
    description="统一的MCP客户机网关服务器 (简化版)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 健康检查和系统信息
# ============================================================================

@app.get("/", response_model=APIResponse)
async def root():
    """根路径 - 系统信息"""
    return APIResponse(
        success=True,
        message="MCP Gateway Server (简化版) 正在运行",
        data={
            "service": "MCP Gateway Server",
            "version": "1.0.0",
            "mode": "simplified",
            "uptime": format_duration(int((datetime.now() - server_start_time).total_seconds())),
            "endpoints": {
                "health": "/health",
                "stats": "/stats", 
                "docs": "/docs",
                "clients": "/clients",
                "tools": "/tools",
                "smart_tool_call": "/tools/smart-call"
            }
        }
    )


@app.get("/health", response_model=APIResponse)
async def health_check():
    """健康检查"""
    try:
        stats = client_manager.get_stats()
        status = "healthy" if stats["connected_clients"] >= 0 else "degraded"
        
        return APIResponse(
            success=True,
            message=f"服务器运行正常 - {status}",
            data={
                "status": status,
                "connected_clients": stats["connected_clients"],
                "total_servers": stats["total_servers"],
                "connected_servers": stats["connected_servers"],
                "total_tools": stats["total_tools"],
                "uptime": format_duration(int((datetime.now() - server_start_time).total_seconds()))
            }
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return APIResponse(
            success=False,
            message="服务器异常",
            data={"status": "unhealthy", "error": str(e)}
        )


@app.get("/stats", response_model=APIResponse)
async def get_stats():
    """获取系统统计信息"""
    try:
        stats = client_manager.get_stats()
        
        # 计算运行时长
        uptime_seconds = int((datetime.now() - server_start_time).total_seconds())
        uptime_str = format_duration(uptime_seconds)
        
        return APIResponse(
            success=True,
            message="统计信息获取成功",
            data={
                **stats,
                "uptime": uptime_str,
                "uptime_seconds": uptime_seconds,
                "server_start_time": server_start_time.isoformat(),
                "mode": "simplified",
                "settings": {
                    "claude_model": settings.claude_model,
                    "client_timeout": settings.client_timeout,
                    "task_timeout": settings.task_timeout
                }
            }
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {e}")


# ============================================================================
# 客户机管理
# ============================================================================

@app.post("/clients", response_model=APIResponse)
async def add_client(client_info: ClientInfo):
    """添加MCP客户机服务器"""
    try:
        await client_manager.add_server_to_client(
            client_info.vm_id,
            client_info.session_id,
            client_info.name,
            client_info.url,
            client_info.description
        )
        
        logger.info(f"✅ 服务器添加成功: {client_info.name} -> {client_info.vm_id}/{client_info.session_id}")
        
        return APIResponse(
            success=True,
            message="服务器添加成功",
            data={
                "vm_id": client_info.vm_id,
                "session_id": client_info.session_id,
                "server_name": client_info.name,
                "url": client_info.url,
                "description": client_info.description
            }
        )
    except Exception as e:
        logger.error(f"添加服务器失败: {e}")
        raise HTTPException(status_code=400, detail=f"添加服务器失败: {e}")


@app.get("/clients", response_model=APIResponse)
async def list_clients():
    """列出所有客户机"""
    try:
        clients = await client_manager.get_all_clients()
        
        # 添加详细的服务器信息
        detailed_clients = []
        for client_status in clients:
            client = await client_manager.get_client(client_status.vm_id, client_status.session_id)
            if client:
                server_details = []
                for server_name, server in client.servers.items():
                    server_details.append({
                        "name": server_name,
                        "url": server.remote_url,
                        "description": server.description,
                        "connected": server.connected,
                        "last_seen": server.last_seen.isoformat()
                    })
                
                detailed_clients.append({
                    "vm_id": client_status.vm_id,
                    "session_id": client_status.session_id,
                    "status": client_status.status,
                    "server_count": client_status.server_count,
                    "connected_servers": client_status.connected_servers,
                    "tool_count": client_status.tool_count,
                    "resource_count": client_status.resource_count,
                    "last_seen": client_status.last_seen,
                    "servers": server_details
                })
        
        return APIResponse(
            success=True,
            message=f"获取到 {len(clients)} 个客户机",
            data=detailed_clients
        )
    except Exception as e:
        logger.error(f"获取客户机列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取客户机列表失败: {e}")


@app.delete("/clients/{vm_id}/{session_id}", response_model=APIResponse)
async def remove_client(vm_id: str, session_id: str):
    """移除整个客户机"""
    try:
        success = await client_manager.remove_client(vm_id, session_id)
        
        if success:
            return APIResponse(
                success=True,
                message="客户机移除成功",
                data={"vm_id": vm_id, "session_id": session_id}
            )
        else:
            raise HTTPException(status_code=404, detail="客户机不存在")
            
    except Exception as e:
        logger.error(f"移除客户机失败: {e}")
        raise HTTPException(status_code=500, detail=f"移除客户机失败: {e}")


@app.delete("/clients/{vm_id}/{session_id}/servers/{server_name}", response_model=APIResponse)
async def remove_server(vm_id: str, session_id: str, server_name: str):
    """从客户机中移除指定服务器"""
    try:
        success = await client_manager.remove_server_from_client(vm_id, session_id, server_name)
        
        if success:
            return APIResponse(
                success=True,
                message="服务器移除成功",
                data={"vm_id": vm_id, "session_id": session_id, "server_name": server_name}
            )
        else:
            raise HTTPException(status_code=404, detail="客户机或服务器不存在")
            
    except Exception as e:
        logger.error(f"移除服务器失败: {e}")
        raise HTTPException(status_code=500, detail=f"移除服务器失败: {e}")


# ============================================================================
# 工具和资源管理
# ============================================================================

@app.get("/tools", response_model=APIResponse)
async def list_tools():
    """列出所有可用工具"""
    try:
        tools = await client_manager.get_all_tools()
        return APIResponse(
            success=True,
            message=f"获取到 {len(tools)} 个工具",
            data=tools
        )
    except Exception as e:
        logger.error(f"获取工具列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取工具列表失败: {e}")


@app.get("/resources", response_model=APIResponse) 
async def list_resources():
    """列出所有可用资源"""
    try:
        resources = await client_manager.get_all_resources()
        return APIResponse(
            success=True,
            message=f"获取到 {len(resources)} 个资源",
            data=resources
        )
    except Exception as e:
        logger.error(f"获取资源列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资源列表失败: {e}")


@app.post("/tools/call", response_model=APIResponse)
@timing_decorator
async def call_tool(tool_call: ToolCall):
    """调用工具"""
    try:
        logger.info(f"🔧 调用工具: {tool_call.tool_name} on {tool_call.vm_id}/{tool_call.session_id}")
        if tool_call.server_name:
            logger.info(f"   指定服务器: {tool_call.server_name}")
        
        result = await client_manager.call_tool(
            tool_call.vm_id,
            tool_call.session_id,
            tool_call.tool_name,
            tool_call.arguments,
            tool_call.server_name
        )
        
        return APIResponse(
            success=True,
            message=f"工具 {tool_call.tool_name} 执行成功",
            data={
                "tool_name": tool_call.tool_name,
                "vm_id": tool_call.vm_id,
                "session_id": tool_call.session_id,
                "server_name": tool_call.server_name,
                "result": result
            }
        )
    except Exception as e:
        logger.error(f"工具调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"工具调用失败: {e}")


@app.post("/tools/find", response_model=APIResponse)
@timing_decorator
async def find_and_call_tool(tool_call: ToolFindCall):
    """查找并调用工具"""
    try:
        logger.info(f"🔍 查找并调用工具: {tool_call.tool_name}")
        
        result = await client_manager.find_tool_and_call(
            tool_call.tool_name,
            tool_call.arguments,
            tool_call.preferred_vm_id
        )
        
        return APIResponse(
            success=True,
            message=f"工具 {tool_call.tool_name} 执行成功",
            data={
                "tool_name": tool_call.tool_name,
                "preferred_vm_id": tool_call.preferred_vm_id,
                "result": result
            }
        )
    except Exception as e:
        logger.error(f"工具查找调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"工具查找调用失败: {e}")


@app.post("/tools/smart-call", response_model=APIResponse)
@timing_decorator
async def smart_call_tool(smart_call: SmartToolCall):
    """智能工具调用 - 使用AI根据描述生成参数并执行工具"""
    try:
        logger.info(f"🧠 智能调用服务器: {smart_call.mcp_server_name} - {smart_call.task_description[:50]}...")
        
        result = await execute_smart_tool_call(
            client_manager,
            smart_call.mcp_server_name,
            smart_call.task_description,
            smart_call.vm_id,
            smart_call.session_id
        )
        
        return APIResponse(
            success=result.success,
            message=f"智能工具调用{'成功' if result.success else '失败'}",
            data=result.dict()
        )
    except Exception as e:
        logger.error(f"智能工具调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能工具调用失败: {e}")


# ============================================================================
# 智能任务执行
# ============================================================================

@app.post("/tasks/execute", response_model=APIResponse)
@timing_decorator
async def execute_task(task: TaskRequest):
    """执行智能任务"""
    try:
        logger.info(f"🧠 执行智能任务: {task.task_description[:100]}...")
        
        result = await execute_intelligent_task(
            client_manager,
            task.vm_id,
            task.session_id, 
            task.mcp_server_name,
            task.task_description,
            task.context
        )
        
        return APIResponse(
            success=True,
            message="智能任务执行完成",
            data={
                "task_description": task.task_description,
                "vm_id": task.vm_id,
                "session_id": task.session_id,
                "mcp_server_name": task.mcp_server_name,
                "result": result
            }
        )
    except Exception as e:
        logger.error(f"智能任务执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能任务执行失败: {e}")


# ============================================================================
# 服务器注册 (用于简化的FRP注册)
# ============================================================================

@app.post("/servers/register", response_model=APIResponse)
async def register_server(server_info: ServerRegistrationInfo):
    """注册MCP服务器 (用于FRP注册)"""
    try:
        # 提取服务器信息
        name = server_info.name
        url = server_info.url
        description = server_info.description
        
        if not name or not url:
            raise ValueError("name 和 url 是必需的")
        
        # 使用服务器名称作为vm_id和session_id（兼容旧行为）
        await client_manager.add_server_to_client(name, "auto", name, url, description)
        
        logger.info(f"✅ 服务器注册成功: {name} -> {url}")
        
        return APIResponse(
            success=True,
            message="服务器注册成功",
            data={
                "name": name,
                "url": url,
                "description": description,
                "registered_as": f"{name}/auto"
            }
        )
    except Exception as e:
        logger.error(f"服务器注册失败: {e}")
        raise HTTPException(status_code=400, detail=f"服务器注册失败: {e}")


# ============================================================================
# 启动服务器
# ============================================================================

def main():
    """启动服务器"""
    print("🚀 启动 MCP Gateway Server (简化版)")
    print(f"📍 地址: http://localhost:{settings.port}")
    print(f"📚 文档: http://localhost:{settings.port}/docs")
    print(f"🏥 健康检查: http://localhost:{settings.port}/health")
    print("=" * 60)
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )


if __name__ == "__main__":
    main()