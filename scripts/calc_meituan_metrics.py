"""美团(03690.HK) 5项价格指标计算"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import requests as _req
_o = _req.Session.__init__
def _p(self, *a, **kw):
    _o(self, *a, **kw); self.trust_env = False
_req.Session.__init__ = _p

import os; os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

import akshare as ak
from datetime import date, timedelta

# ============================================================
# 基础数据
# ============================================================
TOTAL_SHARES = 55.3          # 亿股 (2024年末，回购后)
HKD_RMB = 1.08
Rf = 1.8                     # %
II = 5.30                    # % 门槛

# FY2024 关键数据 (RMB 亿)
REVENUE_2024 = 3376
OP_2024 = 451                # 经营利润
OPM_2024 = 13.4              # %
NP_2024 = 358                # 归母净利润(IFRS)
EPS_2024 = 5.85              # RMB (basic)
OCF_2024 = 571               # 经营现金流
CAPEX_2024 = 43              # 资本开支
FCF_2024 = 528               # 自由现金流
BUYBACK_2024 = 260           # 回购金额

# FY2025
NP_2025 = -234               # 亏损 (价格战+海外扩张)
REVENUE_2025 = 3649

# FY2026E
EPS_2026E = 2.19             # RMB
NP_2026E = EPS_2026E * TOTAL_SHARES  # ~121亿

# 资产负债表
CASH = 1413                  # 亿 (含短期投资)
DEBT = 513                   # 亿
NET_CASH = CASH - DEBT       # 900亿
NET_ASSETS = 1510            # 亿
BVPS_RMB = NET_ASSETS / TOTAL_SHARES  # 27.3 RMB

# ============================================================
# 获取价格数据
# ============================================================
print("Fetching Meituan price data...")
df = ak.stock_hk_daily(symbol='03690', adjust='qfq')
cur_price = float(df['close'].iloc[-1])
cur_date = str(df['date'].iloc[-1])
print(f"Latest: {cur_date} = {cur_price} HKD\n")

market_cap_hkd = cur_price * TOTAL_SHARES  # 亿HKD
market_cap_rmb = market_cap_hkd / HKD_RMB

# 10年价格
cutoff = date.today() - timedelta(days=3650)
mask = [df['date'].iloc[i] >= cutoff for i in range(len(df))]
closes_10y = sorted([float(df['close'].iloc[i]) for i in range(len(df)) if mask[i]])
n10 = len(closes_10y)

def pct(data, p):
    return data[min(int(len(data) * p / 100), len(data) - 1)]

# ============================================================
# 1. 价格分位 (10年)
# ============================================================
rank = sum(1 for x in closes_10y if x <= cur_price)

print("=" * 60)
print("1. 价格分位 (10年历史, 上市以来完整数据)")
print("=" * 60)
for p in [10, 25, 50, 75, 90]:
    print(f"  P{p}: {pct(closes_10y, p):.2f} HKD")
print(f"  最低: {closes_10y[0]:.2f} HKD (上市初期)")
print(f"  最高: {closes_10y[-1]:.2f} HKD (2021年2月)")
print(f"  当前: {cur_price:.2f} HKD → {rank/n10*100:.1f}% 分位")
print(f"  距最低: +{(cur_price/closes_10y[0]-1)*100:.1f}%")
print(f"  距最高: {(cur_price/closes_10y[-1]-1)*100:.1f}%")

# 年末价格
print()
df['year'] = [d.year for d in df['date']]
for y in [2018,2019,2020,2021,2022,2023,2024,2025]:
    sub = df[df['year'] == y]
    if len(sub) > 0:
        p = float(sub.iloc[-1]['close'])
        print(f"  {y} 年末: {p:.2f} HKD")
print()

# ============================================================
# 2. 目标买入价 (GG/II)
# ============================================================
# 美团不分红，用回购替代分红
# GG = Buyback_Yield (回购收益率) + FCF_growth_potential
# 但龟龟框架用 GG = [AA × M × (1-Q) + O] / MC
# 美团: Q=0 (回购不扣税), M = buyback/AA, O = 0 (已包含在M中)

# 用FY2024数据 (最近一个完整盈利年)
AA = FCF_2024  # 可支配现金 ≈ FCF
M = BUYBACK_2024 / AA  # 回购/FCF = 260/528 = 49.2%
Q = 0  # 回购不扣红利税

GG_2024 = (AA * M * (1 - Q)) / market_cap_rmb * 100
# = 260 / 4426 * 100 = 5.87%

print("=" * 60)
print("2. 目标买入价")
print("=" * 60)
print(f"  基准: FY2024 (最近完整盈利年)")
print(f"  FCF(AA) = {AA} 亿 RMB")
print(f"  回购 = {BUYBACK_2024} 亿 RMB (占FCF {M*100:.1f}%)")
print(f"  市值 = {market_cap_hkd:.0f} 亿 HKD ≈ {market_cap_rmb:.0f} 亿 RMB")
print(f"  GG (FY2024基准) = {BUYBACK_2024}/{market_cap_rmb:.0f} = {GG_2024:.2f}%")
print(f"  II = {II}%")
print()

target_2024 = cur_price * (GG_2024 / II)
print(f"  Target (FY2024) = {cur_price:.2f} × ({GG_2024:.2f}/{II}) = {target_2024:.2f} HKD")
if GG_2024 >= II:
    print(f"  → GG > II，当前价已具备安全边际！")
else:
    print(f"  → GG < II，需等回调至 {target_2024:.2f} HKD 以下 (需跌 {(1-GG_2024/II)*100:.1f}%)")

# 但注意: FY2025亏损，回购力度可能下降
# 假设2025年回购降至100亿 (保守)
buyback_2025e = 100
GG_2025e = buyback_2025e / market_cap_rmb * 100
target_2025e = cur_price * (GG_2025e / II) if GG_2025e > 0 else 0

print()
print(f"  --- 保守情景 (FY2025亏损年) ---")
print(f"  假设回购降至 {buyback_2025e} 亿 (vs FY2024 {BUYBACK_2024} 亿)")
print(f"  GG = {GG_2025e:.2f}%")
print(f"  Target = {target_2025e:.2f} HKD (需跌 {(1-GG_2025e/II)*100:.1f}%)")

# FY2026E 恢复盈利
# 假设恢复回购至200亿
buyback_2026e = 200
GG_2026e = buyback_2026e / market_cap_rmb * 100
print()
print(f"  --- FY2026E (恢复盈利) ---")
print(f"  假设回购恢复至 {buyback_2026e} 亿")
print(f"  GG = {GG_2026e:.2f}%")
target_2026e = cur_price * (GG_2026e / II) if GG_2026e > 0 else 0
print(f"  Target = {target_2026e:.2f} HKD")
if GG_2026e >= II:
    print(f"  → GG > II，安全边际充足")
print()

# ============================================================
# 3. 地板价 (5种方法)
# ============================================================
# 方法1: 净现金/股
net_cash_ps_hkd = NET_CASH / TOTAL_SHARES * HKD_RMB

# 方法2: BVPS
bvps_hkd = BVPS_RMB * HKD_RMB

# 方法3: 10年最低价
hist_low = closes_10y[0]

# 方法4: 股息倒推 — 不适用 (美团不分红)

# 方法5: FCF资本化 (用8%保守折现率)
fcf_floor_hkd = FCF_2024 / 0.08 / TOTAL_SHARES * HKD_RMB

print("=" * 60)
print("3. 地板价")
print("=" * 60)
print(f"  方法1 净现金/股:    {net_cash_ps_hkd:.2f} HKD ({NET_CASH}亿/55.3亿股×1.08)")
print(f"  方法2 每股净资产:    {bvps_hkd:.2f} HKD ({NET_ASSETS}亿/55.3亿股×1.08)")
print(f"  方法3 10年最低:      {hist_low:.2f} HKD")
print(f"  方法4 股息倒推:      N/A (美团不分红)")
print(f"  方法5 FCF/8%:        {fcf_floor_hkd:.2f} HKD ({FCF_2024}亿/8%/55.3亿股×1.08)")

floors = {x: v for x, v in [
    ('净现金', net_cash_ps_hkd),
    ('PB', bvps_hkd),
    ('10Y Low', hist_low),
    ('FCF/8%', fcf_floor_hkd),
] if v > 0}

composite = max(floors.values())
print(f"\n  合成地板价: {composite:.2f} HKD (取最大)")
premium = (cur_price / composite - 1) * 100
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
# 用盈利年份: 2019, 2020, 2023, 2024
# EPS数据 (RMB, 报告值或推算)
eps_data = {
    # year: (净利润亿RMB, EPS RMB, 来源)
    2019: (22.4, 22.4/58, '推算(58亿股)'),     # ~0.386
    2020: (44.7, 44.7/58, '推算(58亿股)'),     # ~0.771
    2021: (-156, -156/61, '亏损'),
    2022: (-66.9, -66.9/61, '亏损'),
    2023: (138.6, 2.23, '报告值'),
    2024: (358, 5.85, '报告值'),
}

# 年末价格
year_end = {}
for y in eps_data:
    sub = df[df['year'] == y]
    if len(sub) > 0:
        year_end[y] = float(sub.iloc[-1]['close'])

print("=" * 60)
print("4. PE Band")
print("=" * 60)

pe_list = []
print(f"  {'Year':>6} {'Price':>8} {'NP(亿RMB)':>10} {'EPS(RMB)':>9} {'PE':>7}")
print(f"  {'-'*6} {'-'*8} {'-'*10} {'-'*9} {'-'*7}")
for y in sorted(eps_data):
    if y in year_end:
        np_y, eps_rmb, src = eps_data[y]
        p = year_end[y]
        eps_hkd = eps_rmb * HKD_RMB
        if eps_hkd > 0:
            pe = p / eps_hkd
            pe_list.append(pe)
            print(f"  {y:>6} {p:>8.2f} {np_y:>10.1f} {eps_rmb:>9.3f} {pe:>7.1f}x")
        else:
            print(f"  {y:>6} {p:>8.2f} {np_y:>10.1f} {eps_rmb:>9.3f}   N/A (亏损)")

# 只取合理PE (剔除极端值)
pe_reasonable = [p for p in pe_list if p < 200]  # 剔除泡沫PE
if pe_reasonable:
    pe_reasonable.sort()
    nr = len(pe_reasonable)
    pe_med = pe_reasonable[nr // 2]
    pe_25 = pe_reasonable[max(0, nr * 25 // 100 - 1)]
    pe_75 = pe_reasonable[min(nr - 1, nr * 75 // 100)]
    pe_avg = sum(pe_reasonable) / nr

    # 当前正常化EPS
    eps_now_hkd = EPS_2024 * HKD_RMB  # 6.32 HKD

    print(f"\n  PE统计 (盈利年, 剔除泡沫PE>200x):")
    print(f"    样本: {pe_reasonable}")
    print(f"    均值: {pe_avg:.1f}x")
    print(f"    中位: {pe_med:.1f}x")
    print(f"    P25:  {pe_25:.1f}x")
    print(f"    P75:  {pe_75:.1f}x")

    print(f"\n  FY2024 正常化EPS = {EPS_2024} RMB = {eps_now_hkd:.2f} HKD")
    print(f"\n  PE Band 目标价 (基于FY2024 EPS):")
    print(f"    PE {pe_25:.1f}x → {pe_25 * eps_now_hkd:.2f} HKD")
    print(f"    PE {pe_med:.1f}x → {pe_med * eps_now_hkd:.2f} HKD")
    print(f"    PE {pe_75:.1f}x → {pe_75 * eps_now_hkd:.2f} HKD")
    print(f"    PE {pe_avg:.1f}x → {pe_avg * eps_now_hkd:.2f} HKD")

    cur_pe_2024 = cur_price / eps_now_hkd
    print(f"\n  当前PE (FY2024): {cur_pe_2024:.1f}x")

    # 2026E
    eps_2026e_hkd = EPS_2026E * HKD_RMB
    cur_pe_2026e = cur_price / eps_2026e_hkd
    print(f"\n  PE Band 目标价 (基于FY2026E EPS {EPS_2026E} RMB = {eps_2026e_hkd:.2f} HKD):")
    print(f"    PE {pe_25:.1f}x → {pe_25 * eps_2026e_hkd:.2f} HKD")
    print(f"    PE {pe_med:.1f}x → {pe_med * eps_2026e_hkd:.2f} HKD")
    print(f"    PE {pe_avg:.1f}x → {pe_avg * eps_2026e_hkd:.2f} HKD")
    print(f"  当前PE (FY2026E): {cur_pe_2026e:.1f}x")
print()

# ============================================================
# 5. 反向估值
# ============================================================
print("=" * 60)
print("5. 反向估值 — 市场隐含什么预期？")
print("=" * 60)

# 美团不分红，DDM不适用
# 用 E/P 和 FCF Yield 两种方法

ke = II / 100  # 5.3%

# 方法1: E/P (用FY2024 EPS)
eps_2024_hkd = EPS_2024 * HKD_RMB
ep_yield = eps_2024_hkd / cur_price
g_implied_ep = ke - ep_yield
print(f"  方法1 E/P (FY2024 EPS):")
print(f"    EPS = {EPS_2024} RMB = {eps_2024_hkd:.2f} HKD")
print(f"    E/P = {ep_yield*100:.2f}%")
print(f"    g_implied = {ke*100:.1f}% - {ep_yield*100:.2f}% = {g_implied_ep*100:.2f}%")

# 方法2: FCF Yield
fcf_yield = FCF_2024 / market_cap_rmb
g_implied_fcf = ke - fcf_yield
print(f"\n  方法2 FCF Yield:")
print(f"    FCF = {FCF_2024} 亿 RMB, 市值 = {market_cap_rmb:.0f} 亿 RMB")
print(f"    FCF Yield = {fcf_yield*100:.2f}%")
print(f"    g_implied = {ke*100:.1f}% - {fcf_yield*100:.2f}% = {g_implied_fcf*100:.2f}%")

# 方法3: 用FY2026E (恢复盈利后)
eps_2026e_hkd = EPS_2026E * HKD_RMB
ep_2026e = eps_2026e_hkd / cur_price
g_implied_2026e = ke - ep_2026e
print(f"\n  方法3 E/P (FY2026E):")
print(f"    EPS_2026E = {EPS_2026E} RMB = {eps_2026e_hkd:.2f} HKD")
print(f"    E/P = {ep_2026e*100:.2f}%")
print(f"    g_implied = {ke*100:.1f}% - {ep_2026e*100:.2f}% = {g_implied_2026e*100:.2f}%")

# 综合解读
avg_g = (g_implied_ep + g_implied_fcf + g_implied_2026e) / 3
print(f"\n  综合隐含增长率 ≈ {avg_g*100:.2f}%")
print(f"  FY2024 收入增速: +22.0%")
print(f"  FY2025 收入增速: +8.1%")

# 用盈利增速看
profit_growth_24 = 158.4  # FY2024净利增速
print(f"  FY2024 净利增速: +{profit_growth_24:.0f}%")
print(f"  FY2025: 由盈转亏 (-234亿)")
print(f"  FY2026E: 恢复盈利 (~{NP_2026E:.0f}亿)")

print()
print("=" * 60)
print("汇总")
print("=" * 60)
print(f"  股价: {cur_price:.2f} HKD | 10年分位: {rank/n10*100:.1f}%")
print(f"  市值: {market_cap_hkd:.0f} 亿 HKD ≈ {market_cap_rmb:.0f} 亿 RMB")
print(f"  PE(FY2024): {cur_price/eps_now_hkd:.1f}x | PE(FY2026E): {cur_price/eps_2026e_hkd:.1f}x")
print(f"  FCF Yield: {fcf_yield*100:.1f}% | 回购Yield(FY2024): {BUYBACK_2024/market_cap_rmb*100:.1f}%")
print(f"  P/B: {cur_price/bvps_hkd:.1f}x | 净现金/市值: {NET_CASH/market_cap_rmb*100:.1f}%")
print(f"  GG(FY2024): {GG_2024:.2f}% | II: {II}% | {'达标' if GG_2024 >= II else '未达标'}")
