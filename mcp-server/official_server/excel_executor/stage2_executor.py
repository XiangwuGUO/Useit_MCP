"""
Stage 2: Code Executor
Generates PowerShell code from modification prompt and executes it with retry mechanism
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from llm.run_llm import run_llm
from executor import CodeExecutor, ExecutionResult


class CodeGenerator:
    """
    Stage 2: Generate and execute PowerShell code from modification prompt

    Input: modify_prompt.txt + Excel file
    Output: Modified Excel file
    """

    def __init__(self, workspace_dir: Path = None):
        if workspace_dir is None:
            workspace_dir = Path(__file__).parent / "test_space"
        self.workspace_dir = workspace_dir
        self.executor = CodeExecutor(workspace_dir)

    def generate_and_execute(
        self,
        excel_file_path: str,
        modification_prompt: str,
        llm_model: str = "gpt-4o",
        api_keys: dict = None,
        max_retries: int = 3
    ) -> dict:
        """
        Generate PowerShell code and execute with retry mechanism

        Args:
            excel_file_path: Path to Excel file
            modification_prompt: Modification instructions
            llm_model: LLM model to use
            api_keys: API keys dictionary
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            {
                "success": bool,
                "code": str,
                "attempts": int,
                "execution_result": dict,
                "all_attempts": list,
                "error": str (if failed)
            }
        """

        print("\n" + "=" * 80)
        print("STAGE 2: Code Generation and Execution with Retry")
        print("=" * 80)

        attempt = 0
        current_prompt = modification_prompt
        last_error = None
        all_attempts = []

        while attempt < max_retries:
            attempt += 1
            print(f"\n{'=' * 80}")
            print(f"Attempt {attempt}/{max_retries}")
            print(f"{'=' * 80}")

            # Generate code
            gen_result = self._generate_code(
                excel_file_path=excel_file_path,
                modification_prompt=current_prompt,
                llm_model=llm_model,
                api_keys=api_keys
            )

            if not gen_result["success"]:
                last_error = gen_result.get("error", "Code generation failed")
                all_attempts.append({
                    "attempt": attempt,
                    "stage": "generation",
                    "error": last_error
                })
                print(f"✗ Code generation failed: {last_error}")
                continue

            code = gen_result["code"]

            print("=" * 80)
            print("Generated Code:")
            print("=" * 80)
            print(code)
            print("=" * 80)
            print()

            # Execute code
            exec_result = self._execute_code(code)

            # Record attempt
            all_attempts.append({
                "attempt": attempt,
                "code": code,
                "success": exec_result.success,
                "output": exec_result.output,
                "error": exec_result.error,
                "execution_time": exec_result.execution_time
            })

            if exec_result.success:
                # Success!
                print(f"\n✓ Attempt {attempt} SUCCEEDED!")
                return {
                    "success": True,
                    "code": code,
                    "attempts": attempt,
                    "execution_result": {
                        "output": exec_result.output,
                        "error": exec_result.error,
                        "execution_time": exec_result.execution_time
                    },
                    "token_usage": gen_result["token_usage"],
                    "all_attempts": all_attempts
                }
            else:
                # Failed, prepare for retry
                last_error = exec_result.error
                print(f"\n✗ Attempt {attempt} FAILED")
                print(f"Error: {last_error}")

                if attempt < max_retries:
                    # Update prompt with error feedback
                    print(f"\nPreparing attempt {attempt + 1}, sending error feedback to LLM...")
                    current_prompt = self._build_retry_prompt(modification_prompt, last_error)

        # All attempts failed
        print(f"\n✗ All {max_retries} attempts FAILED")
        return {
            "success": False,
            "error": f"Failed after {max_retries} attempts. Last error: {last_error}",
            "attempts": attempt,
            "all_attempts": all_attempts
        }

    def _generate_code(
        self,
        excel_file_path: str,
        modification_prompt: str,
        llm_model: str,
        api_keys: dict
    ) -> dict:
        """Generate PowerShell code using LLM"""

        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(excel_file_path, modification_prompt)

        print(f"Model: {llm_model}")
        print(f"Excel file: {excel_file_path}")
        print(f"Prompt length: {len(modification_prompt)} characters")
        print()

        try:
            response_text, token_usage = run_llm(
                messages=user_message,
                system=system_prompt,
                llm=llm_model,
                max_tokens=4096,
                temperature=0,
                api_keys=api_keys
            )

            print(f"✓ LLM response received, tokens: {token_usage}")
            print()

            # Extract code from response
            code = self._extract_code_from_response(response_text)

            return {
                "success": True,
                "code": code,
                "full_response": response_text,
                "token_usage": token_usage,
                "model": llm_model
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "code": None
            }

    def _build_system_prompt(self) -> str:
        """Build system prompt for code generation"""
        return """You are an Excel automation expert. The user will provide:
