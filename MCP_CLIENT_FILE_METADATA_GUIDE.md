# MCP Client 文件和Metadata功能使用指南

## 概述

MCP Client现在支持两种调用模式：

1. **直接调用模式**：跳过LLM，直接调用MCP Server工具
2. **AI智能调用模式**：使用LLM智能选择工具和参数，支持自动注入metadata

两种模式都支持：
- 文件输入（图片、文本等）
- Metadata透传
- 智能文件选择（AI模式）

---

## 文件结构

```
mcp-client/
├── core/
│   ├── api_models.py          # 数据模型（已扩展）
│   ├── file_processor.py      # 文件处理模块
│   ├── file_selector.py       # AI智能文件选择器
│   ├── direct_caller.py       # 直接调用模块
│   ├── metadata_injector.py   # Metadata注入器
│   ├── streaming_executor.py  # 流式执行器（已增强）
│   └── ...
├── server.py                  # MCP Gateway（已添加新端点）
└── ...
```

---

## 模式1：直接调用（跳过LLM）

### 适用场景
- MCP Server只有单个工具
- 参数已准备好，不需要AI生成
- 需要快速执行，节省API成本

### 使用方法

#### Python调用示例

```python
from call_mcp_client import call_mcp_tool_directly

# 示例1：不带文件的直接调用
success, result = call_mcp_tool_directly(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    tool_name="generate_excel",
    arguments={
        "instruction": "创建销售报表",
        "output_path": "/output/report.xlsx"
    },
    metadata={
        "user_id": "user123",
        "task_id": "task_456"
    }
)

if success:
    print("调用成功:", result)
else:
    print("调用失败:", result.get("error"))
```

#### 带文件输入的直接调用

```python
# 示例2：带文件输入的直接调用
success, result = call_mcp_tool_directly(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    tool_name="generate_excel",
    arguments={
        "instruction": "根据图片生成销售报表",
        "output_path": "/output/report.xlsx"
    },
    metadata={
        "user_id": "user123"
    },
    # 文件配置
    files_directory="/data/input_files",
    file_manifest_path="/data/input_files/manifest.json",
    auto_select_files=False,  # 不使用AI选择，使用所有文件
    max_files=10
)
```

#### HTTP API调用示例

```bash
curl -X POST http://localhost:8080/tools/call-direct \
  -H "Content-Type: application/json" \
  -d '{
    "vm_id": "vm1",
    "session_id": "session1",
    "mcp_server_name": "excel_executor",
    "tool_name": "generate_excel",
    "arguments": {
      "instruction": "创建销售报表",
      "output_path": "/output/report.xlsx"
    },
    "metadata": {
      "user_id": "user123"
    },
    "files_input": {
      "files_directory": "/data/input",
      "file_manifest_path": "/data/input/manifest.json",
      "auto_select": false,
      "max_files": 5
    }
  }'
```

---

## 模式2：AI智能调用（使用LLM）

### 适用场景
- 需要AI选择合适的工具
- 需要AI从文件中智能选择相关内容
- 复杂的多步骤任务

### 使用方法

#### Python调用示例

```python
from call_mcp_client import call_streaming_task_with_files

# 示例：AI智能调用，自动选择相关文件
success, result = call_streaming_task_with_files(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    task_description="根据提供的截图和数据文件，生成一份完整的销售分析报表",
    metadata={
        "user_id": "user123",
        "department": "sales"
    },
    # 文件配置
    files_directory="/data/input_files",
    file_manifest_path="/data/input_files/manifest.json",
    auto_select_files=True,  # 使用AI智能选择相关文件
    max_files=5
)

if success:
    print("任务完成:", result.get("summary"))
    print("执行步骤:", result.get("execution_steps"))
else:
    print("任务失败:", result.get("error"))
```

#### HTTP API调用示例

```bash
curl -X POST http://localhost:8080/tasks/execute-stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "vm_id": "vm1",
    "session_id": "session1",
    "mcp_server_name": "excel_executor",
    "task_description": "根据提供的截图和数据生成销售报表",
    "metadata": {
      "user_id": "user123"
    },
    "files_input": {
      "files_directory": "/data/input",
      "file_manifest_path": "/data/input/manifest.json",
      "auto_select": true,
      "max_files": 5
    }
  }'
```

---

## 文件清单格式（manifest.json）

文件清单用于描述目录中的文件，格式如下：

```json
{
  "files": [
    {
      "path": "screenshot1.png",
      "description": "产品列表页面截图，显示所有产品信息"
    },
    {
      "path": "data/sales_2024.csv",
      "description": "2024年销售数据，包含产品ID、数量、金额"
    },
    {
      "path": "requirements.txt",
      "description": "需求文档，说明报表应包含的字段"
    },
    {
      "path": "charts/trend.png",
      "description": "销售趋势图表"
    }
  ]
}
```

