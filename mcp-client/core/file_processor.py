#!/usr/bin/env python3
"""
文件处理模块

负责读取、编码和处理文件输入（图片、文本等）
支持从文件清单中选择相关文件，并进行编码处理
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import base64

from .api_models import FilesInputConfig, FileReference

logger = logging.getLogger(__name__)


class FileProcessor:
    """文件处理器 - 处理文件读取、编码和选择"""

    # 支持的文件类型
    SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
    SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml', '.log'}

    @staticmethod
    async def process_files_input(
        files_config: FilesInputConfig,
        task_description: Optional[str] = None,
        anthropic_api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        处理文件输入配置，返回编码后的文件列表

        Args:
            files_config: 文件输入配置
            task_description: 任务描述（用于AI选择文件）
            anthropic_api_key: Anthropic API密钥（用于AI选择文件）

        Returns:
            编码后的文件数据列表
        """
        try:
            # 1. 读取文件清单
            manifest = FileProcessor._load_manifest(files_config.file_manifest_path)

            # 2. 选择文件
            selected_files = await FileProcessor._select_files(
                manifest=manifest,
                files_config=files_config,
                task_description=task_description,
                anthropic_api_key=anthropic_api_key
            )

            logger.info(f"从 {len(manifest.get('files', []))} 个文件中选择了 {len(selected_files)} 个")

            # 3. 编码文件
            encoded_files = await FileProcessor._encode_files(
                files_directory=files_config.files_directory,
                selected_files=selected_files,
                manifest=manifest
            )

            logger.info(f"成功编码 {len(encoded_files)} 个文件")

            return encoded_files

        except Exception as e:
            logger.error(f"处理文件输入失败: {e}")
            raise

    @staticmethod
    def _load_manifest(manifest_path: str) -> Dict[str, Any]:
        """加载文件清单JSON"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            if 'files' not in manifest:
                raise ValueError("清单文件必须包含 'files' 字段")

            return manifest

        except FileNotFoundError:
            raise FileNotFoundError(f"清单文件不存在: {manifest_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"清单文件JSON格式错误: {e}")

    @staticmethod
    async def _select_files(
        manifest: Dict[str, Any],
        files_config: FilesInputConfig,
        task_description: Optional[str] = None,
        anthropic_api_key: Optional[str] = None
    ) -> List[str]:
        """
        选择相关文件

        Returns:
            选中的文件路径列表
        """
        all_files = [f["path"] for f in manifest.get("files", [])]

        # 如果启用AI自动选择且提供了必要参数
        if files_config.auto_select and task_description and anthropic_api_key:
            try:
                from .file_selector import IntelligentFileSelector

                selector = IntelligentFileSelector(anthropic_api_key)
                selected_files = await selector.select_files(
                    task_description=task_description,
                    file_manifest=manifest,
                    max_files=files_config.max_files
                )

                logger.info(f"AI选择了 {len(selected_files)} 个相关文件")
                return selected_files

            except Exception as e:
                logger.warning(f"AI文件选择失败，使用所有文件: {e}")
                # 降级到使用所有文件

        # 默认：使用所有文件（限制数量）
        selected_files = all_files[:files_config.max_files]
        logger.info(f"使用前 {len(selected_files)} 个文件")

        return selected_files

    @staticmethod
    async def _encode_files(
        files_directory: str,
        selected_files: List[str],
        manifest: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """编码选中的文件"""
        encoded_files = []

        for file_path in selected_files:
            full_path = Path(files_directory) / file_path

            if not full_path.exists():
                logger.warning(f"文件不存在，跳过: {full_path}")
                continue

            try:
                # 从清单中查找文件描述
                description = FileProcessor._find_file_description(file_path, manifest)

                # 编码文件
                file_data = await FileProcessor._encode_single_file(
                    full_path=full_path,
                    relative_path=file_path,
                    description=description
                )

                if file_data:
                    encoded_files.append(file_data)

            except Exception as e:
                logger.error(f"编码文件失败 {file_path}: {e}")
                continue

        return encoded_files

    @staticmethod
    def _find_file_description(file_path: str, manifest: Dict[str, Any]) -> Optional[str]:
        """从清单中查找文件描述"""
        for file_info in manifest.get("files", []):
            if file_info.get("path") == file_path:
                return file_info.get("description")
        return None

    @staticmethod
    async def _encode_single_file(
        full_path: Path,
        relative_path: str,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """编码单个文件"""
        extension = full_path.suffix.lower()

        # 图片文件
        if extension in FileProcessor.SUPPORTED_IMAGE_EXTENSIONS:
            return await FileProcessor._encode_image(
                full_path, relative_path, description
            )

        # 文本文件
        elif extension in FileProcessor.SUPPORTED_TEXT_EXTENSIONS:
            return await FileProcessor._encode_text(
                full_path, relative_path, description
            )

        else:
            logger.warning(f"不支持的文件类型: {extension} ({relative_path})")
            return None

    @staticmethod
    async def _encode_image(
        full_path: Path,
        relative_path: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """编码图片文件为base64"""
        try:
            with open(full_path, 'rb') as f:
                image_data = f.read()
                base64_data = base64.b64encode(image_data).decode('utf-8')

            # 确定MIME类型
            extension = full_path.suffix.lower()[1:]  # 去掉点号
            mime_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'bmp': 'image/bmp'
            }
            mime_type = mime_type_map.get(extension, f'image/{extension}')

            logger.info(f"成功编码图片: {relative_path} ({len(base64_data)} bytes)")

            return {
                "path": relative_path,
                "type": "image",
                "mime_type": mime_type,
                "content": base64_data,
                "description": description
            }

        except Exception as e:
            logger.error(f"编码图片失败 {relative_path}: {e}")
            raise

    @staticmethod
    async def _encode_text(
        full_path: Path,
        relative_path: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """读取文本文件内容"""
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.info(f"成功读取文本文件: {relative_path} ({len(content)} chars)")

            return {
                "path": relative_path,
                "type": "text",
                "content": content,
                "description": description
            }

        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(full_path, 'r', encoding='gbk') as f:
                    content = f.read()
                logger.info(f"使用GBK编码读取文本文件: {relative_path}")

                return {
                    "path": relative_path,
                    "type": "text",
                    "content": content,
                    "description": description
                }
            except Exception as e:
                logger.error(f"读取文本文件失败 {relative_path}: {e}")
                raise
        except Exception as e:
            logger.error(f"读取文本文件失败 {relative_path}: {e}")
            raise
