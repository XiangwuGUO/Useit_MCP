#!/usr/bin/env python3
"""
智能文件选择器

使用Claude API根据任务描述和文件清单，智能选择相关文件
"""

import json
import logging
import re
from typing import List, Dict, Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


class IntelligentFileSelector:
    """智能文件选择器 - 使用AI选择相关文件"""

    def __init__(self, anthropic_api_key: str):
        """
        初始化文件选择器

        Args:
            anthropic_api_key: Anthropic API密钥
        """
        self.model = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=anthropic_api_key,
            temperature=0
        )

    async def select_files(
        self,
        task_description: str,
        file_manifest: Dict[str, Any],
        max_files: int = 5
    ) -> List[str]:
        """
        根据任务描述和文件清单，智能选择相关文件

        Args:
            task_description: 任务描述
            file_manifest: 文件清单，格式：
                {
                    "files": [
                        {"path": "file1.png", "description": "..."},
                        {"path": "file2.txt", "description": "..."}
                    ]
                }
            max_files: 最多选择的文件数量

        Returns:
            选中的文件路径列表
        """
        try:
            # 构建选择提示
            prompt = self._build_selection_prompt(
                task_description,
                file_manifest,
                max_files
            )

            # 调用Claude API
            logger.info("调用Claude API进行文件选择...")
            response = await self.model.ainvoke([HumanMessage(content=prompt)])

            # 解析选择结果
            selected_files = self._parse_selection_response(response.content)

            # 验证选择的文件
            valid_files = self._validate_selected_files(
                selected_files,
                file_manifest
            )

            logger.info(f"AI选择了 {len(valid_files)} 个相关文件")

            return valid_files[:max_files]

        except Exception as e:
            logger.error(f"智能文件选择失败: {e}")
            raise

    def _build_selection_prompt(
        self,
        task_description: str,
        file_manifest: Dict[str, Any],
        max_files: int
    ) -> str:
        """构建文件选择提示"""

        # 格式化文件清单
        files_list = []
        for idx, file_info in enumerate(file_manifest.get("files", []), 1):
            path = file_info.get("path", "")
            description = file_info.get("description", "无描述")
            files_list.append(f"{idx}. {path}\n   描述: {description}")

        files_text = "\n".join(files_list)

        prompt = f"""You are a file selection assistant. Based on the task description and available files, select the most relevant files.

**Task Description:**
{task_description}

**Available Files:**
{files_text}

**Instructions:**
- Analyze which files are most relevant to the task
- Select up to {max_files} files
- Return ONLY a JSON array of file paths
- Use exact file paths as shown above

**Response Format (JSON array only):**
["path/to/file1.ext", "path/to/file2.ext"]

Your selection:"""

        return prompt

    def _parse_selection_response(self, response_content: str) -> List[str]:
        """解析Claude的选择结果"""

        try:
            # 尝试直接解析JSON
            if response_content.strip().startswith('['):
                return json.loads(response_content.strip())

            # 使用正则提取JSON数组
            json_match = re.search(r'\[.*?\]', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)

            # 如果没有找到JSON，尝试按行解析
            lines = response_content.strip().split('\n')
            file_paths = []
            for line in lines:
                line = line.strip()
                # 移除引号和逗号
                line = line.strip('",[]')
                if line and not line.startswith(('#', '//', '--')):
                    file_paths.append(line)

            if file_paths:
                logger.warning("未找到JSON格式，使用行解析")
                return file_paths

            logger.warning("无法解析AI响应，返回空列表")
            return []

        except json.JSONDecodeError as e:
            logger.error(f"解析JSON失败: {e}")
            return []
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            return []

    def _validate_selected_files(
        self,
        selected_files: List[str],
        file_manifest: Dict[str, Any]
    ) -> List[str]:
        """验证选择的文件是否存在于清单中"""

        manifest_paths = {f.get("path") for f in file_manifest.get("files", [])}
        valid_files = []

        for file_path in selected_files:
            if file_path in manifest_paths:
                valid_files.append(file_path)
            else:
                logger.warning(f"选择的文件不在清单中: {file_path}")

        return valid_files
