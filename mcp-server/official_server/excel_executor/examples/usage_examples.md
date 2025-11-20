# Excel COM 代码生成器 - 使用示例

## 基础示例

### 示例1：创建简单表格

**需求描述：**
```
创建一个学生成绩表，包含姓名、语文、数学、英语四列
```

**AI会生成的代码片段：**
```powershell
# 写入表头
$sheet.Cells.Item(1, 1).Value2 = "姓名"
$sheet.Cells.Item(1, 2).Value2 = "语文"
$sheet.Cells.Item(1, 3).Value2 = "数学"
$sheet.Cells.Item(1, 4).Value2 = "英语"

# 表头格式化
$headerRange = $sheet.Range("A1:D1")
$headerRange.Font.Bold = $true
```

**结果：**
- 生成 `学生成绩表.xlsx`
- 包含格式化的表头
- 自动调整列宽

---

### 示例2：带计算的表格

**需求描述：**
```
创建员工工资表，包含姓名、基本工资、奖金、总工资，
用公式自动计算总工资，并在底部显示工资总计
```

**生成的关键代码：**
```powershell
# 写入公式计算总工资
$sheet.Cells.Item($row, 4).Formula = "=B$row+C$row"

# 底部总计
$totalRow = 10
$sheet.Cells.Item($totalRow, 1).Value2 = "总计"
$sheet.Cells.Item($totalRow, 4).Formula = "=SUM(D2:D9)"
```

**特点：**
- 自动使用Excel公式
- 动态引用单元格
- 智能总计行

---

### 示例3：格式化报表

**需求描述：**
```
制作月度销售报表，表头黄色背景粗体，
金额列显示货币格式，添加边框
```

**生成的格式化代码：**
```powershell
# 表头格式
$headerRange.Font.Bold = $true
$headerRange.Interior.Color = 65535  # 黄色
$headerRange.HorizontalAlignment = -4108  # 居中

# 货币格式
$sheet.Range("D2:D10").NumberFormat = "¥#,##0.00"

# 添加边框
$dataRange.Borders.LineStyle = 1
```

**效果：**
- 专业的报表外观
- 正确的数字格式
- 清晰的表格边框

---

## 高级示例

### 示例4：数据统计分析

**需求描述：**
```
创建学生成绩统计表：
1. 包含5个学生的语文、数学、英语成绩
2. 计算每个学生的总分和平均分
3. 找出每科的最高分和最低分
4. 计算班级总平均分
```

**生成的代码结构：**
```powershell
# 学生成绩数据
$students = @(
    @("张三", 85, 90, 88),
    @("李四", 92, 87, 95),
    ...
)

# 总分和平均分公式
$sheet.Cells.Item($row, 5).Formula = "=SUM(B$row:D$row)"
$sheet.Cells.Item($row, 6).Formula = "=AVERAGE(B$row:D$row)"

# 统计行
$sheet.Cells.Item($statRow, 2).Formula = "=MAX(B2:B6)"  # 最高分
$sheet.Cells.Item($statRow+1, 2).Formula = "=MIN(B2:B6)"  # 最低分
```

---

### 示例5：多工作表报表

**需求描述：**
```
创建年度报表，包含：
1. "原始数据"工作表 - 存放月度数据
2. "统计分析"工作表 - 显示汇总结果
3. 使用跨表引用公式
```

**生成的代码：**
```powershell
# 创建多个工作表
$dataSheet = $workbook.Worksheets.Item(1)
$dataSheet.Name = "原始数据"

$summarySheet = $workbook.Worksheets.Add()
$summarySheet.Name = "统计分析"

# 跨表引用公式
$summarySheet.Cells.Item(2, 2).Formula = "=原始数据!B2:B13"
```

---

## 实际业务场景

### 场景1：月度考勤表

**需求：**
```
生成9月份考勤表，包含员工姓名、部门、出勤天数、
迟到次数、请假天数，计算实际工作天数
```

**特点：**
- 自动生成日期列
- 条件格式标记异常
- 统计汇总

---

### 场景2：库存盘点表

**需求：**
```
创建库存盘点表：产品编号、名称、期初库存、
入库数量、出库数量、期末库存（自动计算），
标记库存不足的产品（红色）
```

**特点：**
- 库存计算公式
- 条件格式化
- 预警提示

---

### 场景3：财务收支表

**需求：**
```
制作收支明细表，包含日期、项目、收入、支出、余额，
按日期排序，月底自动汇总，生成收支对比图表
```

**特点：**
- 自动排序
- 累计余额计算
- 图表可视化（计划中）

---

## 与Claude Code配合使用

### 在对话中使用

```
你: 帮我创建一个项目进度跟踪表

Claude: 我将使用Excel代码生成器来创建项目进度表。

[调用 generate_and_execute]
- 需求：项目进度跟踪表
- 包含：项目名称、负责人、开始日期、结束日期、完成度
- 格式：表头蓝色，进度条可视化

✓ 代码已生成
✓ 正在执行...
✓ 完成！文件位于：D:/excel_workspace/项目进度表.xlsx

你可以打开查看，如需修改请告诉我。
```

---

## 代码复用

### 保存常用代码

使用 `save_code=True` 参数：

```python
generate_and_execute(
    requirement="创建销售报表",
    save_code=True  # 保存代码供以后使用
)
```

生成的代码会保存在工作区，文件名格式：
```
excel_code_20240115_143022.ps1
```

### 查看已保存的代码

```python
list_generated_files(pattern="*.ps1")
```

---

## 技巧和最佳实践

### 1. 清晰描述需求

❌ 不好：
```
"做个表格"
```

✅ 好：
```
"创建员工信息表，包含姓名、部门、工资、入职日期四列，
表头加粗，工资列显示为货币格式"
```

### 2. 分步描述复杂需求

```
创建销售分析报表：
1. 表头：产品、销量、单价、金额
2. 数据：添加10个产品的示例数据
3. 格式：表头黄色背景，金额列货币格式
4. 公式：金额 = 销量 × 单价
5. 统计：底部显示总销量和总金额
```

### 3. 指定文件名

```python
generate_excel_code(
    requirement="...",
    file_name="2024年度报表.xlsx"  # 明确文件名
)
```

---

## 故障排除

### 代码执行失败？

1. 检查PowerShell执行策略
2. 确保Excel已安装
3. 查看错误信息调整需求
4. 尝试简化需求重新生成

### 格式不符合预期？

在需求中明确说明：
```
"表头使用Arial字体，14号，粗体，浅蓝色背景"
```

### 公式不正确？

重新描述计算逻辑：
```
"总价 = 数量 × 单价，使用Excel公式自动计算"
```

---

## 更多示例

查看 `templates/` 目录获取更多预定义模板。

有问题或建议？欢迎提Issue！
