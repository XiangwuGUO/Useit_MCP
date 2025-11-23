"""
Iterative Excel Automation Pipeline
Multi-round dialogue-based Excel modification with convergence checking
"""

import sys
import json
import time
from pathlib import Path
from typing import Union, List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from excel_screenshot import ExcelScreenshotCapture
from excel_validator import ExcelDataValidator
from stage1_analyzer import PromptGenerator
from stage2_executor import CodeGenerator


class IterativeExcelPipeline:
    """
    Multi-round iterative Excel automation pipeline

    Stage 1: Multi-turn dialogue analysis (maintains conversation history)
    Stage 2: Independent code generation (no history)
    Convergence: Check if all J column values satisfy -0.5 < x < 2
    """

    def __init__(self, workspace_dir: Path = None, conversation_dir: Path = None):
        """
        Initialize iterative pipeline

        Args:
            workspace_dir: Workspace directory for Excel file
            conversation_dir: Directory for conversation history and outputs (default: conv_his)
        """
        if workspace_dir is None:
            workspace_dir = Path(__file__).parent / "test_space"

        if conversation_dir is None:
            conversation_dir = Path(__file__).parent / "conv_his"

        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        self.conversation_dir = conversation_dir
        self.conversation_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.screenshot_capture = ExcelScreenshotCapture()
        self.validator = ExcelDataValidator(lower_bound=-0.5, upper_bound=2.0)
        # Use conversation_dir for stage outputs
        self.stage1_analyzer = PromptGenerator(conversation_dir)
        self.stage2_executor = CodeGenerator(conversation_dir)

        # Iteration state
        self.iteration_history = []

    def run_iterative_pipeline(
        self,
        excel_file_path: Union[str, Path],
        max_iterations: int = 5,
        llm_model: str = "gpt-4o",
        api_keys: dict = None,
        stage2_max_retries: int = 3
    ) -> dict:
        """
        Run multi-round iterative pipeline with convergence checking

        Args:
            excel_file_path: Path to Excel file
            max_iterations: Maximum number of iterations (default: 5)
            llm_model: LLM model to use (must support vision)
            api_keys: API keys dictionary
            stage2_max_retries: Max retries for Stage 2 code execution

        Returns:
            {
                "success": bool,
                "converged": bool,
                "total_rounds": int,
                "final_validation": dict,
                "iteration_history": List[dict],
                "conversation_history_path": str,
                "error": str (if failed)
            }
        """

        print("\n" + "=" * 80)
        print("ITERATIVE EXCEL AUTOMATION PIPELINE")
        print("=" * 80)
        print(f"Excel file: {excel_file_path}")
        print(f"Max iterations: {max_iterations}")
        print(f"LLM model: {llm_model}")
        print(f"Workspace: {self.workspace_dir}")
        print("=" * 80)

        start_time = time.time()

        # Step 1: Open Excel file
        try:
            excel_file_path = Path(excel_file_path)
            if not excel_file_path.exists():
                return {
                    "success": False,
                    "error": f"Excel file not found: {excel_file_path}"
                }

            print(f"\n[Initialization] Opening Excel file...")
            excel_app, workbook = self.screenshot_capture.open_excel_file(
                str(excel_file_path),
                visible=True
            )
            print(f"✓ Excel opened successfully")

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to open Excel: {str(e)}"
            }

        # Step 2: Iterative loop (no conversation manager needed)
        converged = False
        final_validation = None

        for round_num in range(1, max_iterations + 1):
            print(f"\n{'#' * 80}")
            print(f"# ITERATION {round_num}/{max_iterations}")
            print(f"{'#' * 80}")

            iteration_start = time.time()

            # Stage 1: Independent round analysis
            print(f"\n{'=' * 80}")
            print(f"STAGE 1 (Round {round_num}): Independent Round Analysis")
            print(f"{'=' * 80}")

            stage1_result = self.stage1_analyzer.generate_prompt_with_conversation(
                excel_app=excel_app,
                workbook=workbook,
                conversation_manager=None,  # No conversation manager needed
                round_number=round_num,
                llm_model=llm_model,
                api_keys=api_keys,
                save_screenshot=True
            )

            if not stage1_result["success"]:
                print(f"\n✗ Stage 1 (Round {round_num}) FAILED")
                self._record_iteration(round_num, stage1_result, None, None, iteration_start)
                return self._build_failure_result(
                    round_num,
                    f"Stage 1 failed: {stage1_result.get('error')}"
                )

            print(f"\n✓ Stage 1 (Round {round_num}) completed")
            print(f"  Prompt saved: {stage1_result['saved_to']}")

            # Stage 2: Independent code generation and execution
            print(f"\n{'=' * 80}")
            print(f"STAGE 2 (Round {round_num}): Independent Code Generation")
            print(f"{'=' * 80}")

            modification_prompt = stage1_result["prompt_content"]

            stage2_result = self.stage2_executor.generate_and_execute(
                excel_file_path=str(excel_file_path),
                modification_prompt=modification_prompt,
                llm_model=llm_model,
                api_keys=api_keys,
                max_retries=stage2_max_retries
            )

            if not stage2_result["success"]:
                print(f"\n✗ Stage 2 (Round {round_num}) FAILED")
                self._record_iteration(round_num, stage1_result, stage2_result, None, iteration_start)
                return self._build_failure_result(
                    round_num,
                    f"Stage 2 failed: {stage2_result.get('error')}"
                )

            # Save the generated code with round number
            code_path = self.stage2_executor.executor.save_code(
                code=stage2_result["code"],
                language="PowerShell",
                round_number=round_num
            )

            print(f"\n✓ Stage 2 (Round {round_num}) completed")
            print(f"  Code saved: {code_path}")
            print(f"  Execution attempts: {stage2_result['attempts']}")

            # Validation: Check convergence
            print(f"\n{'=' * 80}")
            print(f"CONVERGENCE CHECK (Round {round_num})")
            print(f"{'=' * 80}")

            try:
                validation_result = self.validator.check_convergence(
                    workbook=workbook,
                    column="J",
                    start_row=2,
                    sheet_index=1
                )

                final_validation = validation_result

                # Record iteration
                self._record_iteration(
                    round_num,
                    stage1_result,
                    stage2_result,
                    validation_result,
                    iteration_start
                )

                if validation_result["converged"]:
                    converged = True
                    print(f"\n{'🎉' * 40}")
                    print(f"✓ CONVERGED after {round_num} round(s)!")
                    print(f"  All {validation_result['total_rows']} rows satisfy: -0.5 < J < 2")
                    print(f"{'🎉' * 40}")
                    break
                else:
                    print(f"\n✗ NOT CONVERGED")
                    print(f"  {validation_result['invalid_rows']} rows still out of bounds")
                    print(f"  Continuing to Round {round_num + 1}...")

            except Exception as e:
                print(f"\n✗ Validation failed: {e}")
                return self._build_failure_result(
                    round_num,
                    f"Validation failed: {str(e)}"
                )

        # Save iteration summary to conv_his directory
        summary_path = self._save_iteration_summary(
            total_rounds=len(self.iteration_history),
            converged=converged,
            total_time=time.time() - start_time
        )

        # Build final result
        print(f"\n{'=' * 80}")
        print("PIPELINE EXECUTION COMPLETED")
        print(f"{'=' * 80}")
        print(f"  Total rounds: {len(self.iteration_history)}")
        print(f"  Converged: {'✓ YES' if converged else '✗ NO'}")
        print(f"  Total time: {time.time() - start_time:.1f}s")
        print(f"  Summary: {summary_path}")
        print(f"{'=' * 80}")

        return {
            "success": True,
            "converged": converged,
            "total_rounds": len(self.iteration_history),
            "final_validation": final_validation,
            "iteration_history": self.iteration_history,
            "iteration_summary_path": str(summary_path),
            "excel_app": excel_app,
            "workbook": workbook
        }

    def _record_iteration(
        self,
        round_num: int,
        stage1_result: dict,
        stage2_result: dict,
        validation_result: dict,
        start_time: float
    ):
        """Record iteration details"""
        iteration_time = time.time() - start_time

        record = {
            "round": round_num,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "execution_time": round(iteration_time, 2),
            "stage1": {
                "success": stage1_result.get("success", False),
                "prompt_file": stage1_result.get("saved_to"),
                "screenshot": stage1_result.get("screenshot_path"),
                "token_usage": stage1_result.get("token_usage")
            },
            "stage2": {
                "success": stage2_result.get("success", False) if stage2_result else False,
                "attempts": stage2_result.get("attempts") if stage2_result else None,
                "execution_time": stage2_result.get("execution_result", {}).get("execution_time") if stage2_result else None
            } if stage2_result else None,
            "validation": {
                "converged": validation_result.get("converged", False) if validation_result else False,
                "total_rows": validation_result.get("total_rows") if validation_result else None,
                "invalid_rows": validation_result.get("invalid_rows") if validation_result else None,
                "value_range": [
                    validation_result.get("min_value"),
                    validation_result.get("max_value")
                ] if validation_result else None
            } if validation_result else None
        }

        self.iteration_history.append(record)

    def _build_failure_result(self, round_num: int, error: str) -> dict:
        """Build failure result"""
        return {
            "success": False,
            "converged": False,
            "total_rounds": round_num,
            "iteration_history": self.iteration_history,
            "error": error
        }

    def _save_iteration_summary(
        self,
        total_rounds: int,
        converged: bool,
        total_time: float
    ) -> Path:
        """Save iteration summary to JSON"""
        summary_path = self.conversation_dir / "iteration_summary.json"

        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_rounds": total_rounds,
            "converged": converged,
            "total_time": round(total_time, 2),
            "iterations": self.iteration_history
        }

        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary_path


