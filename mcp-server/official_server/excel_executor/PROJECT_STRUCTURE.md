# 项目文件结构说明

## 📁 项目结构

```
excel_executor/
├── 📄 入口文件
│   └── iterative_pipeline.py          # 主入口：多轮迭代 Excel 自动化管道
│
├── 🔧 核心模块
│   ├── stage1_analyzer.py             # Stage 1: 截图分析，生成修改提示
│   ├── stage2_executor.py             # Stage 2: 代码生成和执行
│   ├── executor.py                    # 代码执行引擎（PowerShell）
│   ├── excel_screenshot.py            # Excel 截图捕获
│   └── excel_validator.py             # Excel 数据验证（收敛检查）
│
├── 🤖 LLM 模块
│   └── llm/
│       ├── run_llm.py                 # LLM 调用接口
│       ├── llm_utils.py               # LLM 工具函数
│       └── load_api_key.py            # API 密钥加载
│
├── ⚙️ 配置和模板
│   ├── config/
│   │   └── api_keys.json              # API 密钥配置
│   ├── prompt_template.md             # excel解析提示词模板（必需）
│
├── 📂 工作目录
│   ├── test_space/                    # Excel 文件目录
│   │   └── test.xlsx                  # 测试 Excel 文件
│   └── conv_his/                      # 对话历史输出目录
│       ├── screenshot_*.png           # 截图文件
│       ├── modify_prompt_*.txt        # 修改提示文件
│       ├── excel_code_*.ps1           # 生成的 PowerShell 代码
│       └── iteration_summary.json     # 迭代总结
│
└── 📚 文档
    ├── USAGE.md                       # 使用说明
    └── examples/
        └── usage_examples.md          # 使用示例
```

---

## 🚀 入口文件

### 主入口：`iterative_pipeline.py`

**功能**：多轮迭代 Excel 自动化管道，自动修改 Excel 直到满足收敛条件。

**使用方式**：

#### 方式 1：直接运行（使用内置 main 函数）

```bash
python iterative_pipeline.py
```

**默认配置**：
- Excel 文件：`test_space/test.xlsx`
- 输出目录：`conv_his/`
- 最大迭代次数：5 轮
- LLM 模型：`gpt-4o`
- 收敛条件：J 列所有值满足 `-0.5 < x < 2`

#### 方式 2：作为模块导入使用

```python
from pathlib import Path
from iterative_pipeline import IterativeExcelPipeline
from llm.load_api_key import load_api_keys

# 加载 API 密钥
api_keys = load_api_keys()

# 创建管道
pipeline = IterativeExcelPipeline(
    workspace_dir=Path("test_space"),      # Excel 文件目录
    conversation_dir=Path("conv_his")      # 输出目录
)

# 运行迭代管道
result = pipeline.run_iterative_pipeline(
    excel_file_path="test_space/test.xlsx",
    max_iterations=5,                      # 最多 5 轮
    llm_model="gpt-4o",
    api_keys=api_keys,
    stage2_max_retries=3                   # Stage 2 每轮最多重试 3 次
)

# 检查结果
if result["success"]:
    if result["converged"]:
        print(f"✓ 成功收敛，共 {result['total_rounds']} 轮")
    else:
        print(f"✗ 未收敛，共 {result['total_rounds']} 轮")
else:
    print(f"✗ 失败: {result.get('error')}")
```


### 每轮迭代步骤：

1. **Stage 1 - 分析**：
   - 捕获 Excel 截图
   - 使用 LLM 分析截图，生成修改提示
   - 保存到 `conv_his/modify_prompt_{轮数}.txt`

2. **Stage 2 - 执行**：
   - 根据修改提示生成 PowerShell 代码
   - 代码模板硬编码在 `stage2_executor.py` 的 `_build_system_prompt()` 方法中
   - 执行代码修改 Excel
   - 保存代码到 `conv_his/excel_code_{轮数}.ps1`
   - 注意：`templates/powershell/` 目录下的文件是参考示例，未在代码中使用

3. **验证**：
   - 检查 J 列数据是否满足收敛条件（`-0.5 < x < 2`）
   - 如果收敛，停止迭代
   - 如果未收敛，继续下一轮

---

