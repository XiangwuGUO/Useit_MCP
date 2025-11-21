#!/usr/bin/env python3
"""
Metadata注入器

在LangChain工具调用中自动注入metadata，对LLM透明
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class MetadataInjector:
    """Metadata注入器 - 自动为工具调用注入metadata"""

    @staticmethod
    def wrap_tools_with_metadata(
        tools: List[BaseTool],
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[BaseTool]:
        """
        包装工具列表，为每个工具调用自动注入metadata

        Args:
            tools: 原始工具列表
            metadata: 要注入的metadata

        Returns:
            包装后的工具列表
        """
        if not metadata:
            logger.info("没有metadata需要注入，返回原始工具")
            return tools

        logger.info(f"为 {len(tools)} 个工具注入metadata")
        logger.info(f"Metadata keys: {list(metadata.keys())}")

        wrapped_tools = []

        for tool in tools:
            try:
                wrapped_tool = MetadataInjector._wrap_single_tool(tool, metadata)
                wrapped_tools.append(wrapped_tool)
            except Exception as e:
                logger.error(f"包装工具失败 {tool.name}: {e}")
                # 失败时使用原始工具
                wrapped_tools.append(tool)

        logger.info(f"成功包装 {len(wrapped_tools)} 个工具")

        return wrapped_tools

    @staticmethod
    def _wrap_single_tool(
        tool: BaseTool,
        metadata: Dict[str, Any]
    ) -> BaseTool:
        """包装单个工具，注入metadata"""

        # 保存原始的invoke方法
        original_invoke = tool.invoke
        original_ainvoke = tool.ainvoke if hasattr(tool, 'ainvoke') else None

        # 创建包装的invoke方法
        def wrapped_invoke(tool_input: Any, *args, **kwargs):
            """同步invoke包装"""
            # 注入metadata
            injected_input = MetadataInjector._inject_metadata(
                tool_input, metadata, tool.name
            )

            # 调用原始方法
            return original_invoke(injected_input, *args, **kwargs)

        # 创建包装的ainvoke方法
        async def wrapped_ainvoke(tool_input: Any, *args, **kwargs):
            """异步invoke包装"""
            # 注入metadata
            injected_input = MetadataInjector._inject_metadata(
                tool_input, metadata, tool.name
            )

            # 调用原始方法
            if original_ainvoke:
                if asyncio.iscoroutinefunction(original_ainvoke):
                    return await original_ainvoke(injected_input, *args, **kwargs)
                else:
                    return original_ainvoke(injected_input, *args, **kwargs)
            else:
                # 如果没有ainvoke，使用invoke
                return original_invoke(injected_input, *args, **kwargs)

        # 替换方法
        tool.invoke = wrapped_invoke
        if original_ainvoke or hasattr(tool, 'ainvoke'):
            tool.ainvoke = wrapped_ainvoke

        logger.debug(f"工具 {tool.name} 已包装metadata注入")

        return tool

    @staticmethod
    def _inject_metadata(
        tool_input: Any,
        metadata: Dict[str, Any],
        tool_name: str
    ) -> Any:
        """
        将metadata注入到工具输入中

        Args:
            tool_input: 原始工具输入（可能是dict或其他类型）
            metadata: 要注入的metadata
            tool_name: 工具名称（用于日志）

        Returns:
            注入metadata后的工具输入
        """
        # 如果tool_input是字典
        if isinstance(tool_input, dict):
            # 复制一份，避免修改原始数据
            injected_input = dict(tool_input)

            # 添加metadata字段
            injected_input["metadata"] = metadata

            logger.debug(
                f"为工具 {tool_name} 注入metadata "
                f"(keys: {list(metadata.keys())})"
            )

            return injected_input

        # 如果tool_input是Pydantic模型
        elif hasattr(tool_input, 'model_dump'):
            # 转换为字典
            input_dict = tool_input.model_dump()
            input_dict["metadata"] = metadata

            logger.debug(
                f"为工具 {tool_name} 注入metadata到Pydantic模型 "
                f"(keys: {list(metadata.keys())})"
            )

            return input_dict

        # 其他类型，尝试包装成字典
        else:
            logger.warning(
                f"工具 {tool_name} 的输入类型不支持metadata注入: "
                f"{type(tool_input)}"
            )

            # 尝试包装
            return {
                "input": tool_input,
                "metadata": metadata
            }

    @staticmethod
    def build_metadata_from_files(
        files_data: List[Dict[str, Any]],
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        从文件数据和用户metadata构建完整的metadata对象

        Args:
            files_data: 文件数据列表
            user_metadata: 用户提供的额外metadata

        Returns:
            完整的metadata对象
        """
        metadata = {}

        # 添加文件数据
        if files_data:
            metadata["files"] = files_data
            logger.info(f"添加 {len(files_data)} 个文件到metadata")

        # 添加用户metadata
        if user_metadata:
            metadata.update(user_metadata)
            logger.info(f"添加用户metadata: {list(user_metadata.keys())}")

        return metadata
