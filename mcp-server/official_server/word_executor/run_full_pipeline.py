"""
Main Entry Point for Excel Automation Pipeline

Usage:
    python run_full_pipeline.py                              # Run full pipeline
    python run_full_pipeline.py --stage1-only                # Only generate prompt
    python run_full_pipeline.py --stage2-only                # Only execute code
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pipeline_manager import ExcelAutomationPipeline
from llm.load_api_key import load_api_keys


def main():
    parser = argparse.ArgumentParser(
        description="Excel Automation Pipeline - Two Stage Execution"
    )

    # File paths
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Path to Excel screenshot or base64 encoded image (for Stage 1)"
    )
    parser.add_argument(
        "--excel",
        type=str,
        default=None,
        help="Path to Excel file to modify"
    )
    parser.add_argument(
        "--template",
        type=str,
        default="prompt_template.md",
        help="Path to prompt template (default: prompt_template.md)"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Path to modification prompt file (default: test_space/modify_prompt.txt)"
    )

    # Execution options
    parser.add_argument(
        "--stage1-only",
        action="store_true",
        help="Run only Stage 1 (image analysis)"
    )
    parser.add_argument(
        "--stage2-only",
        action="store_true",
        help="Run only Stage 2 (code execution)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="LLM model to use (default: gpt-4o)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for Stage 2 (default: 3)"
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="test_space",
        help="Workspace directory (default: test_space)"
    )

    args = parser.parse_args()

    # Setup workspace
    workspace = Path(__file__).parent / args.workspace
    workspace.mkdir(parents=True, exist_ok=True)

    # Set default paths if not specified
    if args.image is None:
        args.image = workspace / "excel_screenshot.png"

    if args.excel is None:
        args.excel = workspace / "test.xlsx"

    if args.prompt is None:
        args.prompt = workspace / "modify_prompt.txt"

    # Load API keys
    print("Loading API keys...")
    api_keys = load_api_keys()

    if not api_keys.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in config/api_keys.json")
        sys.exit(1)

    print(f"✓ API Key loaded: {api_keys['OPENAI_API_KEY'][:10]}...")
    print()

    # Create pipeline
    pipeline = ExcelAutomationPipeline(workspace_dir=workspace)

    # Execute based on mode
    if args.stage1_only:
        # Run only Stage 1
        print("=" * 80)
        print("MODE: Stage 1 Only (Image Analysis)")
        print("=" * 80)

        if not Path(args.image).exists():
            print(f"ERROR: Image file not found: {args.image}")
            sys.exit(1)

        result = pipeline.run_stage1_only(
            image_input=args.image,
            template_path=args.template,
            output_path=args.prompt,
            llm_model=args.model,
            api_keys=api_keys
        )

        if result["success"]:
            print(f"\n✓ Stage 1 completed successfully!")
            print(f"  Prompt saved to: {result['saved_to']}")
            print(f"\nNext step: Review the prompt and run Stage 2")
        else:
            print(f"\n✗ Stage 1 failed: {result.get('error')}")
            sys.exit(1)

    elif args.stage2_only:
        # Run only Stage 2
        print("=" * 80)
        print("MODE: Stage 2 Only (Code Execution)")
        print("=" * 80)

        if not Path(args.excel).exists():
            print(f"ERROR: Excel file not found: {args.excel}")
            sys.exit(1)

        if not Path(args.prompt).exists():
            print(f"ERROR: Prompt file not found: {args.prompt}")
            sys.exit(1)

        # Read modification prompt
        modification_prompt = Path(args.prompt).read_text(encoding="utf-8")

        result = pipeline.run_stage2_only(
            excel_path=args.excel,
            modification_prompt=modification_prompt,
            llm_model=args.model,
            max_retries=args.max_retries,
            api_keys=api_keys
        )

        if result["success"]:
            print(f"\n✓ Stage 2 completed successfully!")
            print(f"  Attempts: {result['attempts']}")
            print(f"  Excel file modified: {args.excel}")
        else:
            print(f"\n✗ Stage 2 failed: {result.get('error')}")
            sys.exit(1)

    else:
        # Run full pipeline (both stages)
        print("=" * 80)
        print("MODE: Full Pipeline (Stage 1 + Stage 2)")
        print("=" * 80)

        if not Path(args.image).exists():
            print(f"ERROR: Image file not found: {args.image}")
            sys.exit(1)

        if not Path(args.excel).exists():
            print(f"ERROR: Excel file not found: {args.excel}")
            sys.exit(1)

        result = pipeline.run_full_pipeline(
            image_input=args.image,
            excel_path=args.excel,
            template_path=args.template,
            modify_prompt_path=args.prompt,
            llm_model=args.model,
            max_retries=args.max_retries,
            api_keys=api_keys
        )

        if result["success"]:
            print(f"\n✓ Full pipeline completed successfully!")
            print(f"  Modification prompt: {result['modify_prompt_path']}")
            print(f"  Excel file modified: {args.excel}")
        else:
            print(f"\n✗ Pipeline failed: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
