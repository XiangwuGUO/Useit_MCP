# Excel自动化脚本
# 需求: 
    创建销售报表：
    - 包含产品名称、销售数量、单价、总金额
    - 表头黄色背景粗体
    - 使用公式计算总金额
    - 底部添加总计行
    - 货币格式显示
    
# 生成时间: 2025-11-17 17:51:43

# 创建Excel应用
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    # 创建新工作簿
    $workbook = $excel.Workbooks.Add()
    $sheet = $workbook.Worksheets.Item(1)
    $sheet.Name = '数据'

    # 写入示例数据
    $sampleData = @(
        @('数据1-1', '数据1-2', '数据1-3'),
        @('数据2-1', '数据2-2', '数据2-3'),
        @('数据3-1', '数据3-2', '数据3-3'),
    )

    for ($i = 0; $i -lt $sampleData.Count; $i++) {
        for ($j = 0; $j -lt $sampleData[$i].Count; $j++) {
            $sheet.Cells.Item(1 + $i, $j + 1).Value2 = $sampleData[$i][$j]
        }
    }

    # 添加公式

    # 自动调整列宽
    $sheet.UsedRange.Columns.AutoFit() | Out-Null

    # 保存文件
    $outputPath = 'excel_workspace\\销售报表.xlsx'
    $workbook.SaveAs($outputPath)
    Write-Output "成功创建Excel文件: $outputPath"
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