def main():
    """Demo usage"""
    print("Iterative Excel Automation Pipeline Demo")
    print()

    workspace = Path(__file__).parent / "test_space"
    excel_file = workspace / "test.xlsx"

    if not excel_file.exists():
        print(f"ERROR: Excel file not found: {excel_file}")
        print("Please create test.xlsx in test_space directory")
        return

    # Load API keys
    from llm.load_api_key import load_api_keys
    api_keys = load_api_keys()

    if not api_keys.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in config/api_keys.json")
        return

    # Create pipeline
    conv_dir = Path(__file__).parent / "conv_his"
    pipeline = IterativeExcelPipeline(
        workspace_dir=workspace,
        conversation_dir=conv_dir
    )

    print(f"Excel directory: {workspace}")
    print(f"Output directory: {conv_dir}")
    print()

    # Run iterative pipeline
    result = pipeline.run_iterative_pipeline(
        excel_file_path=excel_file,
        max_iterations=5,
        llm_model="gpt-4o",
        api_keys=api_keys,
        stage2_max_retries=3
    )

    # Show final results
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    if result["success"]:
        if result["converged"]:
            print(f"✓ SUCCESS: Converged after {result['total_rounds']} rounds")
        else:
            print(f"✗ Did not converge after {result['total_rounds']} rounds")
            print(f"  Final validation: {result['final_validation']}")
    else:
        print(f"✗ FAILED: {result.get('error')}")

    print("=" * 80)


if __name__ == "__main__":
    main()
