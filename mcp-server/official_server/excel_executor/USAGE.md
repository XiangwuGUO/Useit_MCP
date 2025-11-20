# Excel Automation Pipeline - Usage Guide

## 🎯 Overview

This is a two-stage Excel automation pipeline that uses AI to analyze Excel screenshots and generate/execute modification code.

```
Stage 1: Image Analysis
  Input: Excel Screenshot + Template
  Output: modify_prompt.txt

Stage 2: Code Generation & Execution
  Input: modify_prompt.txt + Excel File
  Output: Modified Excel File
```

## 📁 Project Structure

```
Excel_Mcp_Server/
├── stage1_analyzer.py       # Stage 1: Image → Prompt
├── stage2_executor.py        # Stage 2: Prompt → Code → Execute
├── pipeline_manager.py       # Pipeline Orchestrator
├── run_full_pipeline.py      # Main Entry Point
│
├── executor.py               # Code Execution Engine
├── server.py                 # MCP Server
│
├── llm/
│   ├── run_llm.py           # LLM Caller (supports vision)
│   ├── llm_utils.py         # Utility functions
│   └── load_api_key.py      # API Key Loader
│
├── prompt_template.md        # Analysis Template
├── config/
│   └── api_keys.json        # API Keys
└── test_space/
    ├── excel_screenshot.png  # Input image
    ├── test.xlsx             # Excel file to modify
    └── modify_prompt.txt     # Generated prompt
```

## 🚀 Quick Start

### 1. Full Pipeline (Both Stages)

```bash
python run_full_pipeline.py
```

This will:
1. Analyze `test_space/excel_screenshot.png` using `prompt_template.md`
2. Generate `test_space/modify_prompt.txt`
3. Generate PowerShell code based on the prompt
4. Execute the code on `test_space/test.xlsx` (with retry up to 3 times)

### 2. Stage 1 Only (Generate Prompt)

```bash
python run_full_pipeline.py --stage1-only
```

or

```python
from stage1_analyzer import PromptGenerator
from llm.load_api_key import load_api_keys

generator = PromptGenerator()
result = generator.generate_prompt_from_image(
    image_input="test_space/excel_screenshot.png",
    template_path="prompt_template.md",
    output_path="test_space/modify_prompt.txt",
    llm_model="gpt-4o",
    api_keys=load_api_keys()
)
```

### 3. Stage 2 Only (Execute from Existing Prompt)

```bash
python run_full_pipeline.py --stage2-only
```

or

```python
from stage2_executor import CodeGenerator
from llm.load_api_key import load_api_keys
from pathlib import Path

executor = CodeGenerator()
prompt = Path("test_space/modify_prompt.txt").read_text(encoding="utf-8")

result = executor.generate_and_execute(
    excel_file_path="test_space/test.xlsx",
    modification_prompt=prompt,
    llm_model="gpt-4o",
    api_keys=load_api_keys(),
    max_retries=3
)
```

## 📝 Command Line Options

```bash
python run_full_pipeline.py [options]

Options:
  --image PATH         Excel screenshot path (default: test_space/excel_screenshot.png)
  --excel PATH         Excel file path (default: test_space/test.xlsx)
  --template PATH      Prompt template path (default: prompt_template.md)
  --prompt PATH        Modification prompt path (default: test_space/modify_prompt.txt)
  --model MODEL        LLM model (default: gpt-4o)
  --max-retries N      Max retries for Stage 2 (default: 3)
  --workspace DIR      Workspace directory (default: test_space)
  --stage1-only        Run only Stage 1
  --stage2-only        Run only Stage 2
```

## 💡 Usage Examples

### Example 1: Custom Paths

```bash
python run_full_pipeline.py \
  --image screenshots/my_excel.png \
  --excel data/workbook.xlsx \
  --model gpt-4o
```

### Example 2: Using Base64 Image

```python
import base64
from stage1_analyzer import PromptGenerator

# Read image and encode to base64
with open("screenshot.png", "rb") as f:
    base64_image = base64.b64encode(f.read()).decode("utf-8")

generator = PromptGenerator()
result = generator.generate_prompt_from_image(
    image_input=base64_image,  # Pass base64 string directly
    template_path="prompt_template.md",
    llm_model="gpt-4o",
    api_keys=api_keys
)
```

