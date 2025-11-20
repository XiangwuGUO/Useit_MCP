"""
Excel Executor MCP Server
Two-Stage Excel Automation Pipeline via MCP

Stage 1: Vision LLM analyzes Excel screenshot + user prompt → generates modification instructions
Stage 2: Code LLM generates PowerShell code → executes COM operations on Excel
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pipeline_manager import ExcelAutomationPipeline
from llm.load_api_key import load_api_keys

# Server configuration
SERVER_NAME = "excel_executor"
SERVER_PORT = 8004

# Create MCP server
mcp = FastMCP(
    name=SERVER_NAME,
    instructions="Excel automation service using two-stage pipeline: Vision analysis → Code generation → Execution"
)

# Get workspace directory
def get_workspace_dir() -> Path:
    """Get workspace directory from environment or default"""
    workspace = os.environ.get("EXCEL_WORKSPACE_DIR")
    if workspace:
        return Path(workspace).expanduser().resolve()
    default_path = Path.cwd() / "excel_workspace"
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path.resolve()

WORKSPACE_DIR = get_workspace_dir()

# Initialize pipeline
pipeline = ExcelAutomationPipeline(workspace_dir=WORKSPACE_DIR)

# Load API keys
try:
    api_keys = load_api_keys()
except Exception as e:
    print(f"Warning: Could not load API keys: {e}")
    api_keys = None


@mcp.tool()
def run_full_pipeline(
    excel_screenshot: str = Field(..., description="Excel screenshot image (file path or base64 encoded string with 'data:image' prefix)"),
    excel_path: str = Field(..., description="Path to the Excel file to be modified"),
    user_prompt: Optional[str] = Field(None, description="Optional user prompt/requirements (will be combined with image analysis)"),
    llm_model: str = Field("gpt-4o", description="LLM model to use (must support vision for stage 1)"),
    max_retries: int = Field(3, description="Maximum retry attempts for stage 2 code execution")
) -> Dict[str, Any]:
    """
    Run complete two-stage Excel automation pipeline

    This tool performs end-to-end Excel automation:

    Stage 1 - Vision Analysis:
      - Analyzes Excel screenshot using Vision LLM
      - Combines with user prompt to understand requirements
      - Generates detailed modification instructions (modify_prompt.txt)

    Stage 2 - Code Generation & Execution:
      - Generates PowerShell code based on modification instructions
      - Executes code to modify Excel via COM automation
      - Automatically retries on errors with feedback loop

    Args:
        excel_screenshot: Path to screenshot file or base64 image data
        excel_path: Path to Excel file to modify
        user_prompt: Additional user requirements (optional)
        llm_model: LLM model name (default: gpt-4o)
        max_retries: Max retries for stage 2 (default: 3)

    Returns:
        {
            "success": bool,
            "message": str,
            "data": {
                "stage1": {...},  # Stage 1 results
                "stage2": {...},  # Stage 2 results
                "modify_prompt_path": str,
                "excel_path": str
            },
            "error": str (if failed)
        }

    Examples:
        - run_full_pipeline(
            excel_screenshot="/path/to/screenshot.png",
            excel_path="/path/to/data.xlsx",
            user_prompt="Add a summary row at the bottom with totals"
          )
    """
    try:
        # Resolve paths
        excel_path_resolved = Path(excel_path).resolve()

        # Handle image input
        if excel_screenshot.startswith("data:image"):
            # Base64 encoded image
            image_input = excel_screenshot
        else:
            # File path
            image_input = Path(excel_screenshot).resolve()
            if not image_input.exists():
                return {
                    "success": False,
                    "message": "Screenshot file not found",
                    "error": f"File does not exist: {excel_screenshot}"
                }

        # Check Excel file exists
        if not excel_path_resolved.exists():
            return {
                "success": False,
                "message": "Excel file not found",
                "error": f"File does not exist: {excel_path}"
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
        print(f"Excel Executor MCP Server - Running Full Pipeline")
        print(f"{'='*80}")
        print(f"Workspace: {WORKSPACE_DIR}")
        print(f"Screenshot: {excel_screenshot}")
        print(f"Excel File: {excel_path_resolved}")
        print(f"User Prompt: {user_prompt or '(none)'}")
        print(f"LLM Model: {llm_model}")
        print(f"{'='*80}\n")

        result = pipeline.run_full_pipeline(
            image_input=image_input,
            excel_path=excel_path_resolved,
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
                    "excel_path": str(excel_path_resolved)
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
    print(f"Excel Executor MCP Server")
    print("=" * 80)
    print(f"Server Name: {SERVER_NAME}")
    print(f"Port: {SERVER_PORT}")
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"Mode: Two-Stage Pipeline (Vision Analysis → Code Generation → Execution)")
    print("=" * 80)

    start_mcp_server(mcp, SERVER_PORT, SERVER_NAME)
