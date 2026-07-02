"""计算蒙牛(02319.HK)的5个价格指标：价格分位、目标买入价、地板价、PE Band、反向估值"""
import sys; sys.stdout.reconfigure(encoding='utf-8')

# 1) Bypass proxy
import requests as _req
_o = _req.Session.__init__
def _p(self, *a, **kw):
    _o(self, *a, **kw); self.trust_env = False
_req.Session.__init__ = _p

# 2) Suppress numpy memory hog
import os; os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

import akshare as ak
from datetime import date, timedelta

# ============================================================
# 基础数据
# ============================================================
# 从 phase3_quantitative.md 提取的关键数据
OWNER_EARNINGS = 5378        # 百万RMB (FY2024正常化)
GG = 4.01                    # % 精算穿透回报率
II = 5.30                    # % 门槛
Rf = 1.8                     # % 无风险利率
TOTAL_SHARES = 3879          # 百万股
HKD_RMB = 1.08               # 汇率
PAYOUT_RATIO = 0.344         # M 分配率
TAX_RATE = 0.20              # Q 港股通红利税
BUYBACK = 818                # 百万RMB 年均回购

# 正常化EPS (RMB)
NORMALIZED_EPS_RMB = 5618 / 3879  # ~1.449 RMB

# 获取历史价格
print("Fetching price data...")
df = ak.stock_hk_daily(symbol='02319', adjust='qfq')
cur_price = float(df['close'].iloc[-1])
cur_date = str(df['date'].iloc[-1])
print(f"Latest: {cur_date} = {cur_price} HKD\n")

# ============================================================
# 1. 价格分位 (10年)
# ============================================================
cutoff = date.today() - timedelta(days=3650)
mask = [df['date'].iloc[i] >= cutoff for i in range(len(df))]
closes_10y = sorted([float(df['close'].iloc[i]) for i in range(len(df)) if mask[i]])
n = len(closes_10y)

def pct(data, p):
    return data[min(int(len(data) * p / 100), len(data) - 1)]

rank = sum(1 for x in closes_10y if x <= cur_price)

print("=" * 60)
print("1. 价格分位 (10年历史)")
print("=" * 60)
for p in [10, 25, 50, 75, 90]:
    print(f"  P{p}: {pct(closes_10y, p):.3f} HKD")
print(f"  最低: {closes_10y[0]:.3f} HKD")
print(f"  最高: {closes_10y[-1]:.3f} HKD")
print(f"  当前: {cur_price:.3f} HKD → {rank/n*100:.1f}% 分位")
print(f"  距最低: +{(cur_price/closes_10y[0]-1)*100:.1f}%")
print(f"  距最高: {(cur_price/closes_10y[-1]-1)*100:.1f}%")
print()

# ============================================================
# 2. 目标买入价
# ============================================================
# Target = Market_Cap × (GG/II) / Total_Shares
# 但注意: GG < II 时, Target < Current Price
market_cap_hkd = cur_price * TOTAL_SHARES  # 百万HKD
target_price_hkd = market_cap_hkd * (GG / II) / TOTAL_SHARES

print("=" * 60)
print("2. 目标买入价")
print("=" * 60)
print(f"  公式: Target = Current × (GG / II)")
print(f"  GG = {GG}%, II = {II}%")
print(f"  Target = {cur_price:.3f} × ({GG}/{II})")
print(f"  Target = {target_price_hkd:.3f} HKD")
if target_price_hkd < cur_price:
    print(f"  → 当前价偏高，需等回调至 {target_price_hkd:.2f} HKD 以下")
    print(f"  → 需下跌 {(1 - GG/II)*100:.1f}%")
else:
    print(f"  → 当前价已低于目标买入价，具备安全边际")
print()

# ============================================================
# 3. 地板价 (5种方法合成)
# ============================================================
# 方法1: 净流动资产/股 (RMB → HKD)
# cash=17339, trading_securities≈0, debt=29637 (流动17997+非流动11706)
# Net liquid = (cash - debt) / shares
net_liquid_rmb = (17339 - 29637) / TOTAL_SHARES  # 负数
net_liquid_hkd = net_liquid_rmb * HKD_RMB

# 方法2: 每股净资产 (BVPS)
# 净资产=48025百万RMB
bvps_rmb = 48025 / TOTAL_SHARES
bvps_hkd = bvps_rmb * HKD_RMB

# 方法3: 10年历史最低价
hist_low = closes_10y[0]

