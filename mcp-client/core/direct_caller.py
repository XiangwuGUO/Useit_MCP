#!/usr/bin/env python3
"""
直接调用模块

提供跳过LLM直接调用MCP Server工具的功能
支持自动处理文件输入和metadata注入
"""

import logging
import httpx
import time
from uuid import uuid4
from typing import Dict, Any, Optional

from .api_models import DirectToolCallRequest, DirectToolCallResult
from .file_processor import FileProcessor
from .client_manager import ClientManager

logger = logging.getLogger(__name__)


class DirectMCPCaller:
    """直接MCP调用器 - 跳过LLM，直接调用MCP Server"""

    def __init__(self, client_manager: ClientManager, anthropic_api_key: Optional[str] = None):
        """
        初始化直接调用器

        Args:
            client_manager: 客户端管理器
            anthropic_api_key: Anthropic API密钥（用于AI文件选择）
        """
        self.client_manager = client_manager
        self.anthropic_api_key = anthropic_api_key

    async def call_tool_directly(
        self,
        request: DirectToolCallRequest
    ) -> DirectToolCallResult:
        """
        直接调用MCP工具（跳过LLM）

        Args:
            request: 直接调用请求

        Returns:
            调用结果
        """
        start_time = time.time()

        try:
            logger.info(f"🎯 直接调用工具: {request.tool_name}")
            logger.info(f"   MCP Server: {request.mcp_server_name}")
            logger.info(f"   VM/Session: {request.vm_id}/{request.session_id}")

            # 1. 获取MCP客户端
            client = await self.client_manager.get_client(
                request.vm_id,
                request.session_id
            )

            if not client:
                raise ValueError(
                    f"客户端不存在: {request.vm_id}/{request.session_id}"
                )

            # 2. 查找指定的MCP Server
            server = client.servers.get(request.mcp_server_name)
            if not server or not server.connected:
                raise ValueError(
                    f"MCP Server '{request.mcp_server_name}' 未连接或不存在"
                )

            logger.info(f"   Server URL: {server.remote_url}")

            # 3. 构建完整的工具参数（合并arguments和metadata）
            final_arguments = await self._build_tool_arguments(request)

            logger.info(f"   参数数量: {len(request.arguments)}")
            logger.info(f"   包含metadata: {request.metadata is not None}")
            logger.info(f"   包含文件: {request.files_input is not None}")

            # 4. 直接调用MCP工具
            result = await self._call_mcp_tool(
                server_url=server.remote_url,
                tool_name=request.tool_name,
                arguments=final_arguments
            )

            execution_time = time.time() - start_time

            logger.info(f"✅ 工具调用成功，耗时 {execution_time:.2f}秒")

            # 5. 构建返回结果
            files_count = 0
            if final_arguments.get("metadata", {}).get("files"):
                files_count = len(final_arguments["metadata"]["files"])

            return DirectToolCallResult(
                success=True,
                tool_name=request.tool_name,
                mcp_server_name=request.mcp_server_name,
                vm_id=request.vm_id,
                session_id=request.session_id,
                result=result,
                execution_time_seconds=execution_time,
                metadata_included=request.metadata is not None,
                files_count=files_count
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ 直接调用失败: {e}")

            return DirectToolCallResult(
                success=False,
                tool_name=request.tool_name,
                mcp_server_name=request.mcp_server_name,
                vm_id=request.vm_id,
                session_id=request.session_id,
                result=None,
                execution_time_seconds=execution_time,
                metadata_included=False,
                files_count=0,
                error_message=str(e)
            )

    async def _build_tool_arguments(
        self,
        request: DirectToolCallRequest
    ) -> Dict[str, Any]:
        """
        构建完整的工具参数

        最终参数结构：
        {
            // 业务参数（平铺）
            "param1": "value1",
            "param2": "value2",

            // metadata（固定字段名）
            "metadata": {
                "user_id": "...",
                "files": [...],
                "custom_data": {...}
            }
        }
        """
        # 复制业务参数
        final_arguments = dict(request.arguments)

        # 构建metadata对象
        metadata_obj = {}

        # 1. 添加用户提供的metadata
        if request.metadata:
            metadata_obj.update(request.metadata)
            logger.info(f"   添加用户metadata: {list(request.metadata.keys())}")

        # 2. 处理文件输入
        if request.files_input:
            logger.info("   处理文件输入...")

            # 如果启用AI自动选择，需要任务描述
            task_description = None
            if request.files_input.auto_select:
                # 尝试从arguments中提取任务描述（常见字段：instruction, task, description）
                task_description = (
                    request.arguments.get("instruction") or
                    request.arguments.get("task") or
                    request.arguments.get("description") or
                    request.arguments.get("task_description")
                )

                if task_description:
                    logger.info(f"   启用AI文件选择，任务描述: {task_description[:50]}...")
                else:
                    logger.warning("   启用了AI文件选择，但未找到任务描述字段，将使用所有文件")

            files_data = await FileProcessor.process_files_input(
                files_config=request.files_input,
                task_description=task_description,
                anthropic_api_key=self.anthropic_api_key
            )

            metadata_obj["files"] = files_data
            logger.info(f"   添加 {len(files_data)} 个文件到metadata")

        # 3. 添加到参数中
        if metadata_obj:
            final_arguments["metadata"] = metadata_obj

        return final_arguments

    async def _call_mcp_tool(
        self,
        server_url: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        直接调用MCP Server的工具

        使用MCP协议的tools/call方法
        """
        # 构建MCP请求
        mcp_request = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        # 确保URL以/mcp结尾
        if not server_url.endswith("/mcp"):
            server_url = f"{server_url}/mcp"

        logger.info(f"   调用MCP端点: {server_url}")

        # 发送HTTP请求
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await client.post(
                    server_url,
                    json=mcp_request,
                    headers={"Content-Type": "application/json"}
                )

                # 检查HTTP状态码
                if response.status_code != 200:
                    error_text = response.text[:500]  # 限制错误信息长度
                    raise RuntimeError(
                        f"MCP Server HTTP错误: {response.status_code} - {error_text}"
                    )

                # 解析响应
                result_data = response.json()

                # 检查JSON-RPC错误
                if "error" in result_data:
                    error_info = result_data["error"]
                    error_message = error_info.get("message", "未知错误")
                    error_code = error_info.get("code", -1)
                    raise RuntimeError(
                        f"MCP工具调用失败 [code={error_code}]: {error_message}"
                    )

                # 返回结果
                return result_data.get("result")

            except httpx.TimeoutException:
                raise RuntimeError("MCP Server调用超时（300秒）")
            except httpx.RequestError as e:
                raise RuntimeError(f"MCP Server连接失败: {e}")
