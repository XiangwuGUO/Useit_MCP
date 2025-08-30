import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List

from openai import OpenAI

from . import BaseTool, register_tool


@register_tool("web-search")
class WebSearchTool(BaseTool):
    """Web search tool using OpenAI Responses API with web_search_preview."""

    def __init__(self, name: str = "web-search", api_keys: Optional[Dict] = None, logging_dir: Optional[str] = None, **kwargs):
        super().__init__(name=name, api_keys=api_keys, logging_dir=logging_dir)
        self.model = kwargs.get("model", "gpt-5")
        self.max_output_tokens = int(kwargs.get("max_output_tokens", 1200))

        api_key = None
        if api_keys:
            api_key = api_keys.get("OPENAI_API_KEY") or api_keys.get("openai")
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for web search tool")

        # Optional: support custom base_url via env
        base_url = os.environ.get("OPENAI_BASE_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

    def execute(
        self,
        query: str,
        context_description: Optional[str] = None,
        overall_task_query: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        start = time.time()

        prompt_parts: List[str] = []
        if overall_task_query:
            prompt_parts.append(f"Overall goal: {overall_task_query}")
        if context_description:
            prompt_parts.append(f"Purpose: {context_description}")
        prompt_parts.append(f"Task: {query}")

        # Keep input simple, Responses API will invoke web_search_preview tool
        input_text = "\n".join(prompt_parts)

        # Special kwargs for gpt-5 family
        extra_kwargs = {}
        if str(self.model).startswith("gpt-5"):
            extra_kwargs = {"reasoning": {"effort": "minimal"}, "text": {"verbosity": "medium"}}

        try:
            response = self.client.responses.create(
                model=self.model,
                input=input_text,
                tools=[{"type": "web_search_preview"}],
                max_output_tokens=self.max_output_tokens,
                **extra_kwargs,
            )

            text = self._extract_text(response)
            summary = self._summarize(text, query)
            sources = self._extract_sources(text)

            result = {
                "tool_name": self.name,
                "status": "success",
                "query": query,
                "context": context_description,
                "overall_task_context": overall_task_query,
                "content": text,
                "summary": summary,
                "sources": sources,
                "model_used": getattr(response, "model", self.model),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(time.time() - start, 2),
            }

            if self.logging_dir:
                self._log_result(result)

            return result

        except Exception as e:
            return {
                "tool_name": self.name,
                "status": "error",
                "query": query,
                "context": context_description,
                "overall_task_context": overall_task_query,
                "content": f"Web search failed: {e}",
                "summary": f"Search failed for '{query}'",
                "sources": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(time.time() - start, 2),
            }

    def _extract_text(self, response) -> str:
        # Try friendly accessor first
        text = getattr(response, "output_text", None)
        if text:
            return text
        # Fallback to output structure
        outputs = getattr(response, "output", None) or []
        for out in outputs:
            if getattr(out, "type", "") in ("thinking", "reasoning"):
                continue
            content = getattr(out, "content", None) or []
            if content and hasattr(content[0], "text"):
                return content[0].text
        return ""

    def _summarize(self, text: str, query: str) -> str:
        if not text:
            return f"No results for '{query}'"
        # Simple heuristic summary: first sentence or trimmed head
        head = text.strip().split("\n", 1)[0]
        head = head.strip()
        if len(head) > 240:
            head = head[:237] + "..."
        return head

    def _extract_sources(self, text: str) -> List[str]:
        if not text:
            return []
        import re
        url_pattern = r"https?://[^\s\)]+(?:[^\s\)\.]|(?<=\w)\.)"
        urls = re.findall(url_pattern, text)
        seen = set()
        deduped = []
        for u in urls:
            u = u.rstrip('.,;:!?')
            domain = re.search(r"https?://([^/]+)", u)
            d = domain.group(1) if domain else u
            if d not in seen:
                seen.add(d)
                deduped.append(u)
            if len(deduped) >= 5:
                break
        return deduped

    def _log_result(self, result: Dict[str, Any]):
        try:
            os.makedirs(self.logging_dir, exist_ok=True)
            path = os.path.join(self.logging_dir, f"websearch_{int(time.time())}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
