from __future__ import annotations

import os
from typing import Dict, Optional

from useit_ai_run.gui_agent.node_handler.logic_nodes.base import BaseNodeHandler
from . import create_tool, get_all_tool_names, get_tool_config


class ToolsNodeHandler(BaseNodeHandler):
    """Dispatcher for tool nodes, aligned with logic_nodes interface."""

    def handle(
        self,
        planner,  # FlowLogicPlanner (unused, but kept for consistent signature)
        current_node: Dict,
        current_state: Dict,
        screenshot_path: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        node_id = self._get_node_id(current_node)
        node_title = self._get_node_title(current_node)
        node_type = current_node.get("type")
        node_data = current_node.get("data", {})

        self._log_info(f"Processing tool node: {node_id} - {node_title}")

        # Determine the tool name
        tool_name = None
        if node_type in ("tools", "knowledge-retrieval"):
            tool_name = current_node.get("tool_name") or node_data.get("type")
        elif node_type in get_all_tool_names():
            tool_name = node_type

        if not tool_name:
            return self._error_result(current_node, current_state, "No tool_name configured for this node")

        # Merge parameters from node
        parameters = current_node.get("parameters", {}).copy()
        parameters.update(node_data)

        # Normalize common aliases
        if "purpose" in parameters:
            parameters["context_description"] = parameters.pop("purpose")
        if "scope" in parameters:
            parameters["query"] = parameters.pop("scope")

        try:
            tool_logging_dir = os.path.join(self.logging_dir, "tool_logs", tool_name)
            os.makedirs(tool_logging_dir, exist_ok=True)

            api_keys = getattr(planner, "api_keys", None) or {}
            tool = create_tool(tool_name=tool_name, api_keys=api_keys, logging_dir=tool_logging_dir)
            if not tool:
                return self._error_result(current_node, current_state, f"Tool '{tool_name}' not registered")

            # Inject vector store id if required by tool config (optional convention)
            tool_cfg = get_tool_config(tool_name)
            if tool_cfg.get("requires_vector_store") and "vector_store_ids" not in parameters:
                vsid = current_state.get("vector_store_id")
                if vsid:
                    parameters["vector_store_ids"] = [vsid]

            result = tool.execute(**parameters)

            if isinstance(result, dict) and result.get("status") == "error":
                msg = result.get("content") or result.get("error_message") or "Unknown tool error"
                return self._error_result(current_node, current_state, f"{tool_name}: {msg}")

            knowledge_summary = (result or {}).get("summary") or f"Tool '{tool_name}' executed successfully."

            updated_state = current_state.copy()
            updated_state[f"{node_id}_tool_result"] = result

            node_completion_summary = knowledge_summary

            return {
                "Observation": f"Tool node {node_id} executed. Tool: {tool_name}",
                "Reasoning": knowledge_summary,
                "Action": f"Tool '{tool_name}' finished",
                "is_node_completed": True,
                "current_state": updated_state,
                "knowledge_summary": knowledge_summary,
                "knowledge_content": result,
                "node_completion_summary": node_completion_summary,
            }

        except Exception as e:
            return self._error_result(current_node, current_state, str(e))

    def _error_result(self, current_node: Dict, current_state: Dict, message: str) -> Dict:
        node_id = self._get_node_id(current_node)
        self._log_error(f"Tool node {node_id} failed: {message}")
        updated_state = current_state.copy()
        updated_state[f"{node_id}_error"] = message
        return {
            "Observation": f"Tool node {node_id} failed.",
            "Reasoning": f"Error: {message}",
            "Action": "Error handling tool",
            "is_node_completed": True,
            "current_state": updated_state,
            "error": message,
            "node_completion_summary": f"Tool failed: {message}",
        }


__all__ = ["ToolsNodeHandler", "get_all_tool_names"]

