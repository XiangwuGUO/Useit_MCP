"""
Pipeline Manager
Orchestrates the complete two-stage Excel automation pipeline
"""

import sys
from pathlib import Path
from typing import Union

sys.path.insert(0, str(Path(__file__).parent))

from stage1_analyzer import PromptGenerator
from stage2_executor import CodeGenerator


class ExcelAutomationPipeline:
    """
    Complete Excel Automation Pipeline

    Stage 1: Image → modify_prompt.txt
    Stage 2: modify_prompt.txt → Execute PowerShell code
    """

    def __init__(self, workspace_dir: Path = None):
        if workspace_dir is None:
            workspace_dir = Path(__file__).parent / "test_space"
        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Initialize stage modules
        self.stage1 = PromptGenerator(workspace_dir)
        self.stage2 = CodeGenerator(workspace_dir)

    def run_full_pipeline(
        self,
        image_input: Union[str, Path],
        excel_path: Union[str, Path],
        template_path: Union[str, Path] = None,
        modify_prompt_path: Union[str, Path] = None,
        llm_model: str = "gpt-4o",
        max_retries: int = 3,
        api_keys: dict = None
    ) -> dict:
        """
        Run the complete two-stage pipeline

        Args:
            image_input: Excel screenshot (file path or base64)
            excel_path: Path to Excel file to modify
            template_path: Path to prompt template (default: prompt_template.md)
            modify_prompt_path: Where to save modification prompt (default: workspace/modify_prompt.txt)
            llm_model: LLM model (must support vision for stage 1)
            max_retries: Max retry attempts for stage 2
            api_keys: API keys dictionary

        Returns:
            {
                "success": bool,
                "stage1_result": dict,
                "stage2_result": dict,
                "modify_prompt_path": str,
                "error": str (if failed)
            }
        """

        print("\n" + "=" * 80)
        print("EXCEL AUTOMATION PIPELINE - TWO STAGE EXECUTION")
        print("=" * 80)
        print(f"Workspace: {self.workspace_dir}")
        print(f"LLM Model: {llm_model}")
        print(f"Max Retries (Stage 2): {max_retries}")
        print("=" * 80)

        # Set default paths
        if template_path is None:
            template_path = Path(__file__).parent / "prompt_template.md"

        if modify_prompt_path is None:
            modify_prompt_path = self.workspace_dir / "modify_prompt.txt"

        # STAGE 1: Image Analysis
        print("\n" + "🔍" * 40)
        print("Starting STAGE 1: Image Analysis")
        print("🔍" * 40)

        stage1_result = self.stage1.generate_prompt_from_image(
            image_input=image_input,
            template_path=template_path,
            output_path=modify_prompt_path,
            llm_model=llm_model,
            api_keys=api_keys
        )

        if not stage1_result["success"]:
            print("\n✗ STAGE 1 FAILED")
            return {
                "success": False,
                "stage1_result": stage1_result,
                "stage2_result": None,
                "error": f"Stage 1 failed: {stage1_result.get('error')}"
            }

        print(f"\n✓ STAGE 1 COMPLETED")
        print(f"  Modification prompt saved to: {stage1_result['saved_to']}")

        # STAGE 2: Code Generation and Execution
        print("\n" + "⚙️" * 40)
        print("Starting STAGE 2: Code Generation and Execution")
        print("⚙️" * 40)

        # Read the generated modification prompt
        modification_prompt = Path(stage1_result["saved_to"]).read_text(encoding="utf-8")

        stage2_result = self.stage2.generate_and_execute(
            excel_file_path=str(excel_path),
            modification_prompt=modification_prompt,
            llm_model=llm_model,
            api_keys=api_keys,
            max_retries=max_retries
        )

        # Final results
        print("\n" + "=" * 80)
        print("PIPELINE EXECUTION COMPLETED")
        print("=" * 80)

        if stage2_result["success"]:
            print("✓ PIPELINE SUCCESS")
            print(f"  Stage 1: Prompt generated ({stage1_result['token_usage']})")
            print(f"  Stage 2: Code executed successfully after {stage2_result['attempts']} attempt(s)")
            print(f"  Excel file modified: {excel_path}")

            return {
                "success": True,
                "stage1_result": stage1_result,
                "stage2_result": stage2_result,
                "modify_prompt_path": str(stage1_result["saved_to"])
            }
        else:
            print("✗ PIPELINE FAILED at Stage 2")
            print(f"  Error: {stage2_result.get('error')}")

            return {
                "success": False,
                "stage1_result": stage1_result,
                "stage2_result": stage2_result,
                "modify_prompt_path": str(stage1_result["saved_to"]),
                "error": f"Stage 2 failed: {stage2_result.get('error')}"
            }

    def run_stage1_only(
        self,
        image_input: Union[str, Path],
        template_path: Union[str, Path] = None,
        output_path: Union[str, Path] = None,
        llm_model: str = "gpt-4o",
        api_keys: dict = None
    ) -> dict:
        """
        Run only Stage 1: Image Analysis

        Returns the same result as stage1.generate_prompt_from_image()
        """

        if template_path is None:
            template_path = Path(__file__).parent / "prompt_template.md"

        if output_path is None:
            output_path = self.workspace_dir / "modify_prompt.txt"

        return self.stage1.generate_prompt_from_image(
            image_input=image_input,
            template_path=template_path,
            output_path=output_path,
            llm_model=llm_model,
            api_keys=api_keys
        )

    def run_stage2_only(
        self,
        excel_path: Union[str, Path],
        modification_prompt: str,
        llm_model: str = "gpt-4o",
        max_retries: int = 3,
        api_keys: dict = None
    ) -> dict:
        """
        Run only Stage 2: Code Generation and Execution

        Returns the same result as stage2.generate_and_execute()
        """

        return self.stage2.generate_and_execute(
            excel_file_path=str(excel_path),
            modification_prompt=modification_prompt,
            llm_model=llm_model,
            api_keys=api_keys,
            max_retries=max_retries
        )


def main():
    """Demo usage"""
    print("Pipeline Manager Demo")
    print()

    workspace = Path(__file__).parent / "test_space"

    # File paths
    image_path = workspace / "excel_screenshot.png"
    excel_path = workspace / "test.xlsx"
    template_path = Path(__file__).parent / "prompt_template.md"

    # Check files
    if not image_path.exists():
        print(f"Error: Screenshot not found: {image_path}")
        print("Please place an Excel screenshot at the above location.")
        return

    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}")
        return

    if not template_path.exists():
        print(f"Error: Template not found: {template_path}")
        return

    # Get API keys
    from llm.load_api_key import load_api_keys
    api_keys = load_api_keys()

    # Create pipeline
    pipeline = ExcelAutomationPipeline(workspace_dir=workspace)

    # Run full pipeline
    result = pipeline.run_full_pipeline(
        image_input=image_path,
        excel_path=excel_path,
        template_path=template_path,
        llm_model="gpt-4o",
        max_retries=3,
        api_keys=api_keys
    )

    # Show results
    if result["success"]:
        print("\n✓ Pipeline completed successfully!")
        print(f"  Modification prompt: {result['modify_prompt_path']}")
    else:
        print(f"\n✗ Pipeline failed: {result.get('error')}")


if __name__ == "__main__":
    main()
