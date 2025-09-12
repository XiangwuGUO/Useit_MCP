import os
import base64
import tempfile
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Import base directory manager
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from base_dir_decorator import get_base_dir_manager

# 导入企业标准服务器基类
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from base_server import StandardMCPServer, ServerConfigs

# Assuming slicer.py is in the same directory
from slicer import slice_audio_by_beats


# 使用原有架构，直接创建FastMCP实例
mcp = FastMCP(
    "audio_slicer",
    title="Audio Slicing Service", 
    description="An MCP server with a tool to slice audio files based on beats.",
    port=8002
)


@mcp.tool()
def slice_audio(
    audio_file_content_base64: str,
    filename: str,
    segment_duration_s: float,
    session_id: str = None,
) -> dict:

    """
    音频切片实现函数
    
    基于节拍检测将音频文件切分为多个片段，每个片段尽可能接近目标时长。

    Args:
        audio_file_content_base64: base64编码的音频文件内容
        filename: 原始音频文件名 (例如: 'track.mp3')
        segment_duration_s: 每个片段的目标时长（秒）
        session_id: 会话ID，用于工作空间隔离（可选）

    Returns:
        包含处理结果和片段路径列表的字典
    """
    try:
        # Use a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Decode the base64 content and write to a temporary file
            audio_data = base64.b64decode(audio_file_content_base64)
            input_audio_path = os.path.join(temp_dir, filename)
            with open(input_audio_path, 'wb') as f:
                f.write(audio_data)

            # Define an output directory for the final segments
            processing_output_dir = os.path.join(temp_dir, "segments")
            
            # Call the existing slicing logic
            segment_paths = slice_audio_by_beats(
                audio_path=input_audio_path,
                segment_duration_s=segment_duration_s,
                output_dir=processing_output_dir
            )

            # Use base directory manager to get output directory
            base_dir_manager = get_base_dir_manager()
            final_output_dir = base_dir_manager.get_base_dir() / "audio_output"
            
            # Create output directory and copy results
            if final_output_dir.exists():
                shutil.rmtree(final_output_dir)  # Clean up previous runs
            shutil.copytree(processing_output_dir, final_output_dir)

            # Get the final paths relative to the base directory
            final_segment_paths = [str(final_output_dir / os.path.basename(p)) for p in segment_paths]

            # Build relative paths for new_files tracking
            base_manager = get_base_dir_manager()
            base_path = Path(base_manager.get_base_dir())
            new_files = {}
            
            for full_path in final_segment_paths:
                try:
                    relative_path = Path(full_path).relative_to(base_path)
                    new_files[str(relative_path)] = "音频片段"
                except ValueError:
                    # If can't make relative, use filename
                    new_files[os.path.basename(full_path)] = "音频片段"

            return {
                "message": f"Successfully sliced audio into {len(final_segment_paths)} segments.",
                "segment_paths": final_segment_paths,
                "new_files": new_files
            }
    except Exception as e:
        # It's good practice to return structured errors
        return {
            "error": "Failed to process audio file.",
            "details": str(e),
            "new_files": {}  # 确保即使出错也有new_files变量
        }

if __name__ == "__main__":
    # 保持兼容性，使用原有启动方式
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from server_base import start_mcp_server
    
    start_mcp_server(mcp, 8002, "audio_slicer") 