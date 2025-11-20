"""
Word Executor MCP Server
Two-Stage Word Automation Pipeline via MCP

Stage 1: Vision LLM analyzes Word screenshot + user prompt → generates modification instructions
Stage 2: Read document → Search paragraph → Generate PowerShell code → Execute COM operations on Word
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pipeline_manager import ExcelAutomationPipeline  # Will use same pipeline class, works for Word too
from llm.load_api_key import load_api_keys

# Server configuration
SERVER_NAME = "word_executor"
SERVER_PORT = 8005

# Create MCP server
mcp = FastMCP(
    name=SERVER_NAME,
    instructions="Word automation service using enhanced two-stage pipeline: Vision analysis → Document search → Paragraph location → Code generation → Execution"
)

# Get workspace directory
def get_workspace_dir() -> Path:
    """Get workspace directory from environment or default"""
    workspace = os.environ.get("WORD_WORKSPACE_DIR")
    if workspace:
        return Path(workspace).expanduser().resolve()
    default_path = Path.cwd() / "word_workspace"
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path.resolve()

WORKSPACE_DIR = get_workspace_dir()

# Initialize pipeline
pipeline = ExcelAutomationPipeline(workspace_dir=WORKSPACE_DIR)  # Reuses same class for Word

# Load API keys
try:
    api_keys = load_api_keys()
except Exception as e:
    print(f"Warning: Could not load API keys: {e}")
    api_keys = None


@mcp.tool()
def run_full_pipeline(
    word_screenshot: str = Field(..., description="Word document screenshot image (file path or base64 encoded string with 'data:image' prefix)"),
    word_path: str = Field(..., description="Path to the Word file (.docx) to be modified"),
    user_prompt: Optional[str] = Field(None, description="Optional user prompt/requirements (will be combined with image analysis)"),
    llm_model: str = Field("gpt-4o", description="LLM model to use (must support vision for stage 1)"),
    max_retries: int = Field(3, description="Maximum retry attempts for stage 2 code execution")
) -> Dict[str, Any]:
    """
    Run complete two-stage Word automation pipeline

    This tool performs end-to-end Word automation with enhanced paragraph location:

    Stage 1 - Vision Analysis:
      - Analyzes Word screenshot using Vision LLM
      - Combines with user prompt to understand requirements
      - Generates detailed modification instructions with location keywords (modify_prompt.txt)

    Stage 2 - Enhanced Code Generation & Execution:
      - Reads complete Word document
      - Searches for target paragraph using keywords
      - Generates PowerShell code with precise paragraph location
      - Executes code to modify Word via COM automation
      - Automatically retries on errors with feedback loop

    Args:
        word_screenshot: Path to screenshot file or base64 image data
        word_path: Path to Word file (.docx) to modify
        user_prompt: Additional user requirements (optional)
        llm_model: LLM model name (default: gpt-4o)
        max_retries: Max retries for stage 2 (default: 3)

    Returns:
        {
            "success": bool,
            "message": str,
            "data": {
                "stage1": {...},  # Stage 1 results
                "stage2": {...},  # Stage 2 results (includes paragraph location)
                "modify_prompt_path": str,
                "word_path": str
            },
            "error": str (if failed)
        }

    Examples:
        - run_full_pipeline(
            word_screenshot="/path/to/screenshot.png",
            word_path="/path/to/document.docx",
            user_prompt="Change font to Microsoft YaHei and make it bold"
          )
    """
    try:
        # Resolve paths
        word_path_resolved = Path(word_path).resolve()

        # Handle image input
        if word_screenshot.startswith("data:image"):
            # Base64 encoded image
            image_input = word_screenshot
        else:
            # File path
            image_input = Path(word_screenshot).resolve()
            if not image_input.exists():
                return {
                    "success": False,
                    "message": "Screenshot file not found",
                    "error": f"File does not exist: {word_screenshot}"
                }

        # Check Word file exists
        if not word_path_resolved.exists():
            return {
                "success": False,
                "message": "Word file not found",
                "error": f"File does not exist: {word_path}"
            }

        # Prepare template path
        template_path = Path(__file__).parent / "prompt_template.md"
        if not template_path.exists():
            return {
                "success": False,
                "message": "Prompt template not found",
                "error": f"Template file missing: {template_path}"
            }

        # Run pipeline
        print(f"\n{'='*80}")
        print(f"Word Executor MCP Server - Running Full Pipeline")
        print(f"{'='*80}")
        print(f"Workspace: {WORKSPACE_DIR}")
        print(f"Screenshot: {word_screenshot}")
        print(f"Word File: {word_path_resolved}")
        print(f"User Prompt: {user_prompt or '(none)'}")
        print(f"LLM Model: {llm_model}")
        print(f"{'='*80}\n")

        result = pipeline.run_full_pipeline(
            image_input=image_input,
            excel_path=word_path_resolved,  # pipeline still uses excel_path param name
            template_path=template_path,
            llm_model=llm_model,
            max_retries=max_retries,
            api_keys=api_keys
        )

        if result["success"]:
            return {
                "success": True,
                "message": "Pipeline executed successfully",
                "data": {
                    "stage1": {
                        "token_usage": result["stage1_result"].get("token_usage"),
                        "prompt_generated": True,
                        "saved_to": result["stage1_result"].get("saved_to")
                    },
                    "stage2": {
                        "attempts": result["stage2_result"].get("attempts"),
                        "execution_success": True,
                        "generated_code": result["stage2_result"].get("generated_code", "")[:500] + "..."  # Truncate for response
                    },
                    "modify_prompt_path": result["modify_prompt_path"],
                    "word_path": str(word_path_resolved)
                }
            }
        else:
            return {
                "success": False,
                "message": "Pipeline execution failed",
                "error": result.get("error", "Unknown error"),
                "data": {
                    "stage1": result.get("stage1_result"),
                    "stage2": result.get("stage2_result")
                }
            }

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return {
            "success": False,
            "message": "Pipeline execution error",
            "error": str(e),
            "detail": error_detail
        }


if __name__ == "__main__":
    from server_base import start_mcp_server

    print("=" * 80)
    print(f"Word Executor MCP Server")
    print("=" * 80)
    print(f"Server Name: {SERVER_NAME}")
    print(f"Port: {SERVER_PORT}")
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"Mode: Enhanced Two-Stage Pipeline (Vision → Document Search → Paragraph Location → Code → Execution)")
    print("=" * 80)

    start_mcp_server(mcp, SERVER_PORT, SERVER_NAME)
