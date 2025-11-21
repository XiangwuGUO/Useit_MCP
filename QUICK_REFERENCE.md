# MCP Client 调用方法快速参考

## 🎯 两种调用模式对比

| 特性 | 直接调用模式 | AI智能调用模式 |
|------|------------|--------------|
| **函数** | `call_mcp_tool_directly()` | `call_streaming_task_with_files()` |
| **是否经过LLM** | ❌ 否 | ✅ 是 |
| **速度** | ⚡⚡⚡ 快速 | ⚡ 较慢 |
| **成本** | 💰 低（无API费用） | 💰💰 高（使用Claude API） |
| **工具选择** | 🔧 手动指定 | 🤖 AI自动选择 |
| **参数生成** | 📝 手动准备 | 🤖 AI自动生成 |
| **文件选择** | 手动/全部/AI | AI智能选择 |
| **Metadata注入** | ✅ 支持 | ✅ 自动注入 |
| **多步骤任务** | ❌ 不支持 | ✅ 支持 |
| **适用场景** | 单工具，参数已知 | 多工具，复杂任务 |

---

## 📋 快速决策流程图

```
开始
  │
  ├─ MCP Server只有一个工具？
  │   ├─ 是 → 使用【直接调用】
  │   └─ 否 → 继续
  │
  ├─ 参数已经完全准备好？
  │   ├─ 是 → 使用【直接调用】
  │   └─ 否 → 使用【AI调用】
  │
  ├─ 需要AI选择合适的工具？
  │   ├─ 是 → 使用【AI调用】
  │   └─ 否 → 继续
  │
  ├─ 需要快速执行、节省成本？
  │   ├─ 是 → 使用【直接调用】
  │   └─ 否 → 使用【AI调用】
  │
  └─ 复杂的多步骤任务？
      ├─ 是 → 使用【AI调用】
      └─ 否 → 使用【直接调用】
```

---

## 🚀 模式1：直接调用（推荐：单工具场景）

### 基本调用

```python
from call_mcp_client import call_mcp_tool_directly

success, result = call_mcp_tool_directly(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    tool_name="generate_excel",
    arguments={
        "instruction": "创建销售报表",
        "output_path": "/output/report.xlsx"
    }
)
```

### 带文件（不使用AI选择）

```python
success, result = call_mcp_tool_directly(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    tool_name="generate_excel",
    arguments={
        "instruction": "根据图片生成报表",
        "output_path": "/output/report.xlsx"
    },
    # 文件配置
    files_directory="/data/input",
    file_manifest_path="/data/input/manifest.json",
    auto_select_files=False,  # 使用所有文件
    max_files=10
)
```

### 带文件（使用AI选择）⭐ 新增

```python
success, result = call_mcp_tool_directly(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    tool_name="generate_excel",
    arguments={
        "instruction": "根据销售数据和趋势图生成Q1销售分析报表",  # AI会根据这个描述选择相关文件
        "output_path": "/output/q1_report.xlsx"
    },
    # 文件配置
    files_directory="/data/q1_files",
    file_manifest_path="/data/q1_files/manifest.json",
    auto_select_files=True,   # ⭐ AI会从10个文件中智能选择相关的
    max_files=5               # 最多选5个
)
```

**注意事项：**
- ✅ AI选择会从`arguments`中提取任务描述（支持字段：`instruction`, `task`, `description`, `task_description`）
- ✅ 需要设置环境变量 `ANTHROPIC_API_KEY`
- ✅ AI选择会产生额外的API费用（用于文件选择）
- ✅ 适合文件较多时使用，可以减少不必要的文件传输

---

## 🤖 模式2：AI智能调用（推荐：复杂任务）

### 基本调用

```python
from call_mcp_client import call_streaming_task_with_files

success, result = call_streaming_task_with_files(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    task_description="创建一个包含产品销售数据的Excel报表"
)
```

### 带文件（AI智能选择）

```python
success, result = call_streaming_task_with_files(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    task_description="根据提供的销售数据和趋势图，生成Q1销售分析报表",
    # 文件配置
    files_directory="/data/q1_files",
    file_manifest_path="/data/q1_files/manifest.json",
    auto_select_files=True,  # 默认True，AI会选择相关文件
    max_files=5
)
```

### 带Metadata

```python
success, result = call_streaming_task_with_files(
    mcp_client_url="http://localhost:8080",
    vm_id="vm1",
    session_id="session1",
    mcp_server_name="excel_executor",
    task_description="生成销售报表",
    metadata={
        "user_id": "user123",
        "department": "sales",
        "report_type": "quarterly"
    }
)
```

