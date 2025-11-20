# 销售报表模板
# 创建一个包含销售数据和图表的报表

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    # 创建工作簿
    $workbook = $excel.Workbooks.Add()
    $sheet = $workbook.Worksheets.Item(1)
    $sheet.Name = "销售数据"

    # 写入表头
    $headers = @("产品名称", "销售数量", "单价", "总金额")
    for ($i = 0; $i -lt $headers.Count; $i++) {
        $sheet.Cells.Item(1, $i + 1).Value2 = $headers[$i]
    }

    # 表头格式化
    $headerRange = $sheet.Range("A1:D1")
    $headerRange.Font.Bold = $true
    $headerRange.Font.Size = 12
    $headerRange.Interior.Color = 65535  # 黄色
    $headerRange.HorizontalAlignment = -4108  # 居中

    # 写入销售数据
    $products = @(
        @("产品A", 100, 50),
        @("产品B", 150, 75),
        @("产品C", 80, 120),
        @("产品D", 200, 35),
        @("产品E", 120, 90)
    )

    for ($i = 0; $i -lt $products.Count; $i++) {
        $row = $i + 2
        $sheet.Cells.Item($row, 1).Value2 = $products[$i][0]
        $sheet.Cells.Item($row, 2).Value2 = $products[$i][1]
        $sheet.Cells.Item($row, 3).Value2 = $products[$i][2]
        # 总金额公式
        $sheet.Cells.Item($row, 4).Formula = "=B$row*C$row"
    }

    # 设置数字格式
    $sheet.Range("C2:D6").NumberFormat = "¥#,##0.00"

    # 添加总计行
    $totalRow = $products.Count + 2
    $sheet.Cells.Item($totalRow, 1).Value2 = "总计"
    $sheet.Cells.Item($totalRow, 1).Font.Bold = $true
    $sheet.Cells.Item($totalRow, 2).Formula = "=SUM(B2:B6)"
    $sheet.Cells.Item($totalRow, 4).Formula = "=SUM(D2:D6)"
    $sheet.Cells.Item($totalRow, 4).Font.Bold = $true

    # 添加边框
    $dataRange = $sheet.Range("A1:D$totalRow")
    $dataRange.Borders.LineStyle = 1

    # 自动调整列宽
    $sheet.UsedRange.Columns.AutoFit() | Out-Null

    # 保存文件
    $outputPath = Join-Path $PSScriptRoot "销售报表.xlsx"
    $workbook.SaveAs($outputPath)

    Write-Output "成功创建销售报表: $outputPath"
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
