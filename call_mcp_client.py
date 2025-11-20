from typing import Optional, Dict, Any, Tuple

import requests
import json
import os
from pathlib import Path

from useit_ai_run.utils.logger_utils import LoggerUtils

logger = LoggerUtils(component_name="mcp_apis")

from config import app_config

DEFAULT_MCP_BASE_DIR = app_config['mcp_base_dir']
DEFAULT_MCP_CLIENT_URL = app_config['mcp_client_url']
DEFAULT_FRPC_JSON_PATH = app_config['frpc_json_path']


def register_servers_with_vm_session(
    mcp_server_url: str, vm_id: str, session_id: str, json_path: Optional[str] = None
) -> bool:
    """
    Register MCP servers from JSON file with specified vm_id and session_id
    
    Args:
        mcp_server_url: URL of the MCP client server
        vm_id: Virtual machine ID
        session_id: Session ID

        If json_path is not provided, it defaults to
        f"{}/{vm_id}_{session_id}/.useit/mcp_server_frp.json".
    
    Returns:
        bool: True if registration successful
    """
    
    json_file = Path(json_path)

    if not json_file.exists():
        logger.logger.error(f"JSON registration file not found: {json_file}")
        return False

    logger.logger.info(f"JSON file path: {json_file}")

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        servers = data.get('servers', [])
        if not servers:
            logger.logger.error("No server configurations found in JSON file")
            return False

        logger.logger.info(f"Registering {len(servers)} servers from JSON...")
        success_count = 0

        for server in servers:
            logger.logger.info(f"Registering server: {server['name']}...")
            try:
                payload = {
                    "vm_id": vm_id,
                    "session_id": session_id,
                    "name": server['name'],
                    "url": server['url'],
                    "description": server.get('description', ''),
                    "transport": server.get('transport', 'http'),
                }

                response = requests.post(f"{mcp_server_url}/clients", json=payload)
                if response.status_code == 200:
                    logger.logger.info(f"{server['name']} registered successfully")
                    success_count += 1
                else:
                    logger.logger.error(f"{server['name']} registration failed: HTTP {response.status_code}")

            except Exception as e:
                logger.logger.exception(f"Exception during registration for {server['name']}: {e}")

        logger.logger.info(f"Successfully registered {success_count}/{len(servers)} servers")
        return success_count > 0

    except Exception as e:
        logger.logger.exception(f"Failed to process JSON file: {e}")
        return False


def register_single_mcp_server(
    mcp_client_url: str,
    vm_id: str,
    session_id: str,
    server_name: str,
    server_url: str
) -> bool:
    """Register a single MCP server (aligned with simple_streaming_demo)."""
    logger.logger.info(f"Registering single MCP server: {server_name} -> {server_url}")
    try:
        payload = {
            "vm_id": vm_id,
            "session_id": session_id,
            "name": server_name,
            "url": server_url,
            "description": f"{server_name} MCP server",
            "transport": "http",
        }
        response = requests.post(f"{mcp_client_url}/clients", json=payload, timeout=10)
        if response.status_code == 200:
            logger.logger.info(f"{server_name} registered successfully")
            return True
        else:
            logger.logger.warning(f"{server_name} registration response: HTTP {response.status_code}")
            if response.status_code == 400:
                logger.logger.info("Server may already exist; continuing")
            return True
    except Exception as e:
        logger.logger.exception(f"Exception during single server registration for {server_name}: {e}")
        return False


def call_streaming_task(
    mcp_client_url: str,
    vm_id: str,
    session_id: str,
    mcp_server_name: str,
    task_description: str,
) -> Tuple[bool, Dict[str, Any]]:
    """Call streaming task and log live progress (aligned with simple_streaming_demo)."""
    try:
        task_request = {
            "vm_id": vm_id,
            "session_id": session_id,
            "mcp_server_name": mcp_server_name,
            "task_description": task_description,
        }
        response = requests.post(
            f"{mcp_client_url}/tasks/execute-stream",
            json=task_request,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=(30, 300),
        )
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.logger.error(f"Streaming request failed: {error_msg}")
            return False, {"error": error_msg}

        success, task_result = _process_sse_stream(response)
        
        return success, task_result
    
    except Exception as e:
        logger.logger.exception(f"Streaming task execution exception: {e}")
        return False, {"error": str(e)}


