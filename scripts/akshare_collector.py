"""AKShare 数据采集器 — 生成与龟龟框架兼容的 data_pack_market.md

用法:
    python scripts/akshare_collector.py --code 600887
    python scripts/akshare_collector.py --code 00700.HK
    python scripts/akshare_collector.py --code 600887 --output output/my_data_pack.md
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

# Bypass system proxy for Chinese financial API endpoints (eastmoney, sina, etc.)
# Fixes ProxyError when Clash/V2Ray system proxy intercepts domestic API calls
import requests as _req
_orig_init = _req.Session.__init__
def _patched_init(self, *a, **kw):
    _orig_init(self, *a, **kw)
    self.trust_env = False
_req.Session.__init__ = _patched_init

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from format_utils import format_number, format_table, format_header

import akshare as ak


# ─── 工具函数 ───

def fmt_num(v):
    try:
        return format_number(float(v))
    except (ValueError, TypeError):
        return str(v)


def fmt_pct(v):
    try:
        return f"{float(v) * 100:.2f}%"
    except (ValueError, TypeError):
        return str(v)


def _detect_market(code: str) -> str:
    code = code.upper()
    if code.endswith(".HK"):
        return "HK"
    if code.endswith((".SS", ".SZ", ".SH")):
        return "A"
    if code.endswith((".US",)):
        return "US"
    if code.isdigit():
        if code.startswith(("6", "5", "0", "3")):
            return "A"
        if len(code) <= 5:
            return "HK"
    # 纯字母代码 → 美股
    if code.isalpha() and len(code) <= 5:
        return "US"
    return "A"


def _normalize_code(code: str) -> tuple:
    market = _detect_market(code)
    clean = code.replace(".SH", "").replace(".SZ", "").replace(".SS", "").replace(".HK", "").replace(".US", "")
    if market == "A":
        ak_code = clean
        ts_code = code if "." in code else f"{clean}.{'SH' if clean.startswith(('6', '5', '9')) else 'SZ'}"
        sina_prefix = f"{'sh' if clean.startswith(('6','5','9')) else 'sz'}{clean}"
        return ak_code, ts_code, sina_prefix, market
    elif market == "HK":
        return clean.zfill(5), f"{clean.zfill(4)}.HK", clean.zfill(5), market
    else:
        return clean, f"{clean}.US", clean, market


def _safe_call(func, *args, retries=3, delay=3, **kwargs):
    for i in range(retries):
        try:
            result = func(*args, **kwargs)
            if result is None:
                raise ValueError("返回 None")
            return result
        except Exception as e:
            if i < retries - 1:
                print(f"    [retry {i + 1}/{retries}] {func.__name__}: {type(e).__name__}: {e}")
                time.sleep(delay)
            else:
                print(f"    [FAIL] {func.__name__}: {e}")
                return pd.DataFrame()


def _fmt_million(val):
    """将原始值（元）转为百万元"""
    try:
        return float(val) / 1e6
    except (ValueError, TypeError):
        return val


# ─── 采集各数据段 ───

def get_basic_info(ak_code, ts_code, sina_prefix, market) -> str:
    """§1 基本信息"""
    lines = ["## 1. 基本信息\n"]
    try:
        if market == "A":
            df = _safe_call(ak.stock_individual_info_em, symbol=ak_code)
            if df is not None and len(df) > 0:
                info = dict(zip(df["item"], df["value"]))
                lines.append(f"- 股票代码: {ts_code}")
                lines.append(f"- 股票简称: {info.get('股票简称', 'N/A')}")
                lines.append(f"- 行业: {info.get('行业', 'N/A')}")
                total_shares = info.get('总股本', 'N/A')
                total_mv = info.get('总市值', 'N/A')
                if total_shares != 'N/A':
                    lines.append(f"- 总股本: {float(total_shares) / 1e8:.2f} 亿股")
                if total_mv != 'N/A':
                    lines.append(f"- 总市值: {float(total_mv) / 1e8:.2f} 亿元")
                lines.append(f"- 上市时间: {info.get('上市时间', 'N/A')}")
        elif market == "HK":
            lines.append(f"- 股票代码: {ts_code}")
            # 使用 yfinance 获取港股基本信息
            try:
                import yfinance as yf
                yf_code = f"{ak_code.lstrip('0').zfill(4)}.HK"
                ticker = yf.Ticker(yf_code)
                info = ticker.info

                # 获取基本信息
                long_name = info.get("longName") or info.get("shortName") or "N/A"
                lines.append(f"- 股票简称: {long_name}")

                # 行业信息
                industry = info.get("industry") or info.get("sector") or "N/A"
                if industry != "N/A":
                    lines.append(f"- 行业: {industry}")

                # 市值 (yfinance单位是美元，需转换)
                market_cap = info.get("marketCap")
                if market_cap:
                    # 港股市值：美元→港币（约7.8倍），直接转换为亿
                    mv_hkd_yi = market_cap * 7.8 / 1e8
                    lines.append(f"- 总市值: {mv_hkd_yi:.0f} 亿港元")

                # 股本
                shares = info.get("sharesOutstanding")
                if shares:
                    lines.append(f"- 总股本: {shares / 1e8:.2f} 亿股")

                # 52周高低
                fifty_two_week_high = info.get("fiftyTwoWeekHigh")
                fifty_two_week_low = info.get("fiftyTwoWeekLow")
                if fifty_two_week_high:
                    lines.append(f"- 52周最高: {fifty_two_week_high:.2f}")
                if fifty_two_week_low:
                    lines.append(f"- 52周最低: {fifty_two_week_low:.2f}")

            except Exception as e:
                lines.append(f"- 获取详细信息失败: {e}")
    except Exception as e:
        lines.append(f"- 获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def _fetch_daily_prices(ak_code, sina_prefix, market, start_date, end_date):
    """获取日线数据，多源切换：腾讯(A股) → 东方财富 → yfinance(港股/美股)"""
    df = pd.DataFrame()

    if market == "A":
        # 优先腾讯源
        df = _safe_call(ak.stock_zh_a_daily, symbol=sina_prefix,
                        start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and len(df) > 0:
            col_map = {"date": "日期", "open": "开盘", "high": "最高", "low": "最低",
                       "close": "收盘", "volume": "成交量"}
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            return df
        # 备用东方财富
        df = _safe_call(ak.stock_zh_a_hist, symbol=ak_code, period="daily",
                        start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and len(df) > 0:
            return df

    elif market == "HK":
        df = _safe_call(ak.stock_hk_hist, symbol=ak_code, period="daily",
                        start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and len(df) > 0:
            return df
        # yfinance 备用
        print("    AKShare港股接口失败，切换 yfinance...")
        try:
            import yfinance as yf
            # yfinance 港股用4位代码 (0700.HK 不是 00700.HK)
            yf_code = f"{ak_code.lstrip('0').zfill(4)}.HK"
            print(f"    yfinance code: {yf_code}")
            td = yf.Ticker(yf_code)
            # yfinance 需要 YYYY-MM-DD 格式
            yf_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            yf_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            df = td.history(start=yf_start, end=yf_end)
            if df is not None and len(df) > 0:
                df = df.rename(columns={"Open": "开盘", "High": "最高", "Low": "最低",
                                        "Close": "收盘", "Volume": "成交量"})
                df["日期"] = df.index.strftime("%Y-%m-%d")
                df = df.reset_index(drop=True)
                return df
        except Exception as e:
            print(f"    [FAIL] yfinance: {e}")

    return df


def get_market_data(ak_code, sina_prefix, market) -> str:
    """§2 市场行情"""
    lines = ["\n## 2. 市场行情\n"]
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        df = _fetch_daily_prices(ak_code, sina_prefix, market, start_date, end_date)

        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            high52 = df["最高"].max()
            low52 = df["最低"].min()
            lines.append("| 指标 | 值 |")
            lines.append("|------|-----|")
            lines.append(f"| 最新收盘价 | {latest['收盘']} |")
            lines.append(f"| 52周最高 | {high52} |")
            lines.append(f"| 52周最低 | {low52} |")
            first_close = df.iloc[0]["收盘"]
            lines.append(f"| 52周涨幅 | {fmt_pct((latest['收盘'] - first_close) / first_close)} |")
            lines.append(f"| 日均成交量 | {fmt_num(df['成交量'].mean() / 1e4)} 万股 |")
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_income_statement(sina_prefix, market) -> str:
    """§3 合并利润表（新浪源，5年年报）"""
    lines = ["\n## 3. 合并利润表\n"]
    try:
        if market != "A":
            lines.append("非A股暂仅支持 A 股利润表\n")
            return "\n".join(lines)

        df = _safe_call(ak.stock_financial_report_sina, stock=sina_prefix, symbol="利润表")
        if df is not None and len(df) > 0:
            annual = df[df["报告日"].astype(str).str.endswith("1231")].head(5)
            key_cols = ["报告日", "营业总收入", "营业收入", "营业总成本", "营业成本",
                        "净利润", "归属于母公司所有者的净利润"]
            existing = [c for c in key_cols if c in annual.columns]
            subset = annual[existing].copy()
            # 转为百万元
            for c in existing[1:]:
                subset[c] = subset[c].apply(lambda x: f"{_fmt_million(x):,.2f}" if pd.notna(x) else "N/A")
            lines.append("单位: 百万元\n")
            lines.append(subset.to_markdown(index=False))
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_balance_sheet(sina_prefix, market) -> str:
    """§4 合并资产负债表（新浪源，5年年报）"""
    lines = ["\n## 4. 合并资产负债表\n"]
    try:
        if market != "A":
            lines.append("非A股暂仅支持 A 股资产负债表\n")
            return "\n".join(lines)

        df = _safe_call(ak.stock_financial_report_sina, stock=sina_prefix, symbol="资产负债表")
        if df is not None and len(df) > 0:
            annual = df[df["报告日"].astype(str).str.endswith("1231")].head(5)
            key_cols = ["报告日", "资产总计", "负债合计",
                        "所有者权益(或股东权益)合计", "归属于母公司股东权益合计",
                        "实收资本(或股本)", "流动资产合计", "非流动资产合计"]
            existing = [c for c in key_cols if c in annual.columns]
            subset = annual[existing].copy()
            for c in existing[1:]:
                subset[c] = subset[c].apply(lambda x: f"{_fmt_million(x):,.2f}" if pd.notna(x) else "N/A")
            lines.append("单位: 百万元\n")
            lines.append(subset.to_markdown(index=False))
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_cashflow_statement(sina_prefix, market) -> str:
    """§5 现金流量表（新浪源，5年年报）"""
    lines = ["\n## 5. 现金流量表\n"]
    try:
        if market != "A":
            lines.append("非A股暂仅支持 A 股现金流量表\n")
            return "\n".join(lines)

        df = _safe_call(ak.stock_financial_report_sina, stock=sina_prefix, symbol="现金流量表")
        if df is not None and len(df) > 0:
            annual = df[df["报告日"].astype(str).str.endswith("1231")].head(5)
            key_cols = ["报告日", "经营活动产生的现金流量净额",
                        "投资活动产生的现金流量净额", "筹资活动产生的现金流量净额",
                        "现金及现金等价物净增加额"]
            # 找到 FCF 相关：经营现金流 - 资本支出
            capex_col = None
            for c in annual.columns:
                if "购建固定资产" in c or "资本支出" in c:
                    capex_col = c
                    break

            existing = [c for c in key_cols if c in annual.columns]
            subset = annual[existing].copy()

            # 计算 FCF
            if capex_col and capex_col in annual.columns:
                subset["自由现金流(估)"] = annual["经营活动产生的现金流量净额"].astype(float) + annual[capex_col].astype(float)
                existing.append("自由现金流(估)")

            for c in existing[1:]:
                subset[c] = subset[c].apply(lambda x: f"{_fmt_million(x):,.2f}" if pd.notna(x) and not isinstance(x, str) else x)

            lines.append("单位: 百万元\n")
            lines.append(subset.to_markdown(index=False))
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_dividend_history(ak_code, market) -> str:
    """§6 分红历史"""
    lines = ["\n## 6. 分红历史\n"]
    try:
        if market == "A":
            df = _safe_call(ak.stock_history_dividend_detail, symbol=ak_code, indicator="分红")
            if df is not None and len(df) > 0:
                lines.append("| 公告日期 | 送股 | 转增 | 派息(每10股) | 除权除息日 |")
                lines.append("|----------|------|------|-------------|-----------|")
                for _, row in df.head(10).iterrows():
                    lines.append(f"| {row.get('公告日期', 'N/A')} | {row.get('送股', 0)} | "
                                 f"{row.get('转增', 0)} | {row.get('派息', 'N/A')} | "
                                 f"{row.get('除权除息日', 'N/A')} |")
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_financial_abstract(ak_code, market) -> str:
    """§12 关键财务指标 — 同花顺"""
    lines = ["\n## 12. 关键财务指标\n"]
    try:
        if market != "A":
            lines.append("非A股暂不支持同花顺财务摘要\n")
            return "\n".join(lines)

        df = _safe_call(ak.stock_financial_abstract_ths, symbol=ak_code, indicator="按年度")
        if df is not None and len(df) > 0:
            df_recent = df.tail(5).iloc[::-1]
            lines.append("| 报告期 | 营业总收入 | 归母净利润 | 销售毛利率 | 净资产收益率 |")
            lines.append("|--------|-----------|-----------|-----------|-------------|")
            for _, row in df_recent.iterrows():
                lines.append(f"| {row.get('报告期', 'N/A')} | {row.get('营业总收入', 'N/A')} | "
                             f"{row.get('归母净利润', 'N/A')} | {row.get('销售毛利率', 'N/A')} | "
                             f"{row.get('净资产收益率', 'N/A')} |")
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_weekly_10y(ak_code, sina_prefix, market) -> str:
    """§11 十年周线行情"""
    lines = ["\n## 11. 十年周线行情\n"]
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=365 * 10)).strftime("%Y%m%d")

        df = _fetch_daily_prices(ak_code, sina_prefix, market, start_date, end_date)

        if df is not None and len(df) > 0:
            low10 = df["最低"].min()
            high10 = df["最高"].max()
            current = df.iloc[-1]["收盘"]
            pct = (current - low10) / (high10 - low10) if high10 != low10 else 0
            lines.append(f"- 10年数据点: {len(df)} 个")
            lines.append(f"- 10年最低: {low10}")
            lines.append(f"- 10年最高: {high10}")
            lines.append(f"- 当前价: {current}")
            lines.append(f"- 10年百分位: {fmt_pct(pct)}")
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_risk_free_rate() -> str:
    """§14 无风险利率"""
    lines = ["\n## 14. 无风险利率\n"]
    lines.append("- 默认值: 1.8% (中国10年期国债收益率近似值)")
    lines.append("- 说明: 实际使用时建议查询最新国债收益率")
    lines.append("")
    return "\n".join(lines)


def get_top10_holders(ak_code, market) -> str:
    """§7 股东与治理 — 前5大股东（新浪源）"""
    lines = ["\n## 7. 股东与治理\n"]
    try:
        if market != "A":
            lines.append("*非A股暂不支持股东数据自动采集*\n")
            return "\n".join(lines)

        df = _safe_call(ak.stock_main_stock_holder, stock=ak_code)
        if df is not None and len(df) > 0:
            # 取最近一期
            latest_date = df["截至日期"].max()
            latest = df[df["截至日期"] == latest_date].head(5)
            lines.append(f"截至日期: {latest_date} | 股东总数: {latest['股东总数'].iloc[0]:,.0f}\n")
            lines.append("| # | 股东名称 | 持股数量(万股) | 持股比例 | 股本性质 |")
            lines.append("|---|---------|--------------|---------|---------|")
            for _, row in latest.iterrows():
                shares = row.get("持股数量", "N/A")
                if shares != "N/A" and pd.notna(shares):
                    shares = f"{float(shares)/1e4:,.2f}"
                lines.append(f"| {row.get('编号', 'N/A')} | {row.get('股东名称', 'N/A')} | "
                             f"{shares} | {row.get('持股比例', 'N/A')} | {row.get('股本性质', 'N/A')} |")
        else:
            lines.append("*[§7 待Agent WebSearch补充]*")
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_auto_warnings(ak_code, ts_code, market) -> str:
    """§13 风险警示 — 自动检测"""
    lines = ["\n## 13. 风险警示\n"]
    warnings = []

    if market == "A":
        # 检查 ST / 退市
        try:
            df = _safe_call(ak.stock_zh_a_spot_em)
            if df is not None and len(df) > 0:
                row = df[df["代码"] == ak_code]
                if len(row) > 0:
                    name = row.iloc[0].get("名称", "")
                    if "ST" in name or "*ST" in name:
                        warnings.append(f"⚠️ ST/退市风险: 当前名称 \"{name}\"")
                    pe = row.iloc[0].get("市盈率-动态", None)
                    if pe is not None and pe != "-" and float(pe) < 0:
                        warnings.append(f"⚠️ 亏损企业: 市盈率(TTM) = {pe}")
        except Exception:
            pass

        # 检查质押比
        try:
            df = _safe_call(ak.stock_gpzy_pledge_ratio_em)
            if df is not None and len(df) > 0:
                row = df[df["股票代码"].astype(str) == ak_code]
                if len(row) > 0:
                    ratio = row.iloc[0].get("质押比例", 0)
                    if float(ratio) > 50:
                        warnings.append(f"⚠️ 高质押风险: 质押比例 {ratio}% (>50%)")
                    elif float(ratio) > 30:
                        warnings.append(f"⚡ 中等质押: 质押比例 {ratio}%")
        except Exception:
            pass

    if warnings:
        lines.append("### 13.1 脚本自动检测\n")
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("### 13.1 脚本自动检测\n")
        lines.append("- 未检测到明显风险信号")

    lines.append("\n### 13.2 Agent WebSearch 补充\n")
    lines.append("*[§13.2 待Agent WebSearch补充]*")
    lines.append("")
    return "\n".join(lines)


def get_repurchase(ak_code, market) -> str:
    """§15 股票回购"""
    lines = ["\n## 15. 股票回购\n"]
    try:
        if market != "A":
            lines.append("*非A股暂不支持回购数据*\n")
            return "\n".join(lines)

        df = _safe_call(ak.stock_repurchase_em)
        if df is not None and len(df) > 0:
            row = df[df["股票代码"].astype(str) == ak_code]
            if len(row) > 0:
                lines.append("| 起始时间 | 计划金额(亿) | 已回购金额(亿) | 进度 |")
                lines.append("|---------|-------------|---------------|------|")
                for _, r in row.head(5).iterrows():
                    plan_amt = r.get("计划回购金额区间-上限", 0)
                    done_amt = r.get("已回购金额", 0)
                    plan_yi = f"{float(plan_amt)/1e8:.2f}" if pd.notna(plan_amt) else "N/A"
                    done_yi = f"{float(done_amt)/1e8:.2f}" if pd.notna(done_amt) else "N/A"
                    lines.append(f"| {r.get('回购起始时间', 'N/A')} | {plan_yi} | {done_yi} | {r.get('实施进度', 'N/A')} |")
            else:
                lines.append("- 无回购记录")
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_pledge(ak_code, market) -> str:
    """§16 股权质押"""
    lines = ["\n## 16. 股权质押\n"]
    try:
        if market != "A":
            lines.append("*非A股暂不支持质押数据*\n")
            return "\n".join(lines)

        df = _safe_call(ak.stock_gpzy_individual_pledge_ratio_detail_em, symbol=ak_code)
        if df is not None and len(df) > 0:
            # 统计
            total_pledge = df["质押股份数量"].sum()
            active = df[df["状态"] == "未解押"]
            active_count = len(active)
            lines.append(f"- 质押记录总数: {len(df)} 笔")
            lines.append(f"- 未解押笔数: {active_count} 笔")
            lines.append(f"- 质押股份总数: {total_pledge/1e4:,.2f} 万股")

            if active_count > 0:
                lines.append("\n**未解押明细:**\n")
                lines.append("| 股东名称 | 质押数量(万股) | 占总股本比 | 机构 | 状态 |")
                lines.append("|---------|--------------|-----------|------|------|")
                for _, r in active.head(5).iterrows():
                    qty = r.get("质押股份数量", 0)
                    lines.append(f"| {r.get('股东名称', 'N/A')} | "
                                 f"{float(qty)/1e4:,.2f} | "
                                 f"{r.get('占总股本比例', 'N/A')}% | "
                                 f"{str(r.get('质押机构', 'N/A'))[:20]} | "
                                 f"{r.get('状态', 'N/A')} |")
        else:
            lines.append("- 无质押记录")
    except Exception as e:
        lines.append(f"获取失败: {e}")
    lines.append("")
    return "\n".join(lines)


def get_derived_metrics(sina_prefix, market) -> str:
    """§17 衍生指标预计算 — 从财务报表计算关键指标"""
    lines = ["\n## 17. 衍生指标\n"]
    try:
        if market != "A":
            lines.append("*非A股暂不支持衍生指标计算*\n")
            return "\n".join(lines)

        # 从利润表和资产负债表取数
        df_inc = _safe_call(ak.stock_financial_report_sina, stock=sina_prefix, symbol="利润表")
        df_bs = _safe_call(ak.stock_financial_report_sina, stock=sina_prefix, symbol="资产负债表")
        df_cf = _safe_call(ak.stock_financial_report_sina, stock=sina_prefix, symbol="现金流量表")

        if df_inc is None or len(df_inc) == 0:
            lines.append("*利润表数据不足，无法计算*")
            lines.append("")
            return "\n".join(lines)

        annual_inc = df_inc[df_inc["报告日"].astype(str).str.endswith("1231")].head(3)

        lines.append("### 17.1 关键比率 (最近3年年报)\n")
        lines.append("| 指标 | " + " | ".join(str(y)[:4] for y in annual_inc["报告日"]) + " |")
        lines.append("|------|" + "|".join(["------"] * len(annual_inc)) + "|")

        # 净利润
        ni_col = "归属于母公司所有者的净利润"
        if ni_col in annual_inc.columns:
            vals = [f"{_fmt_million(v):,.0f}" if pd.notna(v) else "N/A" for v in annual_inc[ni_col]]
            lines.append(f"| 归母净利润(百万) | " + " | ".join(vals) + " |")

        # 营业收入
        rev_col = "营业总收入"
        if rev_col in annual_inc.columns:
            vals = [f"{_fmt_million(v):,.0f}" if pd.notna(v) else "N/A" for v in annual_inc[rev_col]]
            lines.append(f"| 营业总收入(百万) | " + " | ".join(vals) + " |")

        # ROE = 归母净利润 / 归母股东权益
        if df_bs is not None and len(df_bs) > 0:
            annual_bs = df_bs[df_bs["报告日"].astype(str).str.endswith("1231")].head(3)
            eq_col = "归属于母公司股东权益合计"
            if ni_col in annual_inc.columns and eq_col in annual_bs.columns and len(annual_bs) > 0:
                roe_vals = []
                for i in range(min(len(annual_inc), len(annual_bs))):
                    ni = annual_inc.iloc[i][ni_col]
                    eq = annual_bs.iloc[i][eq_col]
                    if pd.notna(ni) and pd.notna(eq) and float(eq) != 0:
                        roe_vals.append(f"{float(ni)/float(eq)*100:.1f}%")
                    else:
                        roe_vals.append("N/A")
                lines.append(f"| ROE | " + " | ".join(roe_vals) + " |")

        # FCF = 经营现金流 - 资本支出
        if df_cf is not None and len(df_cf) > 0:
            annual_cf = df_cf[df_cf["报告日"].astype(str).str.endswith("1231")].head(3)
            ocf_col = "经营活动产生的现金流量净额"
            capex_col = None
            for c in annual_cf.columns:
                if "购建固定资产" in c or "资本支出" in c:
                    capex_col = c
                    break
            if ocf_col in annual_cf.columns and capex_col:
                fcf_vals = []
                for _, r in annual_cf.iterrows():
                    ocf = r.get(ocf_col)
                    capex = r.get(capex_col)
                    if pd.notna(ocf) and pd.notna(capex):
                        fcf_vals.append(f"{_fmt_million(float(ocf)+float(capex)):,.0f}")
                    else:
                        fcf_vals.append("N/A")
                lines.append(f"| 自由现金流(百万,估) | " + " | ".join(fcf_vals) + " |")

        lines.append("\n### 17.2 龟龟策略参数\n")
        lines.append("*以下参数需要 Agent 在 Phase 3 中根据穿透回报率精算流程计算：*")
        lines.append("- M (分配意愿): 待 Phase 3 计算")
        lines.append("- R% (粗算穿透回报率): 待 Phase 3 计算")
        lines.append("- GG% (精算穿透回报率): 待 Phase 3 计算")
        lines.append("- λ 系数: 待 Phase 3 计算")

    except Exception as e:
        lines.append(f"计算失败: {e}")
    lines.append("")
    return "\n".join(lines)


# ─── 主流程 ───

STEPS = [
    ("基本信息",   lambda a, t, s, m: get_basic_info(a, t, s, m)),
    ("市场行情",   lambda a, t, s, m: get_market_data(a, s, m)),
    ("利润表",     lambda a, t, s, m: get_income_statement(s, m)),
    ("资产负债表", lambda a, t, s, m: get_balance_sheet(s, m)),
    ("现金流量表", lambda a, t, s, m: get_cashflow_statement(s, m)),
    ("分红历史",   lambda a, t, s, m: get_dividend_history(a, m)),
    ("股东与治理", lambda a, t, s, m: get_top10_holders(a, m)),
    ("财务指标",   lambda a, t, s, m: get_financial_abstract(a, m)),
    ("十年周线",   lambda a, t, s, m: get_weekly_10y(a, s, m)),
    ("风险警示",   lambda a, t, s, m: get_auto_warnings(a, t, m)),
    ("无风险利率", lambda a, t, s, m: get_risk_free_rate()),
    ("股票回购",   lambda a, t, s, m: get_repurchase(a, m)),
    ("股权质押",   lambda a, t, s, m: get_pledge(a, m)),
    ("衍生指标",   lambda a, t, s, m: get_derived_metrics(s, m)),
]


def collect(code: str, output_path: str = None) -> str:
    ak_code, ts_code, sina_prefix, market = _normalize_code(code)
    print(f"=== AKShare 数据采集 ===")
    print(f"  输入: {code} → {ts_code} ({market}股)\n")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    unit = {"A": "百万元", "HK": "百万港元", "US": "百万美元"}[market]

    sections = [
        f"# 数据包 — {ts_code}\n",
        f"*生成时间: {timestamp} | 数据源: AKShare (腾讯/新浪/同花顺) | 单位: {unit}*\n",
    ]

    for i, (name, func) in enumerate(STEPS, 1):
        print(f"[{i}/{len(STEPS)}] {name}...")
        try:
            sections.append(func(ak_code, ts_code, sina_prefix, market))
        except Exception as e:
            sections.append(f"\n## {name}\n\n获取失败: {e}\n")
        time.sleep(1)

    # 占位符
    sections.append("\n---\n")
    sections.append("*此数据包由 AKShare 采集器生成。§8 行业与竞争、§10 MD&A 摘要需 Agent WebSearch 补充。*\n")
    sections.append("\n## 8. 行业与竞争\n\n*[§8 待Agent WebSearch补充]*\n")
    sections.append("\n## 9. 主营业务构成\n\n*[§9 待Agent WebSearch补充]*\n")
    sections.append("\n## 10. MD&A 摘要\n\n*[§10 待Agent WebSearch补充]*\n")

    full_text = "\n".join(sections)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"\n[OK] 数据包已保存: {output_path}")

    return full_text


def main():
    parser = argparse.ArgumentParser(description="AKShare 数据采集器 (龟龟框架兼容)")
    parser.add_argument("--code", required=True, help="股票代码 (如 600887, 00700.HK)")
    parser.add_argument("--output", default="output/data_pack_market.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        ak_code, ts_code, sina_prefix, market = _normalize_code(args.code)
        print(f"  Input:  {args.code}")
        print(f"  TS:     {ts_code}")
        print(f"  AK:     {ak_code}")
        print(f"  Sina:   {sina_prefix}")
        print(f"  Market: {market}")
        print(f"  Output: {args.output}")
        return

    collect(args.code, args.output)


if __name__ == "__main__":
    main()
