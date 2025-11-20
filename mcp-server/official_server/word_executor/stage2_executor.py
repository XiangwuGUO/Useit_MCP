"""
Stage 2: Code Executor
Generates PowerShell code from modification prompt and executes it with retry mechanism
Enhanced for Word: Read document → Search paragraph → Generate code → Execute
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from llm.run_llm import run_llm
from executor import CodeExecutor, ExecutionResult
from document_reader import DocumentReader
from document_search import DocumentSearcher


class CodeGenerator:
    """
    Stage 2: Generate and execute PowerShell code from modification prompt

    Input: modify_prompt.txt + Word file
    Output: Modified Word file

    Enhanced Word flow:
    1. Read complete Word document
    2. Search for target paragraph using keywords
    3. Extract paragraph context
    4. Generate Word COM code with paragraph location info
    5. Execute code
    """

    def __init__(self, workspace_dir: Path = None):
        if workspace_dir is None:
            workspace_dir = Path(__file__).parent / "test_space"
        self.workspace_dir = workspace_dir
        self.executor = CodeExecutor(workspace_dir)
        self.document_reader = DocumentReader()
        self.document_searcher = DocumentSearcher()

    def generate_and_execute(
        self,
        word_file_path: str,
        modification_prompt: str,
        llm_model: str = "gpt-4o",
        api_keys: dict = None,
        max_retries: int = 3
    ) -> dict:
        """
        Generate PowerShell code and execute with retry mechanism
        Enhanced for Word: Read document → Search paragraph → Generate precise code

        Args:
            word_file_path: Path to Word file (.docx)
            modification_prompt: Modification instructions (from Stage 1)
            llm_model: LLM model to use
            api_keys: API keys dictionary
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            {
                "success": bool,
                "code": str,
                "attempts": int,
                "execution_result": dict,
                "document_info": dict,
                "search_info": dict,
                "all_attempts": list,
                "error": str (if failed)
            }
        """

        print("\n" + "=" * 80)
        print("STAGE 2: Code Generation and Execution with Retry (Word Enhanced)")
        print("=" * 80)

        # === NEW: Read Word document ===
        print("\n[Step 1] Reading Word document...")
        try:
            doc_info = self.document_reader.read_word_document(word_file_path)
            print(f"✓ Document read successfully")
            print(f"  Total paragraphs: {doc_info['total_paragraphs']}")
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read Word document: {str(e)}"
            }

        # === NEW: Search for target paragraph ===
        print("\n[Step 2] Searching for target paragraph...")
        target_index, search_info = self.document_searcher.search_paragraph(
            doc_info['paragraphs'],
            modification_prompt
        )

        if target_index is None:
            print("✗ Could not locate target paragraph")
            print(f"  Search info: {search_info}")
            return {
                "success": False,
                "error": "Could not locate target paragraph in document. Please check the search keywords.",
                "search_info": search_info,
                "document_info": {"total_paragraphs": doc_info['total_paragraphs']}
            }

        print(f"✓ Target paragraph found at index: {target_index}")
        print(f"  Match method: {search_info.get('match_method')}")
        print(f"  Paragraph text (preview): {doc_info['paragraphs'][target_index]['text'][:100]}...")

        # === NEW: Extract paragraph context ===
        print("\n[Step 3] Extracting paragraph context...")
        context = self.document_reader.get_context_paragraphs(
            doc_info,
            target_index,
            context_size=2
        )

        print(f"✓ Context extracted (±2 paragraphs)")

        # Build enriched prompt with document context
        enriched_prompt = self._build_enriched_prompt(
            modification_prompt,
            context,
            doc_info
        )

        print("\n[Step 4] Generating and executing Word COM code...")
        print("=" * 80)

        attempt = 0
        current_prompt = enriched_prompt
        last_error = None
        all_attempts = []

        while attempt < max_retries:
            attempt += 1
            print(f"\n{'=' * 80}")
            print(f"Attempt {attempt}/{max_retries}")
            print(f"{'=' * 80}")

            # Generate code
            gen_result = self._generate_code(
                word_file_path=word_file_path,
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
                    "document_info": {
                        "total_paragraphs": doc_info['total_paragraphs'],
                        "target_paragraph_index": target_index
                    },
                    "search_info": search_info,
                    "all_attempts": all_attempts,
                    "generated_code": code
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
        word_file_path: str,
        modification_prompt: str,
        llm_model: str,
        api_keys: dict
    ) -> dict:
        """Generate PowerShell code using LLM (Word COM)"""

        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(word_file_path, modification_prompt)

        print(f"Model: {llm_model}")
        print(f"Word file: {word_file_path}")
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
        """Build system prompt for Word COM code generation"""
        return """You are a Word automation expert. The user will provide:
1. Word file path (.docx)
2. Target paragraph index and context
3. Description of modifications needed (content and/or formatting)

You need to generate complete PowerShell code to execute these modifications using Word COM.

**CRITICAL REQUIREMENT**: ALL code, comments, variable names, error messages, and output text MUST be in English only.
Do NOT use any non-English characters (Chinese, Japanese, etc.) to avoid encoding issues in PowerShell.

Code requirements:
- Complete and executable, including all steps
- Use COM objects to manipulate Word
- Include error handling
- Add comments to explain key steps (in English only)
- Ensure resource cleanup (close Word document)
- Use absolute paths
- **Important**: Only modify the specified paragraph, do not affect other content
- **Important**: Support both content modification and format modification (font, size, color, alignment)

