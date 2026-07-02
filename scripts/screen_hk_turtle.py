"""港股龟龟框架选股 — 第一步+第二步合并：获取候选股价格数据并计算分位"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import requests as _req
_o = _req.Session.__init__
def _p(self, *a, **kw):
    _o(self, *a, **kw); self.trust_env = False
_req.Session.__init__ = _p
import os; os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['MKL_NUM_THREADS']='1'
import akshare as ak
import time
from datetime import date, timedelta

# 候选清单 (代码, 名称, 行业, 预估PE, 预估股息率%)
candidates = [
    ("0939", "建设银行",   "银行",   5,  8),
    ("1398", "工商银行",   "银行",   5,  5.5),
    ("1288", "农业银行",   "银行",   5,  6.5),
    ("3328", "交通银行",   "银行",   5,  6.5),
    ("0005", "汇丰控股",   "银行",  11,  5.5),
    ("0883", "中国海油",   "石油",   8,  8),
    ("1088", "中国神华",   "煤炭",   9,  9),
    ("0386", "中国石化",   "石化",   7,  9),
    ("0857", "中国石油",   "石油",   8,  7),
    ("0728", "中国电信",   "电信",  11,  6.5),
    ("0941", "中国移动",   "电信",  11,  5.5),
    ("0762", "中国联通",   "电信",  11,  5.5),
    ("0598", "中国外运",   "物流",   8,  5.5),
    ("0270", "粤海投资",   "水务",  11,  6.5),
    ("0006", "电能实业",   "公用",  13,  6.5),
]

HKD_RMB = 1.08
cutoff = date.today() - timedelta(days=3650)

print(f"{'代码':>6} {'名称':>6} {'现价':>6} {'10Y分位':>7} {'P25':>6} {'P50':>6} {'P75':>6} {'距高':>6} {'距低':>6}")
print("-" * 70)

results = []
for code, name, sector, pe_est, div_est in candidates:
    try:
        # 用 stock_hk_hist (eastmoney源) 替代 stock_hk_daily (sina源)
        df = ak.stock_hk_hist(symbol=code, period='daily', adjust='qfq',
                              start_date='20160101', end_date='20261231')
        cur = float(df['收盘'].iloc[-1])

        # 10年价格分位
        mask = [df['日期'].iloc[i] >= cutoff for i in range(len(df))]
        closes = sorted([float(df['收盘'].iloc[i]) for i in range(len(df)) if mask[i]])
        if not closes:
            print(f"{code:>6} {name:>6} — 无10年数据")
            continue

        n = len(closes)
        rank = sum(1 for x in closes if x <= cur)
        pct_rank = rank / n * 100

        p25 = closes[min(int(n * 0.25), n-1)]
        p50 = closes[n // 2]
        p75 = closes[min(int(n * 0.75), n-1)]
        low = closes[0]
        high = closes[-1]

        vs_high = (cur / high - 1) * 100
        vs_low = (cur / low - 1) * 100

        print(f"{code:>6} {name:>6} {cur:>6.2f} {pct_rank:>6.1f}% {p25:>6.2f} {p50:>6.2f} {p75:>6.2f} {vs_high:>5.0f}% {vs_low:>5.0f}%")

        results.append({
            'code': code, 'name': name, 'sector': sector,
            'price': cur, 'pct_rank': pct_rank,
            'p25': p25, 'p50': p50, 'p75': p75,
            'low': low, 'high': high,
            'pe_est': pe_est, 'div_est': div_est,
        })

        time.sleep(2)  # 避免限速
    except Exception as e:
        print(f"{code:>6} {name:>6} — ERROR: {str(e)[:50]}")
        time.sleep(3)

print()
print("=" * 70)
print("价格分位 < 30% 的候选:")
for r in results:
    if r['pct_rank'] < 30:
        print(f"  {r['code']} {r['name']:>6} {r['price']:>6.2f} 分位={r['pct_rank']:.1f}% PE~{r['pe_est']}x 股息~{r['div_est']}%")

print()
print("价格分位 < 50% 的候选:")
for r in sorted(results, key=lambda x: x['pct_rank']):
    if r['pct_rank'] < 50:
        print(f"  {r['code']} {r['name']:>6} {r['price']:>6.2f} 分位={r['pct_rank']:.1f}% PE~{r['pe_est']}x 股息~{r['div_est']}%")