1. Excel file path
2. A step-by-step guide of modifications (generated from a previous analysis)

You need to generate complete PowerShell code to execute these modifications via COM object.

**CRITICAL REQUIREMENT - ENCODING**: 
- Variable names, comments, and log messages MUST be in English.
- **EXCEPTION**: The String values written INTO the Excel cells (e.g., "接消力池", "跌水2.2") MUST be preserved exactly as they appear in the input. Do NOT translate the data content.

**Code Requirements**:
- Complete and executable.
- Use `New-Object -ComObject Excel.Application`.
- **Handle Row Insertions**: The input involves inserting rows. Ensure the code executes steps sequentially.
- **Handle Formulas**: Use `.Formula` property when writing formulas (e.g., `="1/"&...`).
- **Handle Copy/Fill**: The input involves copying a slope value/formula and pasting it to the rest of the column. Use `.Copy()` and `.PasteSpecial()`.
- **CRITICAL - Cell Colors**: Use BGR integer values directly (Red=255, Orange=49407, Yellow=65535). DO NOT use `[System.Drawing.Color]` - it's not available in PowerShell by default.
- Include resource cleanup (`finally` block).
- Use absolute paths for file opening.

**PowerShell Code Template**:
```powershell
# Excel Modification Script
# Encoding: UTF-8 with BOM is recommended for saving this script

$excel = $null
$workbook = $null
$attachedToExisting = $false

try {
    # 1. Setup Excel - Try to attach to existing instance first
    try {
        $excel = [System.Runtime.InteropServices.Marshal]::GetActiveObject("Excel.Application")
        $attachedToExisting = $true
        Write-Host "Attached to existing Excel instance."
    }
    catch {
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $true
        $attachedToExisting = $false
        Write-Host "Created new Excel instance."
    }

    # 2. Find or Open Workbook
    $targetFileName = "filename.xlsx" # Replace with actual filename
    $targetPath = "C:\path\to\file.xlsx" # Replace with actual absolute path

    # Try to find workbook if already open
    $workbook = $null
    foreach ($wb in $excel.Workbooks) {
        if ($wb.FullName -eq $targetPath) {
            $workbook = $wb
            Write-Host "Found already open workbook: $targetPath"
            break
        }
    }

    # If not found, open it
    if (-not $workbook) {
        $workbook = $excel.Workbooks.Open($targetPath)
        Write-Host "Opened workbook: $targetPath"
    }

    # IMPORTANT: Always use Sheet1 explicitly
    $sheet = $workbook.Worksheets.Item("Sheet1")

    Write-Host "Starting modifications..."

    # --- START OF MODIFICATIONS ---
    # Translate the user's step-by-step guide into code below.
    # Example of handling the specific tasks:

    # Example: Writing Text (Allowing Chinese in value)
    # $sheet.Range("A6").Value2 = "接消力池"

    # Example: Setting Cell Background Color (BGR format, NOT RGB)
    # Red: 255, Orange: 49407, Yellow: 65535, Green: 5287936, Blue: 16711680
    # $sheet.Range("A6").Interior.Color = 255  # Red
    # $sheet.Range("A12").Interior.Color = 49407  # Orange

    # Example: Inserting a Row
    # $sheet.Rows.Item(13).Insert()

    # Example: Copying Values Down (Use Copy + PasteSpecial)
    # $sourceRange = $sheet.Range("K6")
    # $destinationRange = $sheet.Range("K6:K20")
    # $sourceRange.Copy()
    # $destinationRange.PasteSpecial(-4163)  # -4163 = xlPasteValues

    # Example: Copying Formulas Down
    # $sheet.Range("D12").Copy()
    # $sheet.Range("D13").PasteSpecial(-4163)  # -4163 for formulas too

    # --- END OF MODIFICATIONS ---

    Write-Host "Modifications completed."

    # 3. IMPORTANT: Save but DO NOT close
    # Always save changes, keep Excel open for observation
    $workbook.Save()
    Write-Host "Changes saved. Excel window left OPEN for observation."
}
catch {
    Write-Error "An error occurred: $_"
    throw
}
finally {
    # DO NOT close Excel or workbook - leave it open for user observation
    # Only cleanup if we created a new instance AND there was an error
    if ($Error.Count -gt 0 -and -not $attachedToExisting) {
        Write-Host "Error occurred, cleaning up..."
        if ($workbook) {
            try { $workbook.Close($false) } catch {}
        }
        if ($excel) {
            try {
                $excel.Quit()
                [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
            } catch {}
        }
    }
    # Always collect garbage
    [System.GC]::Collect()
}
"""

    def _build_user_message(self, excel_file_path: str, modification_prompt: str) -> str:
        """Build user message for LLM"""
        abs_path = Path(excel_file_path).resolve()

        message = f"""Please generate PowerShell code to modify this Excel file:

Excel file path: {abs_path}

Modification requirements:
{modification_prompt}

Generate complete PowerShell code to execute these modifications."""

        return message

    def _build_retry_prompt(self, original_prompt: str, error: str) -> str:
        """Build retry prompt with error feedback"""
        return f"""{original_prompt}

**IMPORTANT**: The previous code execution failed with the following error:
```
{error}
```

Please analyze the error and fix the code. **Follow these strict rules for the fix**:

1.  **Encoding & Language**: 
    * Variable names, function names, and comments MUST be in **English**.
    * **CRITICAL EXCEPTION**: String literals that are written into Excel cells (e.g., "接消力池", "跌水2.2") **MUST be preserved in their original Chinese**. Do NOT translate them. Do NOT remove them.
    * Add `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` at the very beginning of the script to handle output encoding.

2.  **Common Fixes**:
    * **Path issues**: Ensure absolute paths are correct and use double backslashes `\\` or single forward slashes `/` if necessary.
    * **COM Objects**: Ensure `$workbook.Save()` is called before closing.
    * **Formula Syntax**: Check if `.Formula` string requires double quotes escaping (e.g., `="1/"` might need careful handling inside a PowerShell string).
    * **Data Validation**: Check if variables are null before using them.

3.  **Output**: Generate the COMPLETE fixed PowerShell code.
"""

    def _extract_code_from_response(self, response_text: str) -> str:
        """Extract PowerShell code from LLM response"""
        import re

        # Try to extract ```powershell code block
        pattern = r"```powershell\s*(.*?)\s*```"
        matches = re.findall(pattern, response_text, re.DOTALL)

        if matches:
            return matches[0].strip()

        # Try to extract ``` code block
        pattern = r"```\s*(.*?)\s*```"
        matches = re.findall(pattern, response_text, re.DOTALL)

        if matches:
            return matches[0].strip()

        # If no code block, return entire response
        return response_text.strip()

    def _execute_code(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Execute PowerShell code"""

        print("=" * 80)
        print("Executing Code...")
        print("=" * 80)

        result = self.executor.execute(
            code=code,
            language="PowerShell",
            timeout=timeout
        )

        if result.success:
            print(f"✓ Execution SUCCEEDED")
            print(f"  Time: {result.execution_time}s")
            if result.output:
                print(f"  Output: {result.output}")
        else:
            print(f"✗ Execution FAILED")
            print(f"  Error: {result.error}")

        return result


def main():
    """Demo usage"""
    print("Stage 2 Executor Demo")
    print()

    workspace = Path(__file__).parent / "test_space"
    excel_file = workspace / "test.xlsx"
    prompt_file = workspace / "modify_prompt.txt"

    if not excel_file.exists():
        print(f"Error: Excel file not found: {excel_file}")
        return

    if not prompt_file.exists():
        print(f"Error: Prompt file not found: {prompt_file}")
        return

    # Read modification prompt
    modification_prompt = prompt_file.read_text(encoding="utf-8")

    # Get API keys
    from llm.load_api_key import load_api_keys
    api_keys = load_api_keys()

    # Create executor
    executor = CodeGenerator(workspace_dir=workspace)

    # Execute with retry
    result = executor.generate_and_execute(
        excel_file_path=str(excel_file),
        modification_prompt=modification_prompt,
        llm_model="gpt-4o",
        api_keys=api_keys,
        max_retries=3
    )

    # Show results
    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    if result["success"]:
        print(f"✓ SUCCESS after {result['attempts']} attempt(s)!")
    else:
        print(f"✗ FAILED after {result.get('attempts', 0)} attempt(s)")
        print(f"  Error: {result['error']}")


if __name__ == "__main__":
    main()
