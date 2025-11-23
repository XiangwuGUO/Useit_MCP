"""
Excel Screenshot Capture Module
Captures screenshots of active Excel windows using pywin32 or pyautogui
"""

import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import io

# Try to import pywin32 first (more reliable for Excel COM)
try:
    import win32com.client
    import win32gui
    import win32ui
    import win32con
    from ctypes import windll
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("Warning: pywin32 not available, will try pyautogui as fallback")

# Try to import pyautogui as fallback
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("Warning: pyautogui not available")


class ExcelScreenshotCapture:
    """
    Capture screenshots of Excel windows
    Supports both pywin32 (preferred) and pyautogui (fallback)
    """

    def __init__(self):
        self.method = self._detect_available_method()

    def _detect_available_method(self) -> str:
        """Detect which screenshot method is available"""
        if PYWIN32_AVAILABLE:
            return "pywin32"
        elif PYAUTOGUI_AVAILABLE:
            return "pyautogui"
        else:
            raise RuntimeError("No screenshot library available. Install pywin32 or pyautogui.")

    def open_excel_file(self, file_path: str, visible: bool = True) -> Tuple[object, object]:
        """
        Open Excel file using COM object

        Args:
            file_path: Path to Excel file
            visible: Whether to make Excel visible

        Returns:
            (excel_app, workbook) tuple
        """
        if not PYWIN32_AVAILABLE:
            raise RuntimeError("pywin32 is required to open Excel files")

        abs_path = str(Path(file_path).resolve())

        # Try to attach to existing Excel instance first
        try:
            excel = win32com.client.GetActiveObject("Excel.Application")
            print("Attached to existing Excel instance")

            # Check if file is already open
            for wb in excel.Workbooks:
                if wb.FullName.lower() == abs_path.lower():
                    print(f"File already open: {abs_path}")
                    workbook = wb
                    break
            else:
                # File not open, open it
                workbook = excel.Workbooks.Open(abs_path)
                print(f"Opened file in existing instance: {abs_path}")

        except:
            # No existing instance, create new one
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = visible
            workbook = excel.Workbooks.Open(abs_path)
            print(f"Created new Excel instance and opened: {abs_path}")

        # Make sure it's visible for screenshot
        excel.Visible = True

        # Give Excel time to render
        time.sleep(1)

        return excel, workbook

    def capture_excel_window_pywin32(
        self,
        excel_app: object = None,
        window_title: str = None
    ) -> Image.Image:
        """
        Capture Excel window using pywin32

        Args:
            excel_app: Excel COM object (if available)
            window_title: Window title to find (if excel_app not provided)

        Returns:
            PIL Image object
        """
        if not PYWIN32_AVAILABLE:
            raise RuntimeError("pywin32 not available")

        # Find Excel window
        if excel_app:
            # Get window handle from Excel app
            hwnd = excel_app.Hwnd
        elif window_title:
            # Find window by title
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                raise ValueError(f"Window not found: {window_title}")
        else:
            # Find any Excel window
            hwnd = win32gui.FindWindow("XLMAIN", None)
            if not hwnd:
                raise ValueError("No Excel window found")

        # Bring window to foreground
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)  # Wait for window to come to front

        # Get window dimensions
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        # Capture window
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)

        # Copy window content
        result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

        # Convert to PIL Image
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)

        img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1
        )

        # Cleanup
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

        return img

    def capture_excel_window_pyautogui(
        self,
        region: Tuple[int, int, int, int] = None
    ) -> Image.Image:
        """
        Capture Excel window using pyautogui

        Args:
            region: (left, top, width, height) to capture specific region

        Returns:
            PIL Image object
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not available")

        # Wait a bit for window to be ready
        time.sleep(0.5)

        # Capture screenshot
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()

        return screenshot

    def capture_excel_screenshot(
        self,
        excel_app: object = None,
        window_title: str = None,
        save_path: Optional[str] = None
    ) -> Image.Image:
        """
        Capture Excel screenshot using best available method

        Args:
            excel_app: Excel COM object (preferred for pywin32)
            window_title: Window title to find
            save_path: Optional path to save screenshot

        Returns:
            PIL Image object
        """
        print(f"Capturing Excel screenshot using {self.method}...")

        if self.method == "pywin32":
            img = self.capture_excel_window_pywin32(excel_app, window_title)
        else:
            img = self.capture_excel_window_pyautogui()

        if save_path:
            img.save(save_path)
            print(f"Screenshot saved to: {save_path}")

        return img

    def capture_and_encode_base64(
        self,
        excel_app: object = None,
        window_title: str = None
    ) -> str:
        """
        Capture screenshot and return as base64 encoded string

        Args:
            excel_app: Excel COM object
            window_title: Window title to find

        Returns:
            Base64 encoded image string
        """
        import base64

        img = self.capture_excel_screenshot(excel_app, window_title)

        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        return img_base64


def demo_capture():
    """Demo: Capture Excel screenshot"""
    print("Excel Screenshot Capture Demo")
    print("=" * 80)

    # Check availability
    print(f"pywin32 available: {PYWIN32_AVAILABLE}")
    print(f"pyautogui available: {PYAUTOGUI_AVAILABLE}")
    print()

    if not PYWIN32_AVAILABLE and not PYAUTOGUI_AVAILABLE:
        print("ERROR: No screenshot library available!")
        print("Install: pip install pywin32 pyautogui")
        return

    # Create capture instance
    capture = ExcelScreenshotCapture()
    print(f"Using method: {capture.method}")
    print()

    # Demo 1: Open Excel file and capture
    workspace = Path(__file__).parent / "test_space"
    excel_file = workspace / "test.xlsx"

    if not excel_file.exists():
        print(f"ERROR: Excel file not found: {excel_file}")
        print("Please create test.xlsx in test_space directory")
        return

    try:
        # Open Excel file
        print(f"Opening Excel file: {excel_file}")
        excel, workbook = capture.open_excel_file(str(excel_file))

        # Wait for Excel to be ready
        time.sleep(2)

        # Capture screenshot
        screenshot_path = workspace / "excel_screenshot_auto.png"
        img = capture.capture_excel_screenshot(
            excel_app=excel,
            save_path=str(screenshot_path)
        )

        print(f"✓ Screenshot captured: {img.size}")
        print(f"✓ Saved to: {screenshot_path}")

        # Demo 2: Capture as base64
        print("\nCapturing as base64...")
        img_base64 = capture.capture_and_encode_base64(excel_app=excel)
        print(f"✓ Base64 length: {len(img_base64)} characters")

        print("\n✓ Demo completed successfully!")
        print("\nNote: Excel window is left open for inspection")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_capture()