### 字段说明

- `path`: 文件相对路径（相对于`files_directory`）
- `description`: 文件描述（用于AI选择相关文件）

---

## MCP Server端适配

MCP Server的工具需要支持`metadata`参数：

```python
# MCP Server端工具示例
class ExcelExecutorTool:
    async def generate_excel(
        self,
        # 业务参数
        instruction: str,
        output_path: str,

        # metadata参数（可选）
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        生成Excel报表

        Args:
            instruction: 操作指令
            output_path: 输出路径
            metadata: 元数据（可选），包含：
                - files: 输入文件列表
                - user_id: 用户ID
                - 其他自定义数据
        """

        # 1. 处理文件数据
        if metadata and "files" in metadata:
            files = metadata["files"]

            # 提取图片
            images = [f for f in files if f["type"] == "image"]
            for img in images:
                # base64解码
                image_data = base64.b64decode(img["content"])
                # 使用图片...

            # 提取文本
            text_files = [f for f in files if f["type"] == "text"]
            for txt in text_files:
                content = txt["content"]
                # 使用文本...

        # 2. 执行业务逻辑
        result = await self._do_generate_excel(instruction, output_path, images, text_files)

        return result
```

---

## 支持的文件类型

### 图片文件
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`
- 编码方式：base64
- MIME类型：自动识别

### 文本文件
- `.txt`, `.md`, `.json`, `.csv`, `.xml`, `.yaml`, `.yml`, `.log`
- 编码方式：UTF-8（自动降级GBK）

---

## 完整示例：Excel报表生成

### 1. 准备文件结构

```
/data/input_files/
├── manifest.json
├── screenshot.png          # 界面截图
├── sales_data.csv         # 销售数据
└── requirements.md        # 需求文档
```

### 2. manifest.json内容

```json
{
  "files": [
    {
      "path": "screenshot.png",
      "description": "产品管理界面截图"
    },
    {
      "path": "sales_data.csv",
      "description": "销售明细数据"
    },
    {
      "path": "requirements.md",
      "description": "报表需求说明"
    }
  ]
}
```

### 3. 调用代码

```python
from call_mcp_client import call_mcp_tool_directly

success, result = call_mcp_tool_directly(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    tool_name="generate_excel",
    arguments={
        "instruction": "根据截图和数据生成销售报表",
        "output_path": "/output/sales_report.xlsx"
    },
    files_directory="/data/input_files",
    file_manifest_path="/data/input_files/manifest.json",
    max_files=10
)

if success:
    print("✅ Excel报表生成成功")
    print(f"执行时间: {result['execution_time_seconds']:.2f}秒")
    print(f"使用文件: {result['files_count']}个")
else:
    print(f"❌ 生成失败: {result['error']}")
```

---

## 功能对比

| 特性 | 直接调用 | AI智能调用 |
|------|---------|-----------|
| **是否经过LLM** | ❌ 否 | ✅ 是 |
| **文件选择** | 手动/全部 | AI智能选择 |
| **Metadata注入** | ✅ 支持 | ✅ 自动注入 |
| **执行速度** | ⚡ 快 | 🐌 较慢 |
| **API成本** | 💰 低 | 💰💰 高 |
| **适用场景** | 单工具，参数明确 | 多工具，复杂任务 |

---

## 向后兼容性

所有新功能都是可选的：

- 不提供`metadata`：按原有方式工作
- 不提供`files_input`：按原有方式工作
- 原有API端点：完全兼容

---

## 故障排查

### 问题1：文件读取失败

**现象**：返回错误"文件不存在"

**解决**：
1. 检查`files_directory`路径是否正确
2. 检查`file_manifest_path`是否正确
3. 确保manifest.json中的path相对于files_directory

### 问题2：文件太大导致超时

**解决**：
1. 减少`max_files`数量
2. 压缩图片文件大小
3. 使用`auto_select=true`让AI选择必要文件

### 问题3：metadata未生效

**解决**：
1. 确保MCP Server端工具支持metadata参数
2. 检查metadata格式是否正确（Dict类型）

---

## 更新日志

**v2.1.0 (2025-01-20)**
- ✨ 新增直接调用模式（跳过LLM）
- ✨ 支持文件输入（图片、文本）
- ✨ 支持Metadata自动注入
- ✨ 支持AI智能文件选择
- 📝 完全向后兼容

---

## 联系支持

- 问题反馈：GitHub Issues
- 技术支持：dev@example.com
