"""小米集团(01810.HK) 5项价格指标计算"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import requests as _req
_o = _req.Session.__init__
def _p(self, *a, **kw):
    _o(self, *a, **kw); self.trust_env = False
_req.Session.__init__ = _p
import os; os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['MKL_NUM_THREADS']='1'
import akshare as ak
from datetime import date, timedelta

# ============================================================
# 基础数据
# ============================================================
TOTAL_SHARES = 250           # 亿股 (约数，FY2025末)
HKD_RMB = 1.08
Rf = 1.8
II = 5.30

# FY2024
REVENUE_2024 = 3659          # 亿
ADJ_NP_2024 = 272            # 经调整净利润
IFRS_NP_2024 = 236.58        # IFRS归母净利润
EPS_2024 = 0.95              # RMB basic (IFRS)
OCF_2024 = 393               # 经营现金流
CAPEX_2024 = 200             # 估算 (含EV工厂等)
FCF_2024 = OCF_2024 - CAPEX_2024  # ~193亿

# FY2025 (已公布)
REVENUE_2025 = 4573
ADJ_NP_2025 = 391.7
EPS_2025 = 1.62              # RMB basic
OCF_2025 = 450               # 估算
CAPEX_2025 = 280             # 估算 (EV产能扩张)
FCF_2025 = OCF_2025 - CAPEX_2025  # ~170亿

# FY2026E
EPS_2026E = 1.74             # RMB (卖方一致预期)

# 资产负债 (FY2025)
CASH_RESERVES = 2326         # 现金储备(含短期投资)
CASH_EQUIV = 269             # 现金及等价物
DEBT = 700                   # 有息负债估算 (银行借款+可换股债券)
NET_CASH = CASH_RESERVES - DEBT  # ~1626亿
NET_ASSETS_2025 = 2939       # 亿 (归属母公司)
BVPS_RMB = NET_ASSETS_2025 / TOTAL_SHARES  # 11.76

# 回购
BUYBACK_2024_HKD = 105.4    # 亿HKD
BUYBACK_2024_RMB = BUYBACK_2024_HKD / HKD_RMB  # ~97.6亿
BUYBACK_2025_HKD = 63       # 亿HKD
BUYBACK_2025_RMB = BUYBACK_2025_HKD / HKD_RMB  # ~58.3亿

# 历史净利润 (IFRS, 亿RMB)
HIST_NP = {
    2018: -43,
    2019: 55,
    2020: 203,  # 含大额公允价值变动
    2021: 68,
    2022: -52,
    2023: 175,
    2024: 236.58,
    2025: 405,  # EPS 1.62 × 250亿
}

# ============================================================
# 价格数据
# ============================================================
print("Fetching Xiaomi price data...")
df = ak.stock_hk_daily(symbol='01810', adjust='qfq')
cur_price = float(df['close'].iloc[-1])
cur_date = str(df['date'].iloc[-1])
print(f"Latest: {cur_date} = {cur_price} HKD\n")

market_cap_hkd = cur_price * TOTAL_SHARES
market_cap_rmb = market_cap_hkd / HKD_RMB

cutoff = date.today() - timedelta(days=3650)
mask = [df['date'].iloc[i] >= cutoff for i in range(len(df))]
closes = sorted([float(df['close'].iloc[i]) for i in range(len(df)) if mask[i]])
n10 = len(closes)

def pct(data, p):
    return data[min(int(len(data) * p / 100), len(data) - 1)]

# ============================================================
# 1. 价格分位
# ============================================================
rank = sum(1 for x in closes if x <= cur_price)

print("=" * 60)
print("1. 价格分位 (上市以来 ~8年)")
print("=" * 60)
for p in [10, 25, 50, 75, 90]:
    print(f"  P{p}: {pct(closes, p):.2f} HKD")
print(f"  Min: {closes[0]:.2f}  Max: {closes[-1]:.2f}")
print(f"  Current {cur_price} = {rank/n10*100:.1f}% 分位")
print(f"  vs Low: +{(cur_price/closes[0]-1)*100:.1f}%  vs High: {(cur_price/closes[-1]-1)*100:.1f}%")
print()

# ============================================================
# 2. 目标买入价
# ============================================================
# 小米不分红，用回购计算GG
# GG = Buyback / Market_Cap

buyback_yield_2024 = BUYBACK_2024_RMB / market_cap_rmb * 100
buyback_yield_2025 = BUYBACK_2025_RMB / market_cap_rmb * 100

print("=" * 60)
print("2. 目标买入价")
print("=" * 60)
print(f"  市值 = {market_cap_hkd:.0f} 亿 HKD ≈ {market_cap_rmb:.0f} 亿 RMB")
print(f"  回购 FY2024: {BUYBACK_2024_HKD}亿HKD ≈ {BUYBACK_2024_RMB:.1f}亿RMB")
print(f"  回购 FY2025: {BUYBACK_2025_HKD}亿HKD ≈ {BUYBACK_2025_RMB:.1f}亿RMB")
print()

for label, bb_rmb in [("FY2024", BUYBACK_2024_RMB), ("FY2025", BUYBACK_2025_RMB)]:
    gg = bb_rmb / market_cap_rmb * 100
    target = cur_price * (gg / II) if gg > 0 else 0
    print(f"  --- {label}基准 ---")
    print(f"  GG = {gg:.2f}%  (回购收益率)")
    print(f"  II = {II}%")
    if gg >= II:
        print(f"  → GG > II, 当前价已达标!")
        print(f"  Target = {cur_price:.2f} × ({gg:.2f}/{II}) = {target:.2f} HKD")
    else:
        print(f"  → GG < II, 未达标")
        print(f"  Target = {target:.2f} HKD (需跌 {(1-gg/II)*100:.1f}%)")
    print()

# 也可用FCF算"潜在GG"
# 如果小米把全部FCF用于回购: potential GG = FCF / MC
pot_gg_2024 = FCF_2024 / market_cap_rmb * 100
pot_gg_2025 = FCF_2025 / market_cap_rmb * 100
print(f"  --- 潜在GG (全部FCF用于回购) ---")
print(f"  FY2024: FCF {FCF_2024}亿 → 潜在GG = {pot_gg_2024:.2f}%")
print(f"  FY2025: FCF {FCF_2025}亿 → 潜在GG = {pot_gg_2025:.2f}%")
print()

# ============================================================
# 3. 地板价
# ============================================================
net_cash_ps = NET_CASH / TOTAL_SHARES * HKD_RMB
bvps_hkd = BVPS_RMB * HKD_RMB
hist_low = closes[0]
fcf_floor = FCF_2025 / 0.08 / TOTAL_SHARES * HKD_RMB

print("=" * 60)
print("3. 地板价")
print("=" * 60)
print(f"  方法1 净现金/股:   {net_cash_ps:.2f} HKD ({NET_CASH}亿/250亿×1.08)")
print(f"  方法2 每股净资产:   {bvps_hkd:.2f} HKD ({NET_ASSETS_2025}亿/250亿×1.08)")
print(f"  方法3 10年最低:     {hist_low:.2f} HKD")
print(f"  方法4 股息倒推:     N/A (小米不分红)")
print(f"  方法5 FCF/8%:       {fcf_floor:.2f} HKD ({FCF_2025}亿/8%/250亿×1.08)")

floors = [('净现金', net_cash_ps), ('PB', bvps_hkd), ('10Y低', hist_low), ('FCF/8%', fcf_floor)]
composite = max(v for _, v in floors)
print(f"\n  合成地板价: {composite:.2f} HKD")
premium = (cur_price / composite - 1) * 100
print(f"  当前溢价: +{premium:.1f}%")
if premium <= 0: print("  → 「买入就是胜利」")
elif premium <= 30: print("  → 安全边际充足")
elif premium <= 80: print("  → 合理溢价区间")
else: print("  → 高溢价，需增长支撑")
print()

# ============================================================
# 4. PE Band
# ============================================================
year_end = {}
df['year'] = [d.year for d in df['date']]
for y in HIST_NP:
    sub = df[df['year'] == y]
    if len(sub) > 0:
        year_end[y] = float(sub.iloc[-1]['close'])

print("=" * 60)
print("4. PE Band")
print("=" * 60)
pe_list = []
print(f"  {'Year':>6} {'Price':>8} {'NP(亿)':>8} {'EPS(RMB)':>9} {'PE':>7}")
print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*9} {'-'*7}")
for y in sorted(HIST_NP):
    if y in year_end:
        np_y = HIST_NP[y]
        eps_rmb = np_y / TOTAL_SHARES
        p = year_end[y]
        eps_hkd = eps_rmb * HKD_RMB
        if eps_hkd > 0:
            pe = p / eps_hkd
            pe_list.append((y, pe))
            print(f"  {y:>6} {p:>8.2f} {np_y:>8.1f} {eps_rmb:>9.3f} {pe:>7.1f}x")
        else:
            print(f"  {y:>6} {p:>8.2f} {np_y:>8.1f} {eps_rmb:>9.3f}   N/A (亏损)")

# 只取合理PE (< 100x)
pe_vals = [pe for _, pe in pe_list if pe < 100]
if pe_vals:
    pe_vals.sort()
    nv = len(pe_vals)
    pe_med = pe_vals[nv // 2]
    pe_25 = pe_vals[max(0, nv * 25 // 100 - 1)]
    pe_75 = pe_vals[min(nv - 1, nv * 75 // 100)]
    pe_avg = sum(pe_vals) / nv

    print(f"\n  PE统计 (盈利年, PE<100x):")
    print(f"    样本: {[f'{pe:.1f}' for _, pe in pe_list if pe < 100]}")
    print(f"    均值: {pe_avg:.1f}x  中位: {pe_med:.1f}x")
    print(f"    P25: {pe_25:.1f}x  P75: {pe_75:.1f}x")

    # 用FY2025 EPS
    eps_2025_hkd = EPS_2025 * HKD_RMB
    eps_2026e_hkd = EPS_2026E * HKD_RMB

    print(f"\n  PE Band 目标价 (FY2025 EPS={EPS_2025} RMB = {eps_2025_hkd:.2f} HKD):")
    print(f"    PE {pe_25:.1f}x → {pe_25 * eps_2025_hkd:.2f} HKD")
    print(f"    PE {pe_med:.1f}x → {pe_med * eps_2025_hkd:.2f} HKD")
    print(f"    PE {pe_75:.1f}x → {pe_75 * eps_2025_hkd:.2f} HKD")
    print(f"    PE {pe_avg:.1f}x → {pe_avg * eps_2025_hkd:.2f} HKD")

    print(f"\n  PE Band 目标价 (FY2026E EPS={EPS_2026E} RMB = {eps_2026e_hkd:.2f} HKD):")
    print(f"    PE {pe_25:.1f}x → {pe_25 * eps_2026e_hkd:.2f} HKD")
    print(f"    PE {pe_med:.1f}x → {pe_med * eps_2026e_hkd:.2f} HKD")
    print(f"    PE {pe_avg:.1f}x → {pe_avg * eps_2026e_hkd:.2f} HKD")

    cur_pe_2025 = cur_price / eps_2025_hkd
    cur_pe_2026e = cur_price / eps_2026e_hkd
    print(f"\n  当前PE (FY2025): {cur_pe_2025:.1f}x")
    print(f"  当前PE (FY2026E): {cur_pe_2026e:.1f}x")
print()

# ============================================================
# 5. 反向估值
# ============================================================
ke = II / 100

eps_2025_hkd = EPS_2025 * HKD_RMB
ep_yield_2025 = eps_2025_hkd / cur_price
g_ep = ke - ep_yield_2025

fcf_yield_2025 = FCF_2025 / market_cap_rmb
g_fcf = ke - fcf_yield_2025

eps_2026e_hkd = EPS_2026E * HKD_RMB
ep_yield_2026e = eps_2026e_hkd / cur_price
g_ep_2026e = ke - ep_yield_2026e

print("=" * 60)
print("5. 反向估值 — 市场隐含什么预期？")
print("=" * 60)
print(f"  方法1 E/P (FY2025 EPS):")
print(f"    E/P = {ep_yield_2025*100:.2f}% → g_implied = {ke*100:.1f}% - {ep_yield_2025*100:.2f}% = {g_ep*100:.2f}%")
print(f"\n  方法2 FCF Yield (FY2025E):")
print(f"    FCF = {FCF_2025}亿, Yield = {fcf_yield_2025*100:.2f}% → g_implied = {g_fcf*100:.2f}%")
print(f"\n  方法3 E/P (FY2026E):")
print(f"    E/P = {ep_yield_2026e*100:.2f}% → g_implied = {ke*100:.1f}% - {ep_yield_2026e*100:.2f}% = {g_ep_2026e*100:.2f}%")

avg_g = (g_ep + g_fcf + g_ep_2026e) / 3
print(f"\n  综合隐含增长率 ≈ {avg_g*100:.2f}%")
print(f"  实际增速: FY2024 +35%, FY2025 +25%, FY2025净利+43.8%")

growth_discount = 25.0 - avg_g * 100  # FY2025收入增速 - 隐含增长
print(f"  增长折扣(FY2025收入增速 vs 隐含): {growth_discount:.1f}ppt")
if growth_discount > 8:
    print("  → 市场几乎未充分定价增长 (价值型定价)")
elif growth_discount > 3:
    print("  → 市场部分认可增长")
elif growth_discount > 0:
    print("  → 市场基本定价了增长")
else:
    print("  → 市场给予了增长溢价")

print()
print("=" * 60)
print("汇总")
print("=" * 60)
print(f"  股价: {cur_price:.2f} HKD | 分位: {rank/n10*100:.1f}%")
print(f"  市值: {market_cap_hkd:.0f}亿HKD ≈ {market_cap_rmb:.0f}亿RMB")
print(f"  PE(FY2025): {cur_price/eps_2025_hkd:.1f}x | PE(FY2026E): {cur_price/eps_2026e_hkd:.1f}x")
print(f"  FCF Yield: {fcf_yield_2025*100:.1f}% | 回购Yield: {BUYBACK_2025_RMB/market_cap_rmb*100:.1f}%")
print(f"  P/B: {cur_price/bvps_hkd:.1f}x | 净现金/市值: {NET_CASH/market_cap_rmb*100:.1f}%")