---

## 📊 文件清单格式（manifest.json）

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
      "path": "charts/trend.png",
      "description": "销售趋势图表"
    }
  ]
}
```

**重要：**
- `path`: 相对于 `files_directory` 的路径
- `description`: 文件描述，**AI会根据这个描述选择相关文件**

---

## 🔧 AI文件选择工作原理

### 直接调用模式

```
1. 从 arguments 中提取任务描述
   ↓
2. 将任务描述和文件清单发送给 Claude API
   ↓
3. Claude 分析哪些文件与任务相关
   ↓
4. 返回选中的文件路径列表
   ↓
5. 编码选中的文件并注入到 metadata
```

**支持的字段（优先级从高到低）：**
1. `instruction`
2. `task`
3. `description`
4. `task_description`

**示例：**
```python
arguments = {
    "instruction": "根据销售数据和趋势图生成Q1报表",  # ← AI会使用这个
    "output_path": "/output/report.xlsx"
}
```

### AI调用模式

```
1. 直接使用 task_description 参数
   ↓
2. 将任务描述和文件清单发送给 Claude API
   ↓
3. Claude 分析哪些文件与任务相关
   ↓
4. 返回选中的文件路径列表
   ↓
5. 编码选中的文件并注入到 metadata
```

---

## ⚠️ 常见问题

### Q1: 什么时候应该使用AI文件选择？

**推荐使用的场景：**
- ✅ 文件数量 > 5个
- ✅ 只有部分文件与任务相关
- ✅ 需要减少数据传输量
- ✅ 文件描述比较详细

**不推荐使用的场景：**
- ❌ 文件数量 < 3个（直接传所有文件更快）
- ❌ 所有文件都相关（没必要选择）
- ❌ 没有设置 ANTHROPIC_API_KEY
- ❌ 需要绝对保证所有文件都被使用

### Q2: AI文件选择会产生多少费用？

**费用估算：**
- 每次文件选择调用：约 $0.001 - $0.003
- 主要取决于文件数量和描述长度
- 相比主任务的LLM调用，费用很小

### Q3: 如果AI选择了错误的文件怎么办？

**解决方案：**
1. 改进文件清单的 `description` 字段
2. 改进任务描述，更明确地说明需要什么类型的文件
3. 设置 `auto_select_files=False`，使用所有文件

### Q4: 直接调用模式下，参数中没有任务描述字段怎么办？

**解决方案：**
```python
# 方案1：添加一个任务描述字段
arguments = {
    "instruction": "生成报表",  # ← AI会使用这个
    "param1": "value1",
    # ... 其他参数
}

# 方案2：如果工具不支持额外字段，禁用AI选择
auto_select_files=False  # 使用所有文件
```

---

## 📞 快速参考卡

### 直接调用

```python
call_mcp_tool_directly(
    mcp_client_url=...,
    vm_id=...,
    session_id=...,
    mcp_server_name=...,
    tool_name=...,              # 必需：工具名
    arguments={...},            # 必需：工具参数
    metadata={...},             # 可选：元数据
    files_directory=...,        # 可选：文件目录
    file_manifest_path=...,     # 可选：清单路径
    auto_select_files=False,    # 可选：AI选择（默认False）
    max_files=5                 # 可选：最大文件数
)
```

### AI调用

```python
call_streaming_task_with_files(
    mcp_client_url=...,
    vm_id=...,
    session_id=...,
    mcp_server_name=...,
    task_description=...,       # 必需：任务描述
    metadata={...},             # 可选：元数据
    files_directory=...,        # 可选：文件目录
    file_manifest_path=...,     # 可选：清单路径
    auto_select_files=True,     # 可选：AI选择（默认True）
    max_files=5                 # 可选：最大文件数
)
```

---

## 🎓 最佳实践

1. **文件较少（<3个）**：直接传所有文件，不使用AI选择
2. **文件较多（>5个）**：使用AI选择，减少传输
3. **任务描述要清晰**：描述越详细，AI选择越准确
4. **文件描述要详细**：帮助AI理解文件内容
5. **合理设置 max_files**：根据实际需要设置上限

---

## 📚 更多信息

- 详细文档：`MCP_CLIENT_FILE_METADATA_GUIDE.md`
- API文档：`http://localhost:8080/docs`
- 健康检查：`http://localhost:8080/health`
