# Excel COM 代码生成器 MCP Server

基于代码生成的Excel自动化服务，AI理解需求后生成完整的COM代码一次性执行。

## 核心特点

**不是传统的工具调用模式**，而是：
1. 用户描述需求
2. AI生成完整代码（PowerShell/Python）
3. 一次性执行完成
4. 代码可见、可保存、可复用

## 快速开始

### 1. 安装依赖

```bash
pip install mcp fastmcp
```

### 2. 启动服务器

```bash
cd Excel_Mcp_Server
python server.py
```

### 3. 配置MCP客户端

在Claude Desktop配置文件中添加：

```json
{
  "mcpServers": {
    "excel-codegen": {
      "command": "python",
      "args": ["d:/develop/New_Start/Excel/Excel_Mcp_Server/server.py"],
      "env": {
        "EXCEL_WORKSPACE_DIR": "d:/excel_workspace"
      }
    }
  }
}
```

## 使用示例

### 示例1：创建简单表格

**用户输入：**
```
创建一个员工信息表，包含姓名、部门、工资三列
```

**系统会：**
1. 生成完整的PowerShell代码
2. 显示代码给用户确认
3. 执行代码
4. 返回生成的Excel文件路径

### 示例2：销售报表

**用户输入：**
```
制作销售报表，包含产品名称、数量、单价、总价，表头加粗黄色背景，添加总计行
```

**生成的代码会包含：**
- 表格创建
- 数据填充
- 公式计算
- 格式设置
- 总计统计
- 自动保存

### 示例3：数据分析

**用户输入：**
```
创建一个学生成绩表，包含5个学生的语文、数学、英语成绩，
计算每个学生的总分和平均分，并找出最高分和最低分
```

## MCP工具说明

### 1. generate_excel_code
生成Excel操作代码

```python
generate_excel_code(
    requirement="创建一个包含销售数据的表格",
    language="PowerShell",  # 或 "Python"
    file_name="报表.xlsx"    # 可选
)
```

### 2. execute_excel_code
执行生成的代码

```python
execute_excel_code(
    code="...",
    language="PowerShell",
    timeout=60,
    save_code=False  # 是否保存代码供复用
)
```

### 3. generate_and_execute
一站式生成并执行

```python
generate_and_execute(
    requirement="创建员工表",
    auto_execute=True,
    save_code=True
)
```

### 4. list_generated_files
查看生成的文件

```python
list_generated_files(pattern="*.xlsx")
```

### 5. get_templates
获取可用模板

```python
get_templates()
```

## 工作原理

```
┌─────────────┐
│ 用户需求    │
│ "创建报表"  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ AI分析需求  │
│ 提取操作类型│
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ 代码生成引擎 │
│ 生成PS/Python│
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 安全检查     │
│ 沙箱执行     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 返回结果     │
│ + Excel文件  │
└──────────────┘
```

## 优势对比

| 特性 | 传统Tool模式 | 代码生成模式 |
|------|-------------|-------------|
| 调用次数 | 10-50次 | 1次 |
| 延迟 | 高 | 低 |
| 灵活性 | 受限 | 无限 |
| 代码可见 | ❌ | ✅ |
| 可复用 | ❌ | ✅ |
| 学习价值 | 低 | 高 |

## 支持的操作

- ✅ 创建工作簿和工作表
- ✅ 写入数据（单元格、范围）
- ✅ 格式化（字体、颜色、边框）
- ✅ 公式计算
- ✅ 表头设置
- ✅ 自动列宽调整
- ✅ 数字格式化
- ✅ 数据统计（求和、平均等）
- 🔄 图表创建（计划中）
- 🔄 数据透视表（计划中）

## 安全特性

- 沙箱执行环境
- 文件路径限制
- 危险命令检测
- 超时保护
- 资源自动清理

## 模板库

预定义模板位于 `templates/` 目录：

- `basic_create.ps1` - 基础表格创建
- `sales_report.ps1` - 销售报表
- 更多模板持续添加...

## 故障排除

### 问题1：PowerShell执行策略
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Bypass
```

### 问题2：COM组件未注册
确保已安装Microsoft Excel

### 问题3：权限问题
以管理员权限运行

## 开发计划

- [x] 基础MCP服务器
- [x] PowerShell代码生成
- [x] 沙箱执行引擎
- [x] 基础模板
- [ ] Python代码生成完善
- [ ] 图表生成支持
- [ ] 数据透视表支持
- [ ] 模板管理系统
- [ ] Web UI界面

## 许可证

MIT License

## 贡献

欢迎提交Issue和PR！
