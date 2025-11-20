# 如何运行AI Excel修改工具

## 前提条件

1. 已安装Python 3.8+
2. 已安装OpenAI库：`pip install openai`
3. 有OpenAI API Key

## 步骤1：设置API Key

### Windows PowerShell
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

### Windows CMD
```cmd
set OPENAI_API_KEY=your-api-key-here
```

### Linux/Mac
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## 步骤2：运行修改脚本

```bash
cd d:\develop\New_Start\Excel\Excel_Mcp_Server
python modify_test_excel.py
```

## 工作流程

1. **读取prompt** - 从 `modify_prompt.txt` 读取修改需求
2. **调用LLM** - 使用GPT-4o生成PowerShell代码
3. **执行代码** - 自动执行生成的代码修改Excel
4. **完成** - 查看修改后的 `test.xlsx`

## 文件说明

- `test.xlsx` - 要修改的Excel文件
- `modify_prompt.txt` - 修改需求描述
- `modify_test_excel.py` - 运行脚本

## 当前需求

根据 `modify_prompt.txt`：
- 将K6~K23单元格的值改为 0.005
- 或更保险的选择：0.003

## 示例完整命令

```powershell
# 1. 设置API Key
$env:OPENAI_API_KEY="sk-xxxx..."

# 2. 运行脚本
cd d:\develop\New_Start\Excel\Excel_Mcp_Server
python modify_test_excel.py
```

## 预期输出

```
Starting modification...
Excel file: D:\develop\New_Start\Excel\Excel_Mcp_Server\test_space\test.xlsx
Prompt length: 43 chars

Calling LLM to generate code...
================================================================================
Calling LLM to generate code...
================================================================================
Model: gpt-4o
Excel file: D:\develop\New_Start\Excel\Excel_Mcp_Server\test_space\test.xlsx
Prompt length: 43 chars

LLM response completed, tokens: {...}

================================================================================
Generated code:
================================================================================
[PowerShell代码]
================================================================================

================================================================================
Executing modification code...
================================================================================
SUCCESS: Modification completed
  Execution time: X.XXs
  Output: ...

================================================================================
SUCCESS!
Execution time: X.XXs
```

## 故障排除

### 问题1：API Key未设置
```
ERROR: OPENAI_API_KEY not set
```
解决：参考步骤1设置API Key

### 问题2：OpenAI库未安装
```
ModuleNotFoundError: No module named 'openai'
```
解决：`pip install openai`

### 问题3：Excel文件被占用
```
Error: Excel file is in use
```
解决：关闭Excel程序后重试

## 高级用法

### 修改其他Excel文件

编辑 `modify_test_excel.py`：
```python
excel_file = test_space / "your_file.xlsx"
```

### 使用不同的prompt

编辑 `modify_prompt.txt` 或创建新的prompt文件：
```python
prompt_file = test_space / "your_prompt.txt"
```

### 只生成代码不执行

```python
result = modifier.modify_excel(
    ...
    auto_execute=False  # 改为False
)
```