# 方法4: 股息倒推价格 = 3年平均DPS / max(Rf, 3%)
# 2023 DPS ≈ 1588/3879 = 0.409 RMB; 2024 DPS ≈ 0.56 HKD ≈ 0.519 RMB
# 3年平均 ≈ 0.45 RMB → 0.486 HKD
avg_dps_hkd = 0.486
div_implied = avg_dps_hkd / max(Rf/100, 0.03)

# 方法5: 悲观FCF资本化 = min(5yr FCF) / Rf / shares
# FCF近年: 4849, 5332, 6300 百万RMB, min≈4849
min_fcf = 4849
fcf_floor_hkd = (min_fcf / (Rf/100) / TOTAL_SHARES) * HKD_RMB

print("=" * 60)
print("3. 地板价 (5种方法)")
print("=" * 60)
print(f"  方法1 净流动资产/股: {net_liquid_hkd:.3f} HKD (负债>现金，无效)")
print(f"  方法2 每股净资产:    {bvps_hkd:.3f} HKD")
print(f"  方法3 10年历史最低:   {hist_low:.3f} HKD")
print(f"  方法4 股息倒推:       {div_implied:.3f} HKD (DPS {avg_dps_hkd}/max(Rf,3%))")
print(f"  方法5 FCF资本化:      {fcf_floor_hkd:.3f} HKD (min_FCF {min_fcf}M / {Rf}% / shares × {HKD_RMB})")

# 合成地板价: 取有效方法的最大值(保守取最高地板)
floors = [bvps_hkd, hist_low, div_implied, fcf_floor_hkd]
composite_floor = max(floors)
print(f"\n  合成地板价(取最大): {composite_floor:.3f} HKD")
premium = (cur_price / composite_floor - 1) * 100
print(f"  当前溢价: +{premium:.1f}%")
if premium <= 0:
    print(f"  → 「买入就是胜利」")
elif premium <= 30:
    print(f"  → 安全边际充足")
elif premium <= 80:
    print(f"  → 合理溢价区间")
else:
    print(f"  → 高溢价，需增长支撑")
print()

# ============================================================
# 4. PE Band
# ============================================================
# 年度EPS历史 (RMB，正常化) - 使用websearch/年报数据
# 用年末收盘价和正常化净利润推算历史PE
eps_history = {
    # year: (正常化净利润百万RMB, 来源)
    2019: 4100,   # 约41亿
    2020: 3500,   # 约35亿(疫情)
    2021: 5000,   # 约50亿
    2022: 5200,   # 约52亿
    2023: 4809,   # 实际归母净利润
    2024: 5618,   # 正常化(剔除减值)
}

# 年末收盘价 (HKD，前复权)
year_end_prices = {}
df['year'] = [d.year for d in df['date']]
for y in eps_history:
    sub = df[df['year'] == y]
    if len(sub) > 0:
        year_end_prices[y] = float(sub.iloc[-1]['close'])

print("=" * 60)
print("4. PE Band")
print("=" * 60)
pe_list = []
print(f"  {'Year':>6} {'Price(HKD)':>10} {'EPS(RMB)':>10} {'PE':>8}")
print(f"  {'-'*6} {'-'*10} {'-'*10} {'-'*8}")
for y in sorted(eps_history):
    if y in year_end_prices:
        p = year_end_prices[y]
        eps_rmb = eps_history[y] / TOTAL_SHARES
        eps_hkd = eps_rmb * HKD_RMB
        pe = p / eps_hkd
        pe_list.append(pe)
        print(f"  {y:>6} {p:>10.2f} {eps_rmb:>10.3f} {pe:>8.1f}x")

