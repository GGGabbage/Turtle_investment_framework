Run a full Turtle Investment Framework (龟龟投资策略) analysis on stock: $ARGUMENTS

## Output Directory Convention

All analysis outputs are saved to `d:/work file/财报分析/{公司全称}/`.
- First resolve the company name from the stock code (e.g., 600887 → 伊利股份, 02319.HK → 蒙牛乳业, 00700.HK → 腾讯控股)
- All files below use `OUTDIR = d:/work file/财报分析/{公司全称}/`

## Input Validation
- Stock code must be a valid A-share (e.g., 600887, 000858.SZ), HK stock (00700.HK), or US stock (AAPL)
- If $ARGUMENTS is empty or invalid, ask the user for a valid stock code before proceeding
- If only digits are given, the code will be normalized by scripts/config.py

## Execution Instructions

Read strategies/turtle/coordinator.md for the full pipeline specification, then execute each phase:

### Prerequisite: Check BA outputs
Check in `d:/work file/财报分析/{公司全称}/`:
- **qualitative_report.md** — required. If missing, inform user to run `/business-analysis {stock_code}` first, then stop.
- **data_pack_market.md** — required. If missing, same as above.
- **data_pack_report.md** — optional. If missing, Agent B uses degraded mode (no PDF footnote data).

### Step A: Market Data Refresh
```bash
python3 scripts/data_collector.py --code $ARGUMENTS --output "d:/work file/财报分析/{公司全称}/data_pack_market.md" --refresh-market
```
- Refreshes §1 (price/market cap), §2 (52-week range), §11 (weekly prices), §14 (risk-free rate)
- If data pack is >7 days old, auto-falls back to full collection

### Phase 3: Analysis and Report
- **Step 3.0**: Read strategies/turtle/phase3_preflight.md for data validation
- **Step 3.1 Agent B**: Read strategies/turtle/phase3_quantitative.md for penetrating return rate calculation
  - Write intermediate results to `d:/work file/财报分析/{公司全称}/phase3_quantitative.md`
- **Step 3.2 Agent C**: Read strategies/turtle/phase3_valuation.md for valuation + report assembly
  - Reads qualitative_report.md (from /business-analysis) for qualitative parameters
  - Reads phase3_quantitative.md (from Agent B) for quantitative parameters
- Output: `d:/work file/财报分析/{公司全称}/{公司全称}_{code}_分析报告.md`

### Step 4: Generate HTML Report

After the final report is generated, also produce an HTML version for easy viewing:

```bash
python3 scripts/report_to_html.py --input "d:/work file/财报分析/{公司全称}/{公司全称}_{code}_分析报告.md" --output "d:/work file/财报分析/{公司全称}/{公司全称}_{code}_分析报告.html" --standalone
```

## Error Recovery
- Missing BA outputs → stop and prompt user to run /business-analysis first
- Step A refresh failure → attempt yfinance fallback, then proceed with existing data
- Missing data_pack_report.md → Agent B uses degraded mode (no footnote data)
- Always produce a final report even if partial data

## Output
All files saved to `d:/work file/财报分析/{公司全称}/`:
- Final report: {公司全称}_{code}_分析报告.md
- HTML report: {公司全称}_{code}_分析报告.html
- Quantitative analysis: phase3_quantitative.md

Usage: /turtle-analysis 600887 or /turtle-analysis 00700.HK
