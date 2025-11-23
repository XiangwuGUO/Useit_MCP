"""
Excel Data Validator
Validates J column data and checks convergence conditions
"""

import sys
from pathlib import Path
from typing import List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))

# Try to import pywin32
try:
    import win32com.client
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("Warning: pywin32 not available")


class ExcelDataValidator:
    """
    Validator for Excel J column data
    Checks if all values satisfy: -0.5 < x < 2
    """

    def __init__(self, lower_bound: float = -0.5, upper_bound: float = 2.0):
        """
        Initialize validator with bounds

        Args:
            lower_bound: Lower bound for J column values (default: -0.5)
            upper_bound: Upper bound for J column values (default: 2.0)
        """
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

    def read_column_j_values(
        self,
        workbook: object,
        column: str = "J",
        start_row: int = 2,
        sheet_index: int = 1
    ) -> List[Tuple[int, float]]:
        """
        Read all values from column J

        Args:
            workbook: Excel workbook COM object
            column: Column letter (default: "J")
            start_row: Starting row number (default: 2, skip header)
            sheet_index: Sheet index (default: 1) - ALWAYS uses Sheet1

        Returns:
            List of (row_number, value) tuples
        """
        if not PYWIN32_AVAILABLE:
            raise RuntimeError("pywin32 is required for Excel data validation")

        # IMPORTANT: Always use Sheet1 explicitly
        try:
            # Try by name first
            sheet = workbook.Worksheets("Sheet1")
        except:
            # Fallback to index (1-based)
            sheet = workbook.Worksheets(sheet_index)

        values = []
        row = start_row

        # Read until we hit an empty cell in column C (distance)
        while True:
            # Check if row has data (check column C for distance)
            c_value = sheet.Range(f"C{row}").Value
            if c_value is None or c_value == "":
                break

            # Read J column value
            j_value = sheet.Range(f"{column}{row}").Value

            # Skip if J is empty or not a number
            if j_value is not None and isinstance(j_value, (int, float)):
                values.append((row, float(j_value)))

            row += 1

        return values

    def validate_values(
        self,
        values: List[Tuple[int, float]]
    ) -> dict:
        """
        Validate if all values are within bounds

        Args:
            values: List of (row_number, value) tuples

        Returns:
            {
                "converged": bool,
                "total_rows": int,
                "valid_rows": int,
                "invalid_rows": int,
                "out_of_bounds": List[Tuple[int, float, str]],  # (row, value, reason)
                "min_value": float,
                "max_value": float
            }
        """
        if not values:
            return {
                "converged": True,
                "total_rows": 0,
                "valid_rows": 0,
                "invalid_rows": 0,
                "out_of_bounds": [],
                "min_value": None,
                "max_value": None
            }

        out_of_bounds = []

        for row, value in values:
            if value <= self.lower_bound:
                out_of_bounds.append((row, value, f"J <= {self.lower_bound} (悬空)"))
            elif value >= self.upper_bound:
                out_of_bounds.append((row, value, f"J >= {self.upper_bound} (挖太深)"))

        all_values = [v for _, v in values]

        return {
            "converged": len(out_of_bounds) == 0,
            "total_rows": len(values),
            "valid_rows": len(values) - len(out_of_bounds),
            "invalid_rows": len(out_of_bounds),
            "out_of_bounds": out_of_bounds,
            "min_value": min(all_values) if all_values else None,
            "max_value": max(all_values) if all_values else None
        }

    def check_convergence(
        self,
        workbook: object,
        column: str = "J",
        start_row: int = 2,
        sheet_index: int = 1
    ) -> dict:
        """
        Check if Excel data has converged (all J values in bounds)

        Args:
            workbook: Excel workbook COM object
            column: Column letter (default: "J")
            start_row: Starting row number (default: 2)
            sheet_index: Sheet index (default: 1)

        Returns:
            Validation result dict
        """
        print(f"\nValidating {column} column data...")

        values = self.read_column_j_values(
            workbook=workbook,
            column=column,
            start_row=start_row,
            sheet_index=sheet_index
        )

        result = self.validate_values(values)

        # Print summary
        print(f"  Total rows: {result['total_rows']}")
        print(f"  Valid rows: {result['valid_rows']}")
        print(f"  Invalid rows: {result['invalid_rows']}")

        if result['min_value'] is not None and result['max_value'] is not None:
            print(f"  Value range: [{result['min_value']:.3f}, {result['max_value']:.3f}]")
        print(f"  Required range: ({self.lower_bound}, {self.upper_bound})")

        if result['converged']:
            print("  ✓ CONVERGED: All values within bounds!")
        else:
            print(f"  ✗ NOT CONVERGED: {result['invalid_rows']} rows out of bounds")
            print("\n  Out of bounds rows:")
            for row, value, reason in result['out_of_bounds'][:10]:  # Show first 10
                print(f"    Row {row}: J = {value:.3f} ({reason})")
            if len(result['out_of_bounds']) > 10:
                print(f"    ... and {len(result['out_of_bounds']) - 10} more")

        return result

    def check_convergence_from_file(
        self,
        excel_file_path: str,
        column: str = "J",
        start_row: int = 2,
        sheet_index: int = 1
    ) -> dict:
        """
        Check convergence by opening Excel file

        Args:
            excel_file_path: Path to Excel file
            column: Column letter
            start_row: Starting row number
            sheet_index: Sheet index

        Returns:
            Validation result dict with excel_app and workbook
        """
        if not PYWIN32_AVAILABLE:
            raise RuntimeError("pywin32 is required")

        abs_path = str(Path(excel_file_path).resolve())

        # Try to attach to existing instance
        try:
            excel = win32com.client.GetActiveObject("Excel.Application")
            attached = True
        except:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            attached = False

        try:
            # Find or open workbook
            workbook = None
            for wb in excel.Workbooks:
                if wb.FullName.lower() == abs_path.lower():
                    workbook = wb
                    break

            if not workbook:
                workbook = excel.Workbooks.Open(abs_path)

            # Check convergence
            result = self.check_convergence(
                workbook=workbook,
                column=column,
                start_row=start_row,
                sheet_index=sheet_index
            )

            result["excel_app"] = excel
            result["workbook"] = workbook
            result["attached"] = attached

            return result

        except Exception as e:
            # Cleanup on error
            if not attached:
                try:
                    excel.Quit()
                except:
                    pass
            raise e


def demo_validation():
    """Demo: Validate Excel J column"""
    print("=" * 80)
    print("EXCEL DATA VALIDATOR DEMO")
    print("=" * 80)
    print()

    workspace = Path(__file__).parent / "test_space"
    excel_file = workspace / "test.xlsx"

    if not excel_file.exists():
        print(f"ERROR: Excel file not found: {excel_file}")
        return

    if not PYWIN32_AVAILABLE:
        print("ERROR: pywin32 not available")
        print("Install: pip install pywin32")
        return

    # Create validator
    validator = ExcelDataValidator(lower_bound=-0.5, upper_bound=2.0)

    try:
        # Validate from file
        result = validator.check_convergence_from_file(
            excel_file_path=str(excel_file),
            column="J",
            start_row=2
        )

        print("\n" + "=" * 80)
        print("VALIDATION RESULT")
        print("=" * 80)

        if result["converged"]:
            print("✓ SUCCESS: All J values are within bounds!")
        else:
            print("✗ FAILED: Some J values are out of bounds")
            print(f"\nAction needed: {result['invalid_rows']} rows require adjustment")

        print("\nExcel window left open for inspection")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_validation()
