# 基础Excel创建模板
# 创建一个简单的Excel工作簿并填充数据

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    # 创建工作簿
    $workbook = $excel.Workbooks.Add()
    $sheet = $workbook.Worksheets.Item(1)
    $sheet.Name = "数据表"

    # 写入表头
    $sheet.Cells.Item(1, 1).Value2 = "列1"
    $sheet.Cells.Item(1, 2).Value2 = "列2"
    $sheet.Cells.Item(1, 3).Value2 = "列3"

    # 表头格式化
    $headerRange = $sheet.Range("A1:C1")
    $headerRange.Font.Bold = $true
    $headerRange.Font.Size = 12
    $headerRange.Interior.Color = 15773696  # 浅蓝色

    # 写入示例数据
    $data = @(
        @("数据1-1", "数据1-2", "数据1-3"),
        @("数据2-1", "数据2-2", "数据2-3"),
        @("数据3-1", "数据3-2", "数据3-3")
    )

    for ($i = 0; $i -lt $data.Count; $i++) {
        for ($j = 0; $j -lt $data[$i].Count; $j++) {
            $sheet.Cells.Item($i + 2, $j + 1).Value2 = $data[$i][$j]
        }
    }

    # 自动调整列宽
    $sheet.UsedRange.Columns.AutoFit() | Out-Null

    # 保存文件
    $outputPath = Join-Path $PSScriptRoot "output.xlsx"
    $workbook.SaveAs($outputPath)

    Write-Output "成功创建文件: $outputPath"
}
finally {
    # 清理资源
    if ($workbook) { $workbook.Close($false) }
    if ($excel) {
        $excel.Quit()
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