### Example 3: Programmatic Full Pipeline

```python
from pipeline_manager import ExcelAutomationPipeline
from llm.load_api_key import load_api_keys

pipeline = ExcelAutomationPipeline()

result = pipeline.run_full_pipeline(
    image_input="screenshots/excel.png",
    excel_path="data/workbook.xlsx",
    llm_model="gpt-4o",
    max_retries=3,
    api_keys=load_api_keys()
)

if result["success"]:
    print(f"Success! Prompt: {result['modify_prompt_path']}")
else:
    print(f"Failed: {result['error']}")
```

## 🔧 Configuration

### API Keys

Create `config/api_keys.json`:

```json
{
  "OPENAI_API_KEY": "sk-proj-..."
}
```

### Prompt Template

Edit `prompt_template.md` to customize the analysis instructions for Stage 1.

## ✨ Features

### Stage 1 Features
- ✅ Supports image file paths
- ✅ Supports base64 encoded images
- ✅ Uses vision-capable LLM (GPT-4V, GPT-4o, etc.)
- ✅ Customizable analysis template
- ✅ Saves prompt for manual review

### Stage 2 Features
- ✅ Automatic code generation from prompt
- ✅ **Retry mechanism** (up to 3 attempts by default)
- ✅ **Error feedback to LLM** for automatic fixes
- ✅ All code generated in **English only** (avoids encoding issues)
- ✅ Smart Excel attachment (attaches to running Excel if available)
- ✅ Detailed execution logs

### Retry Mechanism

When code execution fails:
1. Error is captured
2. Error message is sent back to LLM
3. LLM analyzes the error and generates fixed code
4. Fixed code is executed
5. Process repeats up to `max_retries` times

## 📊 Output Format

### Stage 1 Output

```python
{
    "success": True,
    "prompt_content": "...",  # Generated modification prompt
    "saved_to": "test_space/modify_prompt.txt",
    "token_usage": {"gpt-4o": 1234}
}
```

### Stage 2 Output

```python
{
    "success": True,
    "code": "# PowerShell code...",
    "attempts": 2,  # Number of attempts needed
    "execution_result": {
        "output": "Modification completed successfully",
        "error": "",
        "execution_time": 1.23
    },
    "all_attempts": [...]  # History of all attempts
}
```

### Full Pipeline Output

```python
{
    "success": True,
    "stage1_result": {...},
    "stage2_result": {...},
    "modify_prompt_path": "test_space/modify_prompt.txt"
}
```

## 🐛 Troubleshooting

### Common Issues

1. **Encoding Errors in PowerShell**
   - ✅ Fixed: All generated code uses English only

2. **Image Not Found**
   - Check image path is correct
   - Ensure image file exists

3. **API Key Not Found**
   - Create `config/api_keys.json` with your OpenAI API key

4. **Excel File Locked**
   - Close Excel file before running
   - Or use the smart attachment mode (keeps Excel open)

## 📖 API Reference

See inline documentation in:
- `stage1_analyzer.py::PromptGenerator`
- `stage2_executor.py::CodeGenerator`
- `pipeline_manager.py::ExcelAutomationPipeline`

## 🎓 Workflow Recommendation

1. **First Time**: Run full pipeline to see end-to-end execution
2. **Development**: Use `--stage1-only` to generate and review prompts
3. **Refinement**: Manually edit `modify_prompt.txt` if needed
4. **Execution**: Use `--stage2-only` to execute refined prompts
5. **Production**: Use full pipeline for automated workflows

## 📝 Notes

- **Vision Model Required**: Stage 1 requires a vision-capable model (gpt-4o, gpt-4-vision-preview, etc.)
- **PowerShell**: Generated code is in PowerShell (Windows)
- **Retry Limit**: Default 3 retries, configurable via `--max-retries`
- **All English**: Code, comments, and error messages are in English to avoid encoding issues
