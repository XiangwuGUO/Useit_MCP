# 智能Excel修改脚本
# 优先附加到已运行的Excel实例，实时修改内存数据

param(
    [string]$FilePath = "test.xlsx",
    [string]$Range = "K6:K23",
    [double]$Value = 0.005
)

$excel = $null
$workbook = $null
$attachedToExisting = $false

try {
    # 步骤1: 尝试附加到已运行的Excel实例
    Write-Host "Attempting to attach to running Excel instance..."
    try {
        $excel = [System.Runtime.InteropServices.Marshal]::GetActiveObject("Excel.Application")
        $attachedToExisting = $true
        Write-Host "Successfully attached to existing Excel instance" -ForegroundColor Green
    }
    catch {
        Write-Host "No running Excel found, creating new instance..." -ForegroundColor Yellow
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $true  # 新实例设为可见
        $attachedToExisting = $false
    }

    # 步骤2: 在已打开的工作簿中查找目标文件
    $fileName = Split-Path $FilePath -Leaf
    Write-Host "Looking for workbook: $fileName"

    foreach ($wb in $excel.Workbooks) {
        if ($wb.Name -eq $fileName) {
            $workbook = $wb
            Write-Host "Found open workbook: $($wb.FullName)" -ForegroundColor Green
            break
        }
    }

    # 步骤3: 如果没找到，打开文件
    if ($null -eq $workbook) {
        Write-Host "Workbook not open, opening file..." -ForegroundColor Yellow
        $absolutePath = (Resolve-Path $FilePath).Path
        $workbook = $excel.Workbooks.Open($absolutePath)
        Write-Host "Opened: $absolutePath" -ForegroundColor Green
    }

    # 步骤4: 直接修改内存中的数据
    Write-Host "`nModifying cells in memory..."
    $sheet = $workbook.Worksheets.Item(1)
    $targetRange = $sheet.Range($Range)

    # 显示修改前的值（示例）
    $oldValue = $targetRange.Cells.Item(1,1).Value2
    Write-Host "Old value (first cell): $oldValue"

    # 执行修改
    $targetRange.Value2 = $Value

    Write-Host "New value: $Value" -ForegroundColor Cyan
    Write-Host "Range $Range modified successfully!" -ForegroundColor Green

    # 步骤5: 保存策略
    if ($attachedToExisting) {
        Write-Host "`nNOTE: Changes made to open Excel. Please save manually (Ctrl+S)" -ForegroundColor Yellow
        # 不自动保存，让用户决定
    }
    else {
        Write-Host "`nSaving workbook..."
        $workbook.Save()
        Write-Host "Saved successfully" -ForegroundColor Green
    }

    Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
    Write-Host "The changes are now visible in the Excel window!"
}
catch {
    Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    throw
}
finally {
    # 清理：只在创建新实例时关闭
    if (-not $attachedToExisting) {
        if ($workbook) {
            $workbook.Close($true)  # 保存并关闭
        }
        if ($excel) {
            $excel.Quit()
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
        }
    }
    # 如果是附加到已有实例，不做任何清理，让Excel继续运行

    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
