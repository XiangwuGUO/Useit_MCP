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

# Assuming slicer.py is in the same directory
from slicer import slice_audio_by_beats

# 1. Create an MCP server instance with a title and description
mcp = FastMCP(
    "AudioSlicer",
    title="Audio Slicing Service", 
    description="An MCP server with a tool to slice audio files based on beats.",
    port=8002  # 避免与其他服务器冲突
)

# 2. Define the audio slicing function as an MCP tool
@mcp.tool()
def slice_audio(
    audio_file_content_base64: str,
    filename: str,
    segment_duration_s: float,
    session_id: str = None,
) -> dict:
    """
    Slices an audio file into segments based on detected beats.

    The segments are cut at beat markers to be as close as possible
    to the desired segment duration.

    Args:
        audio_file_content_base64: The content of the audio file, encoded in base64.
        filename: The original name of the audio file (e.g., 'track.mp3').
        segment_duration_s: The target duration for each segment in seconds.
        session_id: Session ID for workspace isolation (optional).

    Returns:
        A dictionary containing a message and a list of paths to the sliced audio files.
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

            return {
                "message": f"Successfully sliced audio into {len(final_segment_paths)} segments.",
                "segment_paths": final_segment_paths
            }
    except Exception as e:
        # It's good practice to return structured errors
        return {
            "error": "Failed to process audio file.",
            "details": str(e)
        }

if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from server_base import start_mcp_server
    
    start_mcp_server(mcp, 8002, "AudioSlicer") 