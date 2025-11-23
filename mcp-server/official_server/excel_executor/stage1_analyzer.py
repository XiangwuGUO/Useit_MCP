"""
Stage 1: Image Analyzer
Analyzes Excel screenshots and generates modification prompts
"""

import sys
import base64
from pathlib import Path
from typing import Union, Optional

sys.path.insert(0, str(Path(__file__).parent))

from llm.run_llm import run_llm
from llm.llm_utils import encode_image, is_image_path
from excel_screenshot import ExcelScreenshotCapture


class PromptGenerator:
    """
    Stage 1: Generate modification prompt from Excel screenshot

    Input: Image (file path or base64) + Template
    Output: modify_prompt.txt
    """

    def __init__(self, workspace_dir: Path = None):
        if workspace_dir is None:
            workspace_dir = Path(__file__).parent / "test_space"
        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_capture = ExcelScreenshotCapture()

    def generate_prompt_from_excel(
        self,
        excel_file_path: Union[str, Path],
        template_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        llm_model: str = "gpt-4o",
        api_keys: dict = None,
        save_screenshot: bool = True
    ) -> dict:
        """
        Open Excel file, capture screenshot, and generate modification prompt

        Args:
            excel_file_path: Path to Excel file to open and analyze
            template_path: Path to prompt template (prompt_template.md)
            output_path: Where to save the generated prompt (default: workspace/modify_prompt.txt)
            llm_model: Vision-capable LLM model
            api_keys: API keys dictionary
            save_screenshot: Whether to save the captured screenshot

        Returns:
            {
                "success": bool,
                "prompt_content": str,
                "saved_to": str,
                "screenshot_path": str (if saved),
                "token_usage": dict,
                "excel_app": object (Excel COM object, left open),
                "workbook": object (Workbook object, left open),
                "error": str (if failed)
            }
        """

        print("=" * 80)
        print("STAGE 1: Excel Analysis - Open, Capture, Generate Prompt")
        print("=" * 80)

        # Open Excel file
        try:
            excel_file_path = Path(excel_file_path)
            if not excel_file_path.exists():
                return {
                    "success": False,
                    "error": f"Excel file not found: {excel_file_path}"
                }

            print(f"\n[1/4] Opening Excel file: {excel_file_path}")
            excel_app, workbook = self.screenshot_capture.open_excel_file(str(excel_file_path))
            print(f"✓ Excel opened successfully")

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to open Excel file: {str(e)}"
            }

        # Capture screenshot
        try:
            print(f"\n[2/4] Capturing Excel screenshot...")
            screenshot_path = None
            if save_screenshot:
                screenshot_path = self.workspace_dir / f"{excel_file_path.stem}_screenshot.png"
                image_input = self.screenshot_capture.capture_excel_screenshot(
                    excel_app=excel_app,
                    save_path=str(screenshot_path)
                )
                print(f"✓ Screenshot captured and saved: {screenshot_path}")
            else:
                # Capture as base64
                image_input = self.screenshot_capture.capture_and_encode_base64(excel_app=excel_app)
                print(f"✓ Screenshot captured (base64, length: {len(image_input)})")

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to capture screenshot: {str(e)}",
                "excel_app": excel_app,
                "workbook": workbook
            }

        # Continue with existing logic
        return self._generate_prompt_from_image_internal(
            image_input=image_input if not save_screenshot else str(screenshot_path),
            template_path=template_path,
            output_path=output_path,
            llm_model=llm_model,
            api_keys=api_keys,
            excel_app=excel_app,
            workbook=workbook,
            screenshot_path=screenshot_path
        )

    def generate_prompt_from_image(
        self,
        image_input: Union[str, Path],
        template_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        llm_model: str = "gpt-4o",
        api_keys: dict = None
    ) -> dict:
        """
        Analyze Excel screenshot and generate modification prompt
        (Legacy method - use generate_prompt_from_excel for direct Excel file processing)

        Args:
            image_input: Image file path or base64 encoded string
            template_path: Path to prompt template (prompt_template.md)
            output_path: Where to save the generated prompt (default: workspace/modify_prompt.txt)
            llm_model: Vision-capable LLM model
            api_keys: API keys dictionary

        Returns:
            {
                "success": bool,
                "prompt_content": str,
                "saved_to": str,
                "token_usage": dict,
                "error": str (if failed)
            }
        """
        return self._generate_prompt_from_image_internal(
            image_input=image_input,
            template_path=template_path,
            output_path=output_path,
            llm_model=llm_model,
            api_keys=api_keys
        )

    def _generate_prompt_from_image_internal(
        self,
        image_input: Union[str, Path],
        template_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        llm_model: str = "gpt-4o",
        api_keys: dict = None,
        excel_app: object = None,
        workbook: object = None,
        screenshot_path: Optional[Path] = None
    ) -> dict:
        """
        Internal method: Analyze image and generate modification prompt

        Args:
            image_input: Image file path or base64 encoded string
            template_path: Path to prompt template
            output_path: Where to save the generated prompt
            llm_model: Vision-capable LLM model
            api_keys: API keys dictionary
            excel_app: Excel COM object (will be included in result if provided)
            workbook: Workbook object (will be included in result if provided)
            screenshot_path: Path where screenshot was saved (will be included in result if provided)

        Returns:
            dict with success status and results
        """

        print(f"\n[3/4] Analyzing screenshot with LLM")
        print("=" * 80)

        # Set default output path
        if output_path is None:
            output_path = self.workspace_dir / "modify_prompt.txt"
        output_path = Path(output_path)

        # Read template
        try:
            template_path = Path(template_path)
            if not template_path.exists():
                result = {
                    "success": False,
                    "error": f"Template file not found: {template_path}"
                }
                if excel_app:
                    result["excel_app"] = excel_app
                    result["workbook"] = workbook
                return result

            template_content = template_path.read_text(encoding="utf-8")
            print(f"✓ Template loaded: {template_path}")
            print(f"  Template length: {len(template_content)} characters")
        except Exception as e:
            result = {
                "success": False,
                "error": f"Failed to read template: {str(e)}"
            }
            if excel_app:
                result["excel_app"] = excel_app
                result["workbook"] = workbook
            return result

        # Prepare image input
        try:
            image_content = self._prepare_image_input(image_input)
            print(f"✓ Image prepared")
        except Exception as e:
            result = {
                "success": False,
                "error": f"Failed to prepare image: {str(e)}"
            }
            if excel_app:
                result["excel_app"] = excel_app
                result["workbook"] = workbook
            return result

        # Build messages for LLM
        messages = [{
            "content": [
                image_content,  # Image first
                template_content  # Then template instructions
            ]
        }]

        system_prompt = """You are an Excel automation analysis expert.
You will receive an Excel screenshot and a task template.
Analyze the screenshot carefully and generate a detailed modification plan following the template instructions.

Output the complete modification plan in plain text."""

        print(f"\nCalling vision model: {llm_model}")
        print(f"Sending image + template to LLM...")

        # Call LLM
        try:
            response_text, token_usage = run_llm(
                messages=messages,
                system=system_prompt,
                llm=llm_model,
                max_tokens=4096,
                temperature=0,
                api_keys=api_keys
            )

            print(f"✓ LLM response received")
            print(f"  Token usage: {token_usage}")
            print(f"  Response length: {len(response_text)} characters")

        except Exception as e:
            result = {
                "success": False,
                "error": f"LLM call failed: {str(e)}"
            }
            if excel_app:
                result["excel_app"] = excel_app
                result["workbook"] = workbook
            return result

        # Save to file
        print(f"\n[4/4] Saving modification prompt")
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(response_text, encoding="utf-8")
            print(f"✓ Prompt saved to: {output_path}")
        except Exception as e:
            result = {
                "success": False,
                "error": f"Failed to save prompt: {str(e)}"
            }
            if excel_app:
                result["excel_app"] = excel_app
                result["workbook"] = workbook
            return result

        print("\n" + "=" * 80)
        print("STAGE 1 COMPLETED SUCCESSFULLY")
        if excel_app:
            print("Excel window left OPEN for Stage 2 execution")
        print("=" * 80)

        result = {
            "success": True,
            "prompt_content": response_text,
            "saved_to": str(output_path),
            "token_usage": token_usage
        }

        # Include Excel objects if provided
        if excel_app:
            result["excel_app"] = excel_app
            result["workbook"] = workbook

        # Include screenshot path if provided
        if screenshot_path:
            result["screenshot_path"] = str(screenshot_path)

        return result

    def generate_prompt_with_conversation(
        self,
        excel_app: object,
        workbook: object,
        conversation_manager: object = None,  # Not used, kept for API compatibility
        round_number: int = 1,
        llm_model: str = "gpt-4o",
        api_keys: dict = None,
        save_screenshot: bool = True
    ) -> dict:
        """
        Generate modification prompt using conversation history (multi-turn dialogue)

        Args:
            excel_app: Excel COM object (already opened)
            workbook: Workbook object (already opened)
            round_number: Current round number (1, 2, 3...)
            llm_model: Vision-capable LLM model
            api_keys: API keys dictionary
            save_screenshot: Whether to save the captured screenshot

        Returns:
            {
                "success": bool,
                "prompt_content": str,
                "saved_to": str,
                "screenshot_path": str,
                "round_number": int,
                "error": str (if failed)
            }
        """

        print(f"\n{'=' * 80}")
        print(f"STAGE 1 (Round {round_number}): Multi-Turn Dialogue Analysis")
        print(f"{'=' * 80}")

        # 1. Capture screenshot
        try:
            print(f"\n[1/4] Capturing Excel screenshot (Round {round_number})...")
            screenshot_path = None
            if save_screenshot:
                screenshot_path = self.workspace_dir / f"screenshot_{round_number}.png"
                self.screenshot_capture.capture_excel_screenshot(
                    excel_app=excel_app,
                    save_path=str(screenshot_path)
                )
                print(f"✓ Screenshot captured: {screenshot_path}")
            else:
                screenshot_base64 = self.screenshot_capture.capture_and_encode_base64(excel_app=excel_app)
                screenshot_path = screenshot_base64  # Use base64 string
                print(f"✓ Screenshot captured (base64)")

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to capture screenshot: {str(e)}",
                "round_number": round_number
            }

        # 2. Load unified template (same template for all rounds)
        try:
            print(f"\n[2/4] Loading template for Round {round_number}...")
            template_path = Path(__file__).parent / "prompt_template.md"

            if not template_path.exists():
                return {
                    "success": False,
                    "error": f"Template not found: {template_path}",
                    "round_number": round_number
                }

            template_content = template_path.read_text(encoding="utf-8")

            # Replace round number placeholder "第 N 轮" → "第 1 轮", "第 2 轮", etc.
            template_content = template_content.replace("第 N 轮", f"第 {round_number} 轮")
            print(f"✓ Template loaded: {template_path.name} (轮次: 第 {round_number} 轮)")
            print(f"  Template length: {len(template_content)} characters")

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load template: {str(e)}",
                "round_number": round_number
            }

        # 3. Prepare image content for LLM
        print(f"\n[3/4] Preparing image for LLM...")
        try:
            if save_screenshot:
                # Use file path
                image_content = str(screenshot_path)
            else:
                # Use base64
                image_content = screenshot_path  # Already base64 from step 1

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to prepare image: {str(e)}",
                "round_number": round_number
            }

        # 4. Call LLM with ONLY current round (no history)
        try:
            print(f"\n[4/4] Calling vision model: {llm_model}")
            print(f"Mode: Independent round (no conversation history)")

            # Build messages for current round only
            messages = [{
                "content": [
                    image_content,    # Current screenshot
                    template_content  # Unified template with round number
                ]
            }]

            system_prompt = """You are an Excel automation analysis expert specializing in civil engineering.
You will receive an Excel screenshot showing channel longitudinal profile data and a task template.
Analyze the screenshot carefully and generate a detailed modification plan following the template instructions.

Output the complete modification plan in plain text."""

            response_text, token_usage = run_llm(
                messages=messages,
                system=system_prompt,
                llm=llm_model,
                max_tokens=4096,
                temperature=0,
                api_keys=api_keys
            )

            print(f"✓ LLM response received")
            print(f"  Token usage: {token_usage}")
            print(f"  Response length: {len(response_text)} characters")

        except Exception as e:
            return {
                "success": False,
                "error": f"LLM call failed: {str(e)}",
                "round_number": round_number
            }

        # 5. Save to file
        try:
            print(f"\n[5/5] Saving modification prompt...")
            output_path = self.workspace_dir / f"modify_prompt_{round_number}.txt"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(response_text, encoding="utf-8")
            print(f"✓ Prompt saved to: {output_path}")

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to save prompt: {str(e)}",
                "round_number": round_number
            }

        print(f"\n{'=' * 80}")
        print(f"STAGE 1 (Round {round_number}) COMPLETED SUCCESSFULLY")
        print(f"{'=' * 80}")

        return {
            "success": True,
            "prompt_content": response_text,
            "saved_to": str(output_path),
            "screenshot_path": str(screenshot_path) if save_screenshot else None,
            "round_number": round_number,
            "token_usage": token_usage
        }

    def _prepare_image_input(self, image_input: Union[str, Path]) -> str:
        """
        Prepare image input for LLM

        Args:
            image_input: Either a file path or base64 encoded string

        Returns:
            Image content (file path or base64 string) ready for LLM
        """
        if isinstance(image_input, Path):
            image_input = str(image_input)

        # Check if it's a file path
        if is_image_path(image_input) and Path(image_input).exists():
            print(f"  Image source: File path - {image_input}")
            return image_input

        # Check if it's base64 encoded data
        elif isinstance(image_input, str) and len(image_input) > 100:
            # Assume it's base64 if it's a long string
            print(f"  Image source: Base64 encoded (length: {len(image_input)})")
            return image_input

        else:
            raise ValueError(f"Invalid image input: {image_input[:100]}...")


def main():
    """Demo usage"""
    print("Stage 1 Analyzer Demo")
    print()

    # Example: Analyze an image
    workspace = Path(__file__).parent / "test_space"

    # You need to provide an actual image path
    image_path = workspace / "excel_screenshot.png"
    template_path = Path(__file__).parent / "prompt_template.md"

    if not image_path.exists():
        print(f"Error: Screenshot not found: {image_path}")
        print("Please place an Excel screenshot at the above location.")
        return

    if not template_path.exists():
        print(f"Error: Template not found: {template_path}")
        return

    # Get API keys
    from llm.load_api_key import load_api_keys
    api_keys = load_api_keys()

    # Create analyzer
    analyzer = PromptGenerator(workspace_dir=workspace)

    # Generate prompt
    result = analyzer.generate_prompt_from_image(
        image_input=image_path,
        template_path=template_path,
        llm_model="gpt-4o",
        api_keys=api_keys
    )

    if result["success"]:
        print(f"\n✓ Success! Prompt generated at: {result['saved_to']}")
        print(f"\nPreview (first 500 chars):")
        print(result["prompt_content"][:500])
    else:
        print(f"\n✗ Failed: {result['error']}")


if __name__ == "__main__":
    main()
