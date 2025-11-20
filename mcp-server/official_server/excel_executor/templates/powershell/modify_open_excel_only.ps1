# 严格模式：只修改已打开的Excel
# 如果文件未打开则报错，确保实时修改

param(
    [string]$FileName = "test.xlsx",
    [string]$Range = "K6:K23",
    [double]$Value = 0.005
)

try {
    # 步骤1: 必须连接到已运行的Excel
    Write-Host "Connecting to running Excel instance..."
    try {
        $excel = [System.Runtime.InteropServices.Marshal]::GetActiveObject("Excel.Application")
        Write-Host "Connected to Excel (PID: $($excel.Hwnd))" -ForegroundColor Green
    }
    catch {
        Write-Host "ERROR: No Excel instance is running!" -ForegroundColor Red
        Write-Host "Please open Excel and the target file first." -ForegroundColor Yellow
        exit 1
    }

    # 步骤2: 必须找到已打开的工作簿
    Write-Host "Looking for open workbook: $FileName"
    $workbook = $null

    foreach ($wb in $excel.Workbooks) {
        Write-Host "  Found: $($wb.Name)"
        if ($wb.Name -eq $FileName) {
            $workbook = $wb
            break
        }
    }

    if ($null -eq $workbook) {
        Write-Host "ERROR: File '$FileName' is not open in Excel!" -ForegroundColor Red
        Write-Host "Currently open files:" -ForegroundColor Yellow
        foreach ($wb in $excel.Workbooks) {
            Write-Host "  - $($wb.Name)"
        }
        exit 1
    }

    Write-Host "Found workbook: $($workbook.FullName)" -ForegroundColor Green

    # 步骤3: 修改内存中的数据
    Write-Host "`nModifying range: $Range"
    $sheet = $workbook.Worksheets.Item(1)
    $targetRange = $sheet.Range($Range)

    # 修改前的值
    $oldFirst = $targetRange.Cells.Item(1,1).Value2
    Write-Host "  Old value (first cell): $oldFirst"

    # 执行修改
    $targetRange.Value2 = $Value

    Write-Host "  New value: $Value" -ForegroundColor Cyan

    # 步骤4: 不自动保存，让用户看到并决定
    Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
    Write-Host "Changes are now visible in Excel!" -ForegroundColor Green
    Write-Host "The data is modified in memory (not saved to disk yet)." -ForegroundColor Yellow
    Write-Host "Please save manually if you want to keep the changes (Ctrl+S)." -ForegroundColor Yellow
}
catch {
    Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
# 注意：不清理Excel对象，因为它是用户的实例
