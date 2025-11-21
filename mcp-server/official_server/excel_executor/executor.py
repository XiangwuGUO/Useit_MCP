"""
代码执行引擎
在沙箱环境中安全执行生成的代码
"""

import subprocess
import time
import tempfile
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import re


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    error: str
    generated_files: List[Path]
    execution_time: float
    code_used: str


class CodeExecutor:
    """代码执行器"""

    def __init__(self, workspace_dir: Path, max_timeout: int = 300):
        self.workspace_dir = workspace_dir
        self.max_timeout = max_timeout
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        code: str,
        language: str = "PowerShell",
        timeout: int = 60
    ) -> ExecutionResult:
        """执行代码

        Args:
            code: 要执行的代码
            language: 代码语言
            timeout: 超时时间（秒）

        Returns:
            ExecutionResult: 执行结果
        """
        # 限制超时时间
        timeout = min(timeout, self.max_timeout)

        # 验证代码安全性
        if not self._validate_code_safety(code, language):
            return ExecutionResult(
                success=False,
                output="",
                error="代码包含不安全的操作，执行被拒绝",
                generated_files=[],
                execution_time=0.0,
                code_used=code
            )

        # 记录开始前的文件
        files_before = set(self.workspace_dir.glob("*"))

        # 根据语言执行
        start_time = time.time()

        if language.lower() == "powershell":
            result = self._execute_powershell(code, timeout)
        elif language.lower() == "python":
            result = self._execute_python(code, timeout)
        else:
            return ExecutionResult(
                success=False,
                output="",
                error=f"不支持的语言: {language}",
                generated_files=[],
                execution_time=0.0,
                code_used=code
            )

        execution_time = time.time() - start_time

        # 检测生成的文件
        files_after = set(self.workspace_dir.glob("*"))
        generated_files = list(files_after - files_before)

        return ExecutionResult(
            success=result["success"],
            output=result["output"],
            error=result["error"],
            generated_files=generated_files,
            execution_time=round(execution_time, 2),
            code_used=code
        )

    def _execute_powershell(self, code: str, timeout: int) -> dict:
        """执行PowerShell代码"""
        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.ps1',
            delete=False,
            encoding='utf-8-sig'  # UTF-8 with BOM for PowerShell compatibility
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            # 执行PowerShell
            result = subprocess.run(
                ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
                cwd=str(self.workspace_dir)
            )

            success = result.returncode == 0
            output = result.stdout.strip()
            error = result.stderr.strip()

            return {
                "success": success,
                "output": output,
                "error": error if not success else ""
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"执行超时（{timeout}秒）"
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"执行失败: {str(e)}"
            }
        finally:
            # 清理临时文件
            try:
                Path(script_path).unlink()
            except:
                pass

    def _execute_python(self, code: str, timeout: int) -> dict:
        """执行Python代码"""
        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            # 执行Python
            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
                cwd=str(self.workspace_dir)
            )

            success = result.returncode == 0
            output = result.stdout.strip()
            error = result.stderr.strip()

            return {
                "success": success,
                "output": output,
                "error": error if not success else ""
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"执行超时（{timeout}秒）"
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"执行失败: {str(e)}"
            }
        finally:
            # 清理临时文件
            try:
                Path(script_path).unlink()
            except:
                pass

    def _validate_code_safety(self, code: str, language: str) -> bool:
        """验证代码安全性

        检查代码中是否包含危险操作
        """
        code_lower = code.lower()

        # 危险命令黑名单
        dangerous_patterns = [
            # 系统命令
            r'\brm\s+-rf\b',
            r'\bformat\b.*\bc:\b',
            r'\bdel\b.*\/[sq]',
            r'\bremove-item\b.*-recurse.*-force',

            # 网络操作
            r'\binvoke-webrequest\b',
            r'\bwget\b',
            r'\bcurl\b',
            r'\bstart-process\b.*http',

            # 注册表操作
            r'\bnew-itemproperty\b.*hklm',
            r'\bset-itemproperty\b.*hklm',
            r'\breg\s+add\b',

            # 危险的系统调用
            r'\bshutdown\b',
            r'\brestart-computer\b',
            r'\bstop-computer\b',
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, code_lower):
                return False

        # 检查是否尝试访问工作区外的路径
        # 允许访问工作区和临时目录
        workspace_str = str(self.workspace_dir).lower()

        # 提取所有路径
        path_patterns = [
            r'["\']([a-z]:\\[^"\']+)["\']',  # Windows绝对路径
            r'["\']([/][^"\']+)["\']',  # Unix绝对路径
        ]

        for pattern in path_patterns:
            matches = re.finditer(pattern, code_lower)
            for match in matches:
                path = match.group(1)
                # 如果路径不在工作区内，拒绝
                if workspace_str not in path and 'temp' not in path and 'tmp' not in path:
                    # 允许常见的系统路径用于Excel COM
                    allowed_system = ['program files', 'windows', 'system32']
                    if not any(allowed in path for allowed in allowed_system):
                        return False

        return True

    def save_code(self, code: str, language: str) -> Path:
        """保存代码到文件

        Args:
            code: 代码内容
            language: 代码语言

        Returns:
            保存的文件路径
        """
        # 生成文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        ext = "ps1" if language.lower() == "powershell" else "py"
        filename = f"excel_code_{timestamp}.{ext}"

        # 保存到工作区
        code_file = self.workspace_dir / filename
        # PowerShell 使用 UTF-8 with BOM，Python 使用普通 UTF-8
        encoding = 'utf-8-sig' if language.lower() == "powershell" else 'utf-8'
        code_file.write_text(code, encoding=encoding)

        return code_file

    def get_workspace_info(self) -> dict:
        """获取工作区信息"""
        files = list(self.workspace_dir.glob("*"))

        return {
            "workspace_dir": str(self.workspace_dir),
            "file_count": len(files),
            "files": [f.name for f in files]
        }
