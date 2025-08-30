"""
Web Search FastMCP Server

功能：
- 基于 OpenAI Responses API 的网页搜索
- 使用 web_search_preview 工具进行实时搜索
- 返回搜索结果、摘要和来源链接

依赖：
- openai

运行（开发调试）：
    uv run mcp dev examples/servers/web_search/server.py

生产建议：使用 streamable-http
    uv run examples/servers/web_search/server.py

环境变量：
- OPENAI_API_KEY：OpenAI API 密钥（必需）
- OPENAI_BASE_URL：可选的自定义 API 基础 URL
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP


# -----------------------------------------------------------------------------
# 数据模型（结构化输出）
# -----------------------------------------------------------------------------

class WebSearchRequest(BaseModel):
    query: str = Field(description="搜索查询")
    context_description: Optional[str] = Field(default=None, description="搜索上下文描述")
    overall_task_query: Optional[str] = Field(default=None, description="总体任务查询")
    model: str = Field(default="gpt-5", description="使用的模型")
    max_output_tokens: int = Field(default=1200, description="最大输出token数")


class WebSearchResult(BaseModel):
    tool_name: str
    status: str
    query: str
    context: Optional[str] = None
    overall_task_context: Optional[str] = None
    content: str
    summary: str
    sources: List[str]
    model_used: str
    timestamp: str
    duration_seconds: float


# -----------------------------------------------------------------------------
# 服务器与工具
# -----------------------------------------------------------------------------

def get_openai_client() -> OpenAI:
    """获取 OpenAI 客户端"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    base_url = os.environ.get("OPENAI_BASE_URL")
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    
    return OpenAI(**client_kwargs)


def extract_text(response) -> str:
    """从响应中提取文本内容"""
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


def summarize_text(text: str, query: str) -> str:
    """生成搜索结果摘要"""
    if not text:
        return f"No results for '{query}'"
    # Simple heuristic summary: first sentence or trimmed head
    head = text.strip().split("\n", 1)[0]
    head = head.strip()
    if len(head) > 240:
        head = head[:237] + "..."
    return head


def extract_sources(text: str) -> List[str]:
    """从文本中提取URL来源"""
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


mcp = FastMCP("WebSearch", port=8004)


@mcp.tool()
def web_search(req: WebSearchRequest) -> WebSearchResult:
    """执行网页搜索"""
    start = time.time()
    
    # 获取 OpenAI 客户端
    try:
        client = get_openai_client()
    except ValueError as e:
        return WebSearchResult(
            tool_name="web-search",
            status="error",
            query=req.query,
            context=req.context_description,
            overall_task_context=req.overall_task_query,
            content=str(e),
            summary=f"Configuration error for '{req.query}'",
            sources=[],
            model_used=req.model,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - start, 2),
        )
    
    # 构建提示
    prompt_parts: List[str] = []
    if req.overall_task_query:
        prompt_parts.append(f"Overall goal: {req.overall_task_query}")
    if req.context_description:
        prompt_parts.append(f"Purpose: {req.context_description}")
    prompt_parts.append(f"Task: {req.query}")
    
    input_text = "\n".join(prompt_parts)
    
    # Special kwargs for gpt-5 family
    extra_kwargs = {}
    if str(req.model).startswith("gpt-5"):
        extra_kwargs = {"reasoning": {"effort": "minimal"}, "text": {"verbosity": "medium"}}
    
    try:
        response = client.responses.create(
            model=req.model,
            input=input_text,
            tools=[{"type": "web_search_preview"}],
            max_output_tokens=req.max_output_tokens,
            **extra_kwargs,
        )
        
        text = extract_text(response)
        summary = summarize_text(text, req.query)
        sources = extract_sources(text)
        
        return WebSearchResult(
            tool_name="web-search",
            status="success",
            query=req.query,
            context=req.context_description,
            overall_task_context=req.overall_task_query,
            content=text,
            summary=summary,
            sources=sources,
            model_used=getattr(response, "model", req.model),
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - start, 2),
        )
    
    except Exception as e:
        return WebSearchResult(
            tool_name="web-search",
            status="error",
            query=req.query,
            context=req.context_description,
            overall_task_context=req.overall_task_query,
            content=f"Web search failed: {e}",
            summary=f"Search failed for '{req.query}'",
            sources=[],
            model_used=req.model,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - start, 2),
        )


# -----------------------------------------------------------------------------
# 启动
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from server_base import start_mcp_server
    
    start_mcp_server(mcp, 8004, "WebSearch")