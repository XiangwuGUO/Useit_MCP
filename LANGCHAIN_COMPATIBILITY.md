# LangChain MCP 兼容性解决方案

## 问题背景

LangChain Agent 在调用 MCP 工具时，传递的参数格式与 MCP 工具期望的格式不匹配，导致参数验证错误。

**问题现象：**
- LangChain Agent 传递: `{'req': {'path': '...', 'content': '...'}}`
- 但实际期望: `{'path': '...', 'content': '...'}`

## 解决方案

### 🎯 核心原则

1. **MCP Server 端**：工具使用标准平级参数格式（符合 MCP 规范）
2. **MCP Client 端**：修复参数传递逻辑，直接传递平级参数
3. **向后兼容**：保持对现有调用方式的支持
4. **自动扩展**：新工具无需额外配置即可兼容

### 📋 具体修改

#### 1. MCP Server 端 - 标准平级参数格式

```python
# ✅ 正确：标准 MCP 工具格式
@mcp.tool()
def write_text(
    path: str,
    content: str,
    encoding: str = "utf-8",
    append: bool = False,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """写入文本文件"""
    # 工具实现
    pass

# ❌ 错误：嵌套参数格式
@mcp.tool()
def write_text(**kwargs) -> Dict[str, Any]:
    # 需要手动解析 req 参数
    pass
```

#### 2. MCP Client 端 - 修复参数传递

**修改文件：** `mcp-client/core/streaming_executor.py`

```python
# 修复前：错误地包装参数
async def wrapped_func(**kwargs):
    wrapped_args = {"req": kwargs}  # ❌ 错误包装
    return await tool.ainvoke(wrapped_args)

# 修复后：直接传递平级参数
async def wrapped_func(**kwargs):
    # ✅ 直接传递平级参数
    return await tool.ainvoke(kwargs)
```

### 🔧 实现细节

#### Server 端工具模板

```python
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("your_service_name")

@mcp.tool()
def your_tool(
    required_param: str,
    optional_param: str = "default_value",
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    你的工具描述
    
    Args:
        required_param: 必需参数说明
        optional_param: 可选参数说明
        session_id: 会话ID (可选)
    """
    # 工具实现
    return {
        "status": "success",
        "data": {...}
    }
```

#### Client 端检测逻辑

```python
def _tool_needs_wrapping(self, tool: BaseTool) -> bool:
    """检查工具是否需要参数包装"""
    # 现在大多数工具都不需要包装
    if not hasattr(tool, 'args_schema') or not tool.args_schema:
        return False
    
    # 只有明确包含嵌套req结构的才需要包装
    if hasattr(tool.args_schema, 'model_fields') and 'req' in tool.args_schema.model_fields:
        return True
    
    return False
```

### 🚀 优势

1. **符合标准**：MCP Server 端使用标准平级参数格式
2. **自动兼容**：新工具只要按标准格式编写即可自动兼容 LangChain
3. **易于维护**：无需为每个工具手动编写参数解析代码
4. **可扩展性**：添加新工具时无需修改 Client 端代码
5. **向后兼容**：保持对现有调用方式的支持

### 📊 测试验证

运行测试验证修复效果：

```bash
cd /path/to/useit-mcp
python test_client_side_fix.py
```

**预期结果：**
- ✅ 平级参数调用成功
- ✅ 文件创建功能正常
- ✅ LangChain Agent 模拟调用成功

### 🔄 迁移指南

#### 对于现有 MCP 工具：

1. **修改函数签名**：
   ```python
   # 从这种格式
   @mcp.tool()
   def tool_name(**kwargs):
       req = _parse_args(**kwargs)
   
   # 改为这种格式
   @mcp.tool()
   def tool_name(param1: str, param2: int = 0):
       # 直接使用参数
   ```

2. **删除参数解析函数**：
   ```python
   # 删除这类函数
   def _parse_tool_args(**kwargs) -> ToolRequest:
       # 解析逻辑
   ```

#### 对于新 MCP 工具：

直接使用标准格式即可：

```python
@mcp.tool()
def new_tool(
    param1: str,
    param2: Optional[int] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """工具描述"""
    # 工具实现
    return {"status": "success", "data": {...}}
```

### 🎯 最佳实践

1. **参数命名**：使用清晰的参数名称
2. **类型注解**：提供完整的类型注解
3. **默认值**：为可选参数提供合理默认值
4. **文档**：提供详细的参数说明
5. **错误处理**：实现适当的错误处理逻辑

### 📞 故障排除

**问题：** LangChain Agent 调用失败
**解决：** 检查工具函数是否使用了标准平级参数格式

**问题：** 参数验证错误
**解决：** 确保 Client 端的 `_tool_needs_wrapping` 逻辑正确

**问题：** 工具不兼容
**解决：** 检查是否有遗留的嵌套参数格式

### 🔗 相关资源

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchainjs/tree/main/libs/langchain-mcp-adapters)
- [FastMCP 文档](https://github.com/pydantic/FastMCP)

---

**总结：** 这个解决方案通过在正确的层面（Client 端）处理参数格式转换，实现了 LangChain Agent 与 MCP 工具的无缝兼容，同时保持了代码的简洁性和可扩展性。