def _process_sse_stream(response) -> Tuple[bool, Dict[str, Any]]:
    """Simplified SSE stream processing (aligned with simple_streaming_demo)."""
    execution_steps: list = []
    task_result: Optional[Dict[str, Any]] = None
    tool_count = 0
    logger.logger.info("Start receiving event stream...")
    try:
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith('data:'):
                continue
            
            try:
                data_content = line[5:].strip()
                event_data = json.loads(data_content)
                event_type = event_data.get("type")
                data = event_data.get("data", {})
                
                if event_type == "start":
                    task_id = data.get('task_id')
                    logger.logger.info(f"Task started (ID: {task_id}) Description: {data.get('task_description', '')}")
                
                elif event_type == "tool_start":
                    tool_count += 1
                    tool_name = data.get('tool_name', 'unknown')
                    server_name = data.get('server_name', 'unknown')
                    step_number = data.get('step_number', tool_count)
                    arguments = data.get('arguments', {})
                    # logger.logger.info(f"Step {step_number}: tool '{tool_name}' started MCP server: {server_name} Arguments: {json.dumps(arguments, ensure_ascii=False)}")
                
                elif event_type == "tool_result":
                    tool_name = data.get('tool_name', 'unknown')
                    server_name = data.get('server_name', 'unknown')
                    status = data.get('status', 'unknown')
                    execution_time = data.get('execution_time', 0)
                    step_number = data.get('step_number', '?')
                    result = data.get('result', '')
                    logger.logger.info(f"Step {step_number}: tool '{tool_name}' completed MCP server: {server_name} Execution time: {execution_time:.3f}s Status: {status}")
                    execution_steps.append({
                        "step": step_number,
                        "tool_name": tool_name,
                        "status": status,
                        "execution_time": execution_time,
                        "result": result,
                    })
                
                elif event_type == "complete":
                    success = data.get('success', False)
                    final_result = data.get('final_result', '')
                    summary = data.get('summary', '')
                    total_execution_time = data.get('execution_time', 0)
                    total_steps = data.get('total_steps', 0)
                    total_token_usage = data.get('total_token_usage', {})
                    
                    
                    logger.logger.info(f"Task completed Success: {success} Total execution time: {total_execution_time:.2f}s Total steps: {total_steps} Tool calls: {len(execution_steps)}")
                    logger.logger.info(f"Task completed summary: {summary}")
                    
                    
                    task_result = {
                        "success": success,
                        "execution_steps": execution_steps,
                        "final_result": final_result,
                        "summary": summary,
                        "execution_time": total_execution_time,
                        "tool_count": len(execution_steps),
                        "total_token_usage": total_token_usage,
                    }
                    return success, task_result
                
                elif event_type == "error":
                    error_message = data.get('error_message', 'Unknown error')
                    logger.logger.error(f"Task execution error: {error_message}")
                    return False, {"error": error_message, "execution_steps": execution_steps}
                
            except json.JSONDecodeError as e:
                logger.logger.warning(f"Failed to parse event data: {e}")
                continue
        logger.logger.warning("Streaming connection ended unexpectedly")
        return False, {"error": "Streaming connection ended unexpectedly", "execution_steps": execution_steps, "tool_count": len(execution_steps)}
    except Exception as e:
        logger.logger.exception(f"Failed to process SSE stream: {e}")
        return False, {"error": f"Failed to process SSE stream: {e}"}



