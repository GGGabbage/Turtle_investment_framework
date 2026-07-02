"""烟蒂股筛选器 — 找出净现金>市值、PB极低的港股"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import requests as _req
_o = _req.Session.__init__
def _p(self, *a, **kw):
    _o(self, *a, **kw); self.trust_env = False
_req.Session.__init__ = _p
import os; os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['MKL_NUM_THREADS']='1'
import akshare as ak
import time

# 烟蒂股候选池 — 港股低PB、可能净现金>市值的标的
# 来源：港股通中PB<0.7的国企 + 一些老牌低估值港股
candidates = [
    # 代码, 名称, 预估PB, 预估总负债率%, 行业
    ("1234", "中国利郎",   0.5, 30, "服装"),
    ("0493", "国美零售",   0.3, 70, "零售"),
    ("0881", "中升集团",   0.4, 65, "汽车经销商"),
    ("0960", "龙湖集团",   0.4, 75, "地产"),
    ("2007", "碧桂园",    0.2, 90, "地产"),
    ("0688", "中国海外发展", 0.5, 50, "地产"),
    ("1109", "华润置地",   0.6, 55, "地产"),
    ("0388", "港交所",     5.0, 15, "金融"),
    ("1442", "招商局置地", 0.3, 65, "地产"),
    ("0241", "阿里健康",   2.0, 25, "医疗"),
]

# 补充一些更经典的烟蒂候选
candidates += [
    ("0002", "中电控股",   2.0, 30, "公用"),
    ("0006", "电能实业",   0.8, 25, "公用"),
    ("0016", "新鸿基地产", 0.5, 45, "地产"),
    ("0017", "新世界发展", 0.3, 55, "地产"),
    ("0041", "长城置业",   0.3, 60, "地产"),
    ("0270", "粤海投资",   0.7, 40, "水务"),
    ("0573", "理文造纸",   0.5, 40, "造纸"),
    ("0267", "中信股份",   0.4, 55, "综合"),
    ("0386", "中国石化",   0.7, 50, "石化"),
    ("1038", "长江基建",   0.9, 30, "基建"),
]

print(f"{'代码':>6} {'名称':>8} {'现价':>6} {'PB':>6} {'市值(亿)':>8} {'行业':>6}")
print("-" * 55)

results = []
for code, name, pb_est, debt_est, sector in candidates:
    try:
        df = ak.stock_hk_hist(symbol=code, period='daily', adjust='qfq',
                              start_date='20250101', end_date='20261231')
        if len(df) == 0:
            print(f"{code:>6} {name:>8} — 无数据")
            continue

        cur = float(df['收盘'].iloc[-1])

        # 获取实时行情(含PB/PE/市值)
        try:
            spot = ak.stock_hk_spot_em()
            row = spot[spot['代码'] == code]
            if len(row) > 0:
                pb = float(row.iloc[0].get('市净率', 0) or 0)
                mktcap = float(row.iloc[0].get('总市值', 0) or 0) / 1e8  # 转�
                pe = float(row.iloc[0].get('市盈率-动态', 0) or 0)
            else:
                pb = pb_est
                mktcap = 0
                pe = 0
        except:
            pb = pb_est
            mktcap = 0
            pe = 0

        print(f"{code:>6} {name:>8} {cur:>6.2f} {pb:>6.2f} {mktcap:>8.0f} {sector:>6}")
        results.append({
            'code': code, 'name': name, 'price': cur,
            'pb': pb, 'mktcap': mktcap, 'pe': pe,
            'sector': sector, 'debt_est': debt_est,
        })

        time.sleep(2)
    except Exception as e:
        print(f"{code:>6} {name:>8} — ERROR: {str(e)[:40]}")
        time.sleep(3)

print()
print("=" * 60)
print("PB < 0.7 的烟蒂候选:")
for r in sorted(results, key=lambda x: x['pb']):
    if r['pb'] < 0.7 and r['pb'] > 0:
        print(f"  {r['code']} {r['name']:>8} PB={r['pb']:.2f} 市值={r['mktcap']:.0f}亿 {r['sector']}")