if pe_list:
    pe_list.sort()
    n_pe = len(pe_list)
    pe_median = pe_list[n_pe // 2]
    pe_25 = pe_list[max(0, n_pe * 25 // 100 - 1)]
    pe_75 = pe_list[min(n_pe - 1, n_pe * 75 // 100)]
    pe_mean = sum(pe_list) / len(pe_list)

    eps_now_hkd = NORMALIZED_EPS_RMB * HKD_RMB

    print(f"\n  PE统计 (FY2019-FY2024):")
    print(f"    均值:   {pe_mean:.1f}x")
    print(f"    中位数: {pe_median:.1f}x")
    print(f"    P25:    {pe_25:.1f}x")
    print(f"    P75:    {pe_75:.1f}x")

    print(f"\n  当前正常化EPS: {NORMALIZED_EPS_RMB:.3f} RMB = {eps_now_hkd:.3f} HKD")
    print(f"\n  PE Band 目标价:")
    print(f"    PE P25  → {pe_25 * eps_now_hkd:.2f} HKD")
    print(f"    PE 中位 → {pe_median * eps_now_hkd:.2f} HKD")
    print(f"    PE P75  → {pe_75 * eps_now_hkd:.2f} HKD")
    print(f"    PE 均值 → {pe_mean * eps_now_hkd:.2f} HKD")

    cur_pe = cur_price / eps_now_hkd
    print(f"\n  当前PE: {cur_pe:.1f}x")
    print(f"  当前PE分位: {sum(1 for x in pe_list if x <= cur_pe)}/{len(pe_list)}")

    # 美银2026预测 PE
    eps_2026e_rmb = 4861 / TOTAL_SHARES  # 美银预测纯利48.61亿
    eps_2026e_hkd = eps_2026e_rmb * HKD_RMB
    pe_2026e = cur_price / eps_2026e_hkd
    print(f"\n  基于2026E(美银48.61亿): EPS={eps_2026e_hkd:.3f} HKD, PE={pe_2026e:.1f}x")
print()

# ============================================================
# 5. 反向估值 (市场隐含增长率)
# ============================================================
print("=" * 60)
print("5. 反向估值 — 市场隐含什么预期？")
print("=" * 60)

# 方法1: E/P → g_implied = Ke - E/P
# Ke = WACC, 取 II = 5.3% 作为最低要求回报率
# 实际用 DDM: P = D1/(Ke-g) → g = Ke - D1/P
ep = NORMALIZED_EPS_RMB * HKD_RMB / cur_price  # E/P yield
dps_hkd_now = avg_dps_hkd  # 当前DPS

# DDM法: g = Ke - DPS*(1+g)/P → 迭代
# 简化: g ≈ Ke - DPS/P (g较小时)
ke = II / 100  # 5.3%
g_implied_ddm = ke - dps_hkd_now / cur_price
print(f"  方法1 DDM隐含增长:")
print(f"    Ke = {ke*100:.1f}%, DPS = {dps_hkd_now:.3f} HKD, P = {cur_price:.2f} HKD")
print(f"    g_implied = {ke*100:.1f}% - {dps_hkd_now/cur_price*100:.2f}% = {g_implied_ddm*100:.2f}%")

# 方法2: FCF Yield → g = WACC - FCF_yield
fcf_rmb = 5332  # 2024年FCF百万RMB
fcf_hkd = fcf_rmb / TOTAL_SHARES * HKD_RMB
market_cap_total_hkd = cur_price * TOTAL_SHARES  # 百万HKD
fcf_yield = fcf_rmb / (market_cap_total_hkd / HKD_RMB)  # FCF/市值(RMB)
g_implied_fcf = ke - fcf_yield
print(f"\n  方法2 FCF Yield隐含增长:")
print(f"    FCF = {fcf_rmb}M RMB, 市值 = {market_cap_total_hkd:.0f}M HKD ≈ {market_cap_total_hkd/HKD_RMB:.0f}M RMB")
print(f"    FCF Yield = {fcf_yield*100:.2f}%")
print(f"    g_implied = {ke*100:.1f}% - {fcf_yield*100:.2f}% = {g_implied_fcf*100:.2f}%")

# 方法3: E/P法 - 直接从PE看
g_implied_ep = ke - ep
print(f"\n  方法3 E/P隐含增长:")
print(f"    EPS Yield (E/P) = {ep*100:.2f}%")
print(f"    g_implied = {ke*100:.1f}% - {ep*100:.2f}% = {g_implied_ep*100:.2f}%")

# 综合解读
avg_g = (g_implied_ddm + g_implied_fcf + g_implied_ep) / 3
actual_growth = -6.9  # H1 2025收入增速
print(f"\n  综合隐含增长率 ≈ {avg_g*100:.2f}%")
print(f"  实际收入增速(H1 2025): {actual_growth}%")
growth_discount = actual_growth - avg_g * 100
print(f"  增长折扣: {growth_discount:.1f}ppt")
if growth_discount > 8:
    print(f"  → 市场几乎未给予增长溢价（典型价值股困境定价）")
elif growth_discount > 3:
    print(f"  → 市场部分认可增长，但有显著折扣")
elif growth_discount > 0:
    print(f"  → 市场基本定价了增长")
else:
    print(f"  → 市场给予了增长溢价（成长股特征）")

# 2026E 对比
growth_2026e = 4861 / 5618 * 100 - 100  # 2026E vs 2024正常化
print(f"\n  注: 2026E利润增长(vs 2024正常化) ≈ {growth_2026e:.1f}%")
print(f"      若2026E实现，隐含增长 vs 实际增长 = {avg_g*100:.2f}% vs {growth_2026e:.1f}%")
