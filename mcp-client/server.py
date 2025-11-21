#!/usr/bin/env python3
"""
MCP Gateway Server with LangChain Integration

简化版MCP网关服务器，使用LangChain处理智能任务执行
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import httpx

# 导入核心模块
from core.api_models import *
from core.client_manager import ClientManager
from core.langchain_executor import LangChainMCPExecutor
from core.streaming_executor import StreamingLangChainExecutor
from core.stream_models import *
from core.direct_caller import DirectMCPCaller  # 新增：直接调用模块
from config.settings import settings, validate_required_settings
from utils.helpers import format_duration, timing_decorator

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局管理器
client_manager = ClientManager()
langchain_executor: Optional[LangChainMCPExecutor] = None
streaming_executor: Optional[StreamingLangChainExecutor] = None
direct_caller: Optional[DirectMCPCaller] = None  # 新增：直接调用器

# 服务器启动时间
server_start_time = datetime.now()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global langchain_executor, streaming_executor, direct_caller

    # 启动时
    logger.info("🚀 MCP Gateway Server 启动 (LangChain版)")
    validate_required_settings()

    # 初始化LangChain执行器
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    debug_enabled = os.getenv("MCP_DEBUG_ENABLED", "false").lower() in ("true", "1", "yes")

    if anthropic_api_key:
        langchain_executor = LangChainMCPExecutor(client_manager, anthropic_api_key)
        streaming_executor = StreamingLangChainExecutor(client_manager, anthropic_api_key, debug_enabled=debug_enabled)
        logger.info("✅ LangChain MCP Executor 已初始化")
        logger.info(f"✅ Streaming LangChain MCP Executor 已初始化 (调试模式: {'开启' if debug_enabled else '关闭'})")
    else:
        logger.warning("⚠️ 未设置ANTHROPIC_API_KEY，智能任务执行功能将不可用")

    # 初始化直接调用器（总是可用）
    direct_caller = DirectMCPCaller(client_manager, anthropic_api_key)
    logger.info("✅ Direct MCP Caller 已初始化")

    logger.info("✅ 客户机管理器已就绪")

    yield

    # 关闭时
    logger.info("🛑 MCP Gateway Server 关闭")
    await client_manager.cleanup()
    if langchain_executor:
        await langchain_executor.cleanup()
    if streaming_executor:
        await streaming_executor.cleanup()


# 创建 FastAPI 应用
app = FastAPI(
    title="MCP Gateway Server",
    description="基于LangChain的MCP客户机网关服务器",
    version="2.0.0",
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
        message="MCP Gateway Server (LangChain版) 正在运行",
        data={
            "service": "MCP Gateway Server",
            "version": "2.0.0",
            "mode": "langchain",
            "uptime": format_duration(int((datetime.now() - server_start_time).total_seconds())),
            "langchain_enabled": langchain_executor is not None,
            "endpoints": {
                "health": "/health",
                "stats": "/stats", 
                "docs": "/docs",
                "clients": "/clients",
                "tools": "/tools",
                "tasks": "/tasks/execute",
                "stream_tasks": "/tasks/execute-stream"
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
                "langchain_ready": langchain_executor is not None,
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
                "mode": "langchain",
                "langchain_executor_ready": langchain_executor is not None,
                "anthropic_api_configured": bool(os.getenv("ANTHROPIC_API_KEY"))
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


@app.post("/tools/call-direct", response_model=APIResponse)
@timing_decorator
async def call_tool_direct(request: DirectToolCallRequest):
    """
    直接调用MCP工具（跳过LLM推理）

    适用场景：
    - MCP Server只有单个工具
    - 参数已准备好，不需要AI生成
    - 需要传递额外的metadata（图片、文件等）

    请求体示例：
    {
        "vm_id": "vm1",
        "session_id": "session1",
        "mcp_server_name": "excel_executor",
        "tool_name": "generate_excel",
        "arguments": {
            "instruction": "生成销售报表",
            "output_path": "/output/report.xlsx"
        },
        "metadata": {
            "user_id": "user123"
        },
        "files_input": {
            "files_directory": "/data/input",
            "file_manifest_path": "/data/input/manifest.json",
            "auto_select": false,
            "max_files": 5
        }
    }
    """
    if not direct_caller:
        raise HTTPException(
            status_code=503,
            detail="Direct caller未初始化"
        )

    try:
        logger.info(f"🎯 直接调用MCP工具: {request.tool_name}")
        logger.info(f"   MCP Server: {request.mcp_server_name}")

        # 调用直接调用器
        result = await direct_caller.call_tool_directly(request)

        return APIResponse(
            success=result.success,
            message=f"工具{'成功' if result.success else '失败'}调用",
            data=result.model_dump()
        )

    except Exception as e:
        logger.error(f"直接调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"直接调用失败: {e}")


@app.post("/filesystem/list-all-paths", response_model=APIResponse)
@timing_decorator
async def list_all_paths(tool_call: ToolCall):
    """直接调用filesystem服务器的list_all_paths工具，返回所有文件和文件夹的绝对路径列表
    
    请求体格式:
    {
        "vm_id": "your_vm_id",
        "session_id": "your_session_id",
        "tool_name": "list_all_paths",
        "arguments": {},
        "server_name": "filesystem"  // 可选，指定具体服务器
    }
    """
    try:
        logger.info(f"🗂️ 获取文件系统所有路径: {tool_call.vm_id}/{tool_call.session_id}")
        
        # 确保调用的是list_all_paths工具
        if tool_call.tool_name != "list_all_paths":
            raise ValueError(f"此接口只支持list_all_paths工具，但收到: {tool_call.tool_name}")
        
        # 特殊处理：通过HTTP调用MCP服务器的直接端点
        # 因为list_all_paths不是注册的MCP工具，使用专用HTTP端点
        if tool_call.tool_name == "list_all_paths":
            try:
                # 获取对应的MCP服务器URL
                client = await client_manager.get_client(tool_call.vm_id, tool_call.session_id)
                if not client:
                    raise RuntimeError(f"客户机不存在: {tool_call.vm_id}/{tool_call.session_id}")
                
                # 查找filesystem服务器的URL
                filesystem_server = None
                for server_name, server in client.servers.items():
                    if server_name == "filesystem" or "filesystem" in server_name.lower():
                        filesystem_server = server
                        break
                
                if not filesystem_server or not filesystem_server.connected:
                    raise RuntimeError("filesystem服务器未连接")
                
                # 构造HTTP端点URL
                server_base_url = filesystem_server.remote_url.replace('/mcp', '').rstrip('/')
                direct_endpoint_url = f"{server_base_url}/direct/list-all-paths"
                
                logger.info(f"调用filesystem服务器直接端点: {direct_endpoint_url}")
                
                # 发送HTTP GET请求
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    response = await http_client.get(direct_endpoint_url)
                    
                if response.status_code == 200:
                    result = response.json()
                    # 提取路径数据
                    if isinstance(result, dict) and result.get('success') and 'data' in result:
                        paths_data = result['data'].get('paths', [])
                    else:
                        paths_data = []
                else:
                    raise RuntimeError(f"HTTP调用失败: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(f"HTTP调用list_all_paths失败: {e}")
                raise HTTPException(status_code=500, detail=f"调用list_all_paths失败: {e}")
        else:
            # 其他工具使用标准MCP调用
            result = await client_manager.call_tool(
                tool_call.vm_id,
                tool_call.session_id, 
                tool_call.tool_name,
                tool_call.arguments or {},
                tool_call.server_name
            )
            paths_data = result
        
        return APIResponse(
            success=True,
            message="获取路径列表成功",
            data={
                "vm_id": tool_call.vm_id,
                "session_id": tool_call.session_id,
                "server_name": tool_call.server_name,
                "paths": paths_data
            }
        )
    except Exception as e:
        logger.error(f"获取路径列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取路径列表失败: {e}")


# ============================================================================
# LangChain智能任务执行
# ============================================================================

@app.post("/tasks/execute", response_model=APIResponse)
@timing_decorator
async def execute_task(task: TaskRequest):
    """执行智能任务 (使用LangChain)"""
    if not langchain_executor:
        raise HTTPException(
            status_code=503, 
            detail="LangChain执行器未初始化，请检查ANTHROPIC_API_KEY配置"
        )
    
    try:
        logger.info(f"🧠 执行LangChain智能任务: {task.task_description[:100]}...")
        
        result = await langchain_executor.execute_task(task)
        
        return APIResponse(
            success=True,
            message="智能任务执行完成",
            data={
                "task_description": task.task_description,
                "vm_id": task.vm_id,
                "session_id": task.session_id,
                "mcp_server_name": task.mcp_server_name,
                "result": result.model_dump(),
                "new_files": result.new_files
            }
        )
    except Exception as e:
        logger.error(f"智能任务执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能任务执行失败: {e}")


@app.post("/tools/smart-call", response_model=APIResponse)
@timing_decorator
async def smart_call_tool(smart_call: SmartToolCall):
    """智能工具调用 (简化版，使用单步LangChain调用)"""
    if not langchain_executor:
        raise HTTPException(
            status_code=503,
            detail="LangChain执行器未初始化，请检查ANTHROPIC_API_KEY配置"
        )
    
    try:
        logger.info(f"🧠 智能调用: {smart_call.mcp_server_name} - {smart_call.task_description[:50]}...")
        
        # 转换为TaskRequest
        task_request = TaskRequest(
            vm_id=smart_call.vm_id,
            session_id=smart_call.session_id,
            mcp_server_name=smart_call.mcp_server_name,
            task_description=smart_call.task_description
        )
        
        result = await langchain_executor.execute_task(task_request)
        
        # 转换为SmartToolResult格式
        smart_result = SmartToolResult(
            success=result.success,
            mcp_server_name=smart_call.mcp_server_name,
            selected_tool_name=result.execution_steps[0]["tool_name"] if result.execution_steps else None,
            vm_id=smart_call.vm_id,
            session_id=smart_call.session_id,
            task_description=smart_call.task_description,
            result=result.final_result,
            completion_summary=result.summary,
            execution_time_seconds=result.execution_time_seconds,
            error_message=result.error_message,
            new_files=result.new_files
        )
        
        return APIResponse(
            success=result.success,
            message=f"智能工具调用{'成功' if result.success else '失败'}",
            data=smart_result.model_dump()
        )
    except Exception as e:
        logger.error(f"智能工具调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能工具调用失败: {e}")


# ============================================================================
# 流式任务执行 (SSE)
# ============================================================================

@app.post("/tasks/execute-stream")
@timing_decorator
async def execute_task_streaming(task: TaskRequest):
    """流式执行智能任务 (SSE)"""
    if not streaming_executor:
        raise HTTPException(
            status_code=503, 
            detail="流式执行器未初始化，请检查ANTHROPIC_API_KEY配置"
        )
    
    async def generate_sse_stream():
        """生成SSE流"""
        try:
            logger.info(f"🌊 开始流式执行任务: {task.task_description[:100]}...")
            print(f"🔥🔥🔥 [SERVER] 即将调用 streaming_executor.execute_task_streaming")
            print(f"🔥🔥🔥 [SERVER] streaming_executor类型: {type(streaming_executor)}")
            
            async for event in streaming_executor.execute_task_streaming(task):
                # 转换为SSE消息
                sse_message = SSEMessage(
                    id=event.timestamp,
                    event=event.type,
                    data=json.dumps(event.model_dump(), ensure_ascii=False)
                )
                
                yield sse_message.to_sse_string()
                
                # 确保缓冲区刷新
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"流式任务执行异常: {e}")
            
            # 发送错误事件
            error_event = StreamEvent(
                type="error",
                data={
                    "error_message": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            sse_message = SSEMessage(
                event="error",
                data=json.dumps(error_event.model_dump(), ensure_ascii=False)
            )
            
            yield sse_message.to_sse_string()
    
    return StreamingResponse(
        generate_sse_stream(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.get("/tasks/active", response_model=APIResponse)
async def get_active_tasks():
    """获取活跃任务状态"""
    if not streaming_executor:
        return APIResponse(
            success=False,
            message="流式执行器未初始化",
            data={}
        )
    
    active_tasks = streaming_executor.get_active_tasks()
    
    return APIResponse(
        success=True,
        message=f"获取到 {len(active_tasks)} 个活跃任务",
        data={
            "active_tasks": [task.model_dump() for task in active_tasks.values()],
            "task_count": len(active_tasks)
        }
    )


@app.get("/tasks/{task_id}/status", response_model=APIResponse)
async def get_task_status(task_id: str):
    """获取指定任务状态"""
    if not streaming_executor:
        raise HTTPException(
            status_code=503,
            detail="流式执行器未初始化"
        )
    
    active_tasks = streaming_executor.get_active_tasks()
    
    if task_id not in active_tasks:
        raise HTTPException(
            status_code=404,
            detail=f"任务 {task_id} 不存在"
        )
    
    task_status = active_tasks[task_id]
    
    return APIResponse(
        success=True,
        message="任务状态获取成功",
        data=task_status.model_dump()
    )


@app.get("/debug/session", response_model=APIResponse)
async def get_debug_session():
    """获取调试会话信息"""
    from core.debug_logger import debug_logger
    
    session_info = debug_logger.get_session_info()
    
    return APIResponse(
        success=True,
        message="调试会话信息获取成功",
        data=session_info or {"enabled": False, "session_dir": None}
    )


@app.post("/debug/toggle", response_model=APIResponse) 
async def toggle_debug(enabled: bool = True):
    """切换调试模式"""
    from core.debug_logger import debug_logger
    
    if enabled:
        debug_logger.enable_debug()
        message = "调试模式已开启"
    else:
        debug_logger.disable_debug()
        message = "调试模式已关闭"
    
    return APIResponse(
        success=True,
        message=message,
        data=debug_logger.get_session_info() or {"enabled": False}
    )


# ============================================================================
# 服务器注册 (兼容性接口)
# ============================================================================

@app.post("/servers/register", response_model=APIResponse)
async def register_server(server_info: ServerRegistrationInfo):
    """注册MCP服务器 (兼容性接口)"""
    try:
        name = server_info.name
        url = server_info.url
        description = server_info.description
        
        if not name or not url:
            raise ValueError("name 和 url 是必需的")
        
        # 使用服务器名称作为vm_id和session_id
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
    print("🚀 启动 MCP Gateway Server (LangChain版)")
    print(f"📍 地址: http://localhost:{settings.port}")
    print(f"📚 文档: http://localhost:{settings.port}/docs")
    print(f"🏥 健康检查: http://localhost:{settings.port}/health")
    print(f"🧠 LangChain集成: {'启用' if os.getenv('ANTHROPIC_API_KEY') else '需要配置ANTHROPIC_API_KEY'}")
    print("=" * 60)
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )


if __name__ == "__main__":
    MCP_DEBUG_ENABLED="true"
    main()