def execute_mcp_full_sequence(
    mcp_client_url: Optional[str],
    mcp_server_name: str,
    instruction_text: str,
    vm_id: str,
    session_id: str,
    # json_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute with the new 1-2-3 flow:
    1) Check MCP client status
    2) Register MCP servers (from JSON, if available)
    3) Execute task via streaming

    Return structure remains compatible (token_usage kept as an empty dict for now).
    """
    mcp_client_url = mcp_client_url or DEFAULT_MCP_CLIENT_URL
    assert mcp_client_url is not None, "MCP client URL must be set"

    # Step 1: Check client status
    logger.logger.info("1) Checking MCP client status...")
    if not check_mcp_client_status(mcp_client_url):
        logger.logger.error("MCP client unavailable. Please start the server first.")
        return {
            "registration_success": False,
            "is_completed": False,
            "completion_summary": "MCP client unavailable",
            "token_usage": {},
        }
    
    frpc_json_path = os.path.join(DEFAULT_MCP_BASE_DIR, f"{vm_id}_{session_id}/.useit/mcp_server_frp.json")
    
    if not frpc_json_path or not os.path.exists(frpc_json_path):
        logger.logger.warning("No JSON path provided or file not found; proceeding to task execution")
        frpc_json_path = "/home/ubuntu/workspace/gxw/useit_mcp_new/useit_mcp_test_dir/.useit/mcp_server_frp.json"

    # Step 2: Register MCP servers (from JSON if available)
    logger.logger.info(f"2) Registering MCP servers from frpc_json_path: {frpc_json_path}")
    registration_success = register_servers_with_vm_session(
        mcp_client_url, vm_id, session_id, frpc_json_path
    )
    if not registration_success:
        logger.logger.warning("Server registration failed or no config found; proceeding to task execution")
    logger.logger.info("")

    # Step 3: Execute streaming task
    logger.logger.info("3) Executing streaming task...")
    is_completed = False
    completion_summary = ""
    token_usage: Dict[str, Any] = {}
    
    try:
        success, streaming_result = call_streaming_task(
            mcp_client_url=mcp_client_url,
            vm_id=vm_id,
            session_id=session_id,
            mcp_server_name=mcp_server_name,
            task_description=instruction_text,
        )
        is_completed = bool(success)
        completion_summary = (
            streaming_result.get("summary")
            or str(streaming_result.get("final_result", ""))
            or ""
        )
        token_usage = streaming_result.get("total_token_usage", {})
    
    except Exception as e:
        logger.logger.exception(f"Streaming task execution exception: {e}")

    return {
        "registration_success": registration_success,
        "is_completed": is_completed,
        "completion_summary": completion_summary,
        "token_usage": token_usage,
    }


def check_mcp_client_status(mcp_server_url: str) -> bool:
    """Check MCP client status (richer output aligned with demo)."""
    try:
        response = requests.get(f"{mcp_server_url}/health", timeout=5)
        if response.status_code == 200:
            result = response.json()
            status_data = result.get('data', {})
            logger.logger.info(f"MCP client is healthy Connected servers: {status_data.get('connected_servers', 0)} Available tools: {status_data.get('total_tools', 0)}")
            return True
        else:
            logger.logger.warning(f"MCP client abnormal response: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.logger.error(f"Unable to connect to MCP client: {mcp_server_url}")
        return False
    except Exception as e:
        logger.logger.exception(f"Status check error: {e}")
        return False
    
    


# def calling_external_mcp_server(instruction_text: str, mcp_server_name: str, vm_id: str, session_id: str, mcp_server_url: Optional[str] = None) -> tuple:
#     """
#     Call external MCP server using the streaming interface and return
#     (is_completed, completion_summary, token_usage).
#     """
#     try:
#         mcp_client_url = mcp_server_url or DEFAULT_MCP_SERVER_URL
#         logger.info(f"Calling external MCP client at {mcp_client_url}")
#         logger.info(f"Streaming server call: {mcp_server_name} - {instruction_text}")
#         logger.info(f"Target client: {vm_id}/{session_id}")
        
#         success, result = call_streaming_task(
#             mcp_client_url=mcp_client_url,
#             vm_id=vm_id,
#             session_id=session_id,
#             mcp_server_name=mcp_server_name,
#             task_description=instruction_text,
#         )
        
#         if success:
#             token_usage = result.get("total_token_usage", {})
#             completion_summary = result.get("summary") or str(result.get("final_result", "")) or "No completion summary provided"
#             return True, completion_summary, token_usage
#         else:
#             error_msg = result.get("error", "Unknown error")
#             return False, error_msg, {}
    
#     except Exception as e:
#         error_msg = f"Unexpected error calling MCP server: {str(e)}"
#         logger.exception(error_msg)
#         return False, f"Error: {error_msg}", {}