PowerShell Word COM code template:
```powershell
# Word Modification Script
# Target: Paragraph at index [N]
# Modification: [description]

$word = $null
$doc = $null

try {
    # 1. Try to attach to existing Word instance
    try {
        $word = [System.Runtime.InteropServices.Marshal]::GetActiveObject("Word.Application")
        Write-Host "Attached to existing Word instance"
    }
    catch {
        # If no Word running, create new instance
        $word = New-Object -ComObject Word.Application
        $word.Visible = $true
    }

    # 2. Open document
    $absPath = Resolve-Path "path\to\document.docx"
    $doc = $word.Documents.Open($absPath.Path)
    Write-Host "Document opened: $absPath"

    # 3. Access target paragraph (1-based index in Word COM)
    $paragraphIndex = [PARAGRAPH_INDEX] + 1  # Convert from 0-based to 1-based
    $targetParagraph = $doc.Paragraphs.Item($paragraphIndex)

    # 4. Modify content (if needed)
    $targetParagraph.Range.Text = "New content here"

    # 5. Modify formatting (if needed)
    $range = $targetParagraph.Range
    $range.Font.Name = "Microsoft YaHei"
    $range.Font.Size = 14
    $range.Font.Bold = $true
    $range.Font.Italic = $false
    $range.Font.Color = 255  # Red color (RGB as single integer)
    $range.ParagraphFormat.Alignment = 1  # 0=Left, 1=Center, 2=Right, 3=Justify

    # 6. Save document
    $doc.Save()
    Write-Output "Modification completed successfully"

}
catch {
    Write-Error "Error: $_"
    exit 1
}
finally {
    # Cleanup
    if ($null -ne $doc) {
        $doc.Close()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
    }
    if ($null -ne $word) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
```

Important notes:
1. Paragraph index in Word COM is 1-based (first paragraph = 1), so add 1 to the 0-based Python index
2. Color values: Use single integer (e.g., 255 for red, 16711680 for blue) or wdColorAutomatic = -16777216
3. Alignment values: 0=Left, 1=Center, 2=Right, 3=Justify
4. When modifying content, entire paragraph text is replaced (use Find/Replace for partial replacement)
5. Always save the document after modifications
6. Include proper error handling and resource cleanup

Generate ONLY the PowerShell code block, no additional explanation."""

    def _build_user_message(self, word_file_path: str, modification_prompt: str) -> str:
        """Build user message for LLM (Word)"""
        abs_path = Path(word_file_path).resolve()

        message = f"""Please generate PowerShell code to modify this Word document:

Word file path: {abs_path}

Modification requirements:
{modification_prompt}

Generate complete PowerShell code to execute these modifications."""

        return message

    def _build_enriched_prompt(
        self,
        modification_prompt: str,
        context: dict,
        doc_info: dict
    ) -> str:
        """
        Build enriched prompt with document context and paragraph location

        Args:
            modification_prompt: Original prompt from Stage 1
            context: Paragraph context from DocumentReader.get_context_paragraphs()
            doc_info: Full document info

        Returns:
            Enhanced prompt with paragraph location and context
        """

        target = context["target"]
        target_index = context["target_index"]
        before = context["before"]
        after = context["after"]

        # Build context summary
        context_lines = []

        if before:
            context_lines.append("**Context BEFORE target paragraph:**")
            for para in before[-2:]:  # Last 2 paragraphs before
                context_lines.append(f"  [{para['index']}] {para['text'][:80]}...")

        context_lines.append(f"\n**TARGET PARAGRAPH (Index {target_index}, Word COM Index {target_index + 1}):**")
        context_lines.append(f"  Text: {target['text']}")
        context_lines.append(f"  Style: {target['style']}")
        context_lines.append(f"  Font: {target['font_name']}, Size: {target['font_size']}")
        context_lines.append(f"  Bold: {target['bold']}, Italic: {target['italic']}, Underline: {target['underline']}")
        context_lines.append(f"  Alignment: {target['alignment']}")
        if target.get('color_rgb'):
            context_lines.append(f"  Color: RGB{target['color_rgb']}")

        if after:
            context_lines.append("\n**Context AFTER target paragraph:**")
            for para in after[:2]:  # First 2 paragraphs after
                context_lines.append(f"  [{para['index']}] {para['text'][:80]}...")

        context_summary = "\n".join(context_lines)

        # Build enriched prompt
        enriched = f"""
=== DOCUMENT CONTEXT ===

Total paragraphs in document: {doc_info['total_paragraphs']}

{context_summary}

=== ORIGINAL MODIFICATION REQUIREMENTS ===

{modification_prompt}

=== CODE GENERATION INSTRUCTIONS ===

Based on the above context:
1. The target paragraph is at Python index {target_index} (Word COM index {target_index + 1})
2. Generate PowerShell code to modify ONLY this paragraph
3. Use the provided paragraph index to locate the target
4. Apply both content changes and format changes as specified in the requirements
"""

        return enriched

    def _build_retry_prompt(self, original_prompt: str, error: str) -> str:
        """Build retry prompt with error feedback"""
        return f"""{original_prompt}

**IMPORTANT**: The previous code execution failed with the following error:
```
{error}
```

Please analyze the error and fix the code. Common issues to check:
1. Character encoding: Ensure ALL code uses ONLY English characters (no Chinese/non-ASCII)
2. Path issues: Ensure correct absolute paths are used
3. Cell references: Ensure cell references are correct
4. Formula syntax: Ensure Excel formula syntax is correct
5. Data validation: Check if data is empty before using it
6. String literals: Use double quotes for all strings and avoid non-English characters

Generate the fixed complete code with ALL comments, messages, and text in English only."""

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
