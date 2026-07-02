"""港股选股器 — 基于AKShare数据进行批量筛选

用法:
    # 从代码列表筛选
    python scripts/hk_screener.py --codes 00700.HK,09988.HK

    # 从文件导入
    python scripts/hk_screener.py --file stock_list.txt

    # 价格区间筛选（52周低位）
    python scripts/hk_screener.py --file stock_list.txt --price-percentile 0-30

    # 自动触发分析
    python scripts/hk_screener.py --file stock_list.txt --auto-analyze
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from format_utils import format_number, format_table


@dataclass
class StockInfo:
    code: str
    name: str = ""
    industry: str = ""  # 行业
    market_cap: float = 0  # 市值（亿）
    shares: float = 0  # 股本（亿股）
    price: float = 0
    week_52_high: float = 0
    week_52_low: float = 0
    week_52_percentile: float = 0  # 52周价格百分位
    year_10_high: float = 0
    year_10_low: float = 0
    year_10_percentile: float = 0  # 10年价格百分位
    data_file: str = ""  # 数据包文件路径

    @property
    def week_52_range(self) -> float:
        if self.week_52_high == 0:
            return 0
        return self.week_52_high - self.week_52_low

    @property
    def week_52_position(self) -> float:
        """当前价在52周区间的位置 (0-100%)"""
        if self.week_52_range == 0:
            return 50
        return ((self.price - self.week_52_low) / self.week_52_range) * 100

    @property
    def market_cap_tier(self) -> str:
        """市值分级"""
        if self.market_cap >= 1000:
            return "超大盘(>1000亿)"
        elif self.market_cap >= 500:
            return "大盘(500-1000亿)"
        elif self.market_cap >= 100:
            return "中盘(100-500亿)"
        elif self.market_cap >= 50:
            return "小盘(50-100亿)"
        else:
            return "微型(<50亿)"

    @property
    def is_near_52w_low(self) -> bool:
        """是否接近52周低位（30%以下）"""
        return self.week_52_percentile < 30


class HkStockScreener:
    """港股选股器"""

    def __init__(
        self,
        output_dir: str = "output/hk_screener",
        provider: str = "akshare",
        price_filter: Optional[tuple] = None,  # (min, max) 百分位
        valuation_filter: Optional[dict] = None,  # {"pe_min": 0, "pb_max": 1}
    ):
        self.output_dir = output_dir
        self.provider = provider
        self.price_filter = price_filter  # (min_percentile, max_percentile)
        self.valuation_filter = valuation_filter or {}
        self.stocks: List[StockInfo] = []
        os.makedirs(output_dir, exist_ok=True)

    def load_codes_from_file(self, filepath: str) -> List[tuple]:
        """从文件加载股票代码列表

        文件格式：
        00700.HK  腾讯控股
        09988.HK  阿里巴巴
        """
        codes = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 1:
                    code = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else ""
                    codes.append((code, name))
        return codes

    def fetch_data(self, codes: List[tuple]) -> List[StockInfo]:
        """批量采集数据"""
        print(f"\n=== 港股数据采集 ===")
        print(f"股票数量: {len(codes)}")
        print(f"数据源: {self.provider.upper()}")
        print(f"输出目录: {self.output_dir}\n")

        results = []

        for i, (code, name) in enumerate(codes, 1):
            print(f"[{i}/{len(codes)}] 采集 {code} {name}...")

            # 生成数据包文件名
            safe_name = name.replace(" ", "_") if name else code
            output_file = os.path.join(self.output_dir, f"{code}_{safe_name}.md")

            # 调用 data_collector.py
            try:
                cmd = [
                    sys.executable,
                    os.path.join(os.path.dirname(__file__), "data_collector.py"),
                    "--code", code,
                    "--provider", self.provider,
                    "--output", output_file,
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,
                    timeout=60,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

                if result.returncode == 0 and os.path.exists(output_file):
                    stock_info = self._parse_data_pack(output_file, code, name)
                    if stock_info:
                        results.append(stock_info)
                        print(f"    [OK] 成功: 最新价={stock_info.price:.2f}, "
                              f"52周%={stock_info.week_52_percentile:.1f}%")
                    else:
                        print(f"    [WARN] 数据解析失败")
                else:
                    print(f"    [FAIL] 采集失败")

            except subprocess.TimeoutExpired:
                print(f"    [FAIL] 超时")
            except Exception as e:
                print(f"    [FAIL] 错误: {e}")

        self.stocks = results
        return results

    def _parse_data_pack(self, filepath: str, code: str, name: str) -> Optional[StockInfo]:
        """解析数据包文件，提取关键信息"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            info = StockInfo(code=code, name=name, data_file=filepath)

            lines = content.split("\n")

            # 解析 §1 基本信息
            for line in lines:
                if "股票简称:" in line:
                    match = re.search(r"股票简称:\s*(.+)", line)
                    if match:
                        info.name = match.group(1).strip()
                elif "行业:" in line:
                    match = re.search(r"行业:\s*(.+)", line)
                    if match:
                        info.industry = match.group(1).strip()
                elif "总市值:" in line:
                    # 匹配 "1642.06 亿元" 或 "100.5 亿港元"
                    match = re.search(r"总市值:\s*([\d.]+)\s*([亿]*)(.*)", line)
                    if match:
                        info.market_cap = float(match.group(1))
                elif "总股本:" in line:
                    match = re.search(r"总股本:\s*([\d.]+)", line)
                    if match:
                        info.shares = float(match.group(1))

            # 解析 §2 市场行情 (markdown表格格式)
            in_market_section = False
            for i, line in enumerate(lines):
                if "## 2." in line and "市场行情" in line:
                    in_market_section = True
                    continue
                if in_market_section:
                    if line.strip().startswith("|") and not line.strip().startswith("|---"):
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 3:
                            field = parts[1]
                            value_str = parts[2]
                            try:
                                value = float(value_str)
                                if "最新收盘价" in field or "最新价" in field:
                                    info.price = value
                                elif "52周最高" in field:
                                    info.week_52_high = value
                                elif "52周最低" in field:
                                    info.week_52_low = value
                            except ValueError:
                                pass
                    elif line.strip().startswith("##"):
                        break

            # 解析 §11 十年周线
            for line in lines:
                if "10年最高:" in line:
                    match = re.search(r"10年最高:\s*([\d.]+)", line)
                    if match:
                        info.year_10_high = float(match.group(1))
                elif "10年最低:" in line:
                    match = re.search(r"10年最低:\s*([\d.]+)", line)
                    if match:
                        info.year_10_low = float(match.group(1))
                elif "10年百分位:" in line:
                    match = re.search(r"10年百分位:\s*([\d.]+)%", line)
                    if match:
                        info.year_10_percentile = float(match.group(1))

            # 计算52周百分位
            info.week_52_percentile = info.week_52_position

            return info

        except Exception as e:
            print(f"    解析错误: {e}")
            return None

    def filter_by_price(self) -> List[StockInfo]:
        """按价格区间筛选"""
        if not self.price_filter:
            return self.stocks

        min_p, max_p = self.price_filter
        filtered = [
            s for s in self.stocks
            if min_p <= s.week_52_percentile <= max_p
        ]
        print(f"\n价格筛选 ({min_p}%-{max_p}%): {len(filtered)}/{len(self.stocks)} 只符合")
        return filtered

    def filter_by_valuation(self) -> List[StockInfo]:
        """按估值筛选（暂未实现，需财务数据）"""
        # TODO: 需要PE/PB数据，当前AKShare港股不支持
        return self.stocks

    def generate_report(self, filtered: List[StockInfo]) -> str:
        """生成筛选报告"""
        report_path = os.path.join(self.output_dir, "screening_report.md")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# 港股筛选报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**数据源**: AKShare + yfinance\n\n")
            f.write(f"**股票池**: {len(self.stocks)} 只\n\n")
            f.write(f"**符合条件**: {len(filtered)} 只\n\n")

            # 筛选条件
            f.write(f"## 筛选条件\n\n")
            if self.price_filter:
                min_p, max_p = self.price_filter
                f.write(f"- **价格区间**: 52周百分位 {min_p}%-{max_p}%\n")
            else:
                f.write(f"- **价格区间**: 无限制\n")
            f.write(f"\n")

            # 符合条件的股票 - 详细表
            f.write(f"## 符合条件 ({len(filtered)}只)\n\n")
            if filtered:
                f.write(f"| 代码 | 名称 | 行业 | 市值 | 市值分级 | 最新价 | 52周% | 10年% |\n")
                f.write(f"|------|------|------|------|----------|--------|-------|-------|\n")
                for s in sorted(filtered, key=lambda x: x.week_52_percentile):
                    mv_str = f"{s.market_cap:.0f}" if s.market_cap else "N/A"
                    f.write(f"| {s.code} | {s.name} | {s.industry} | {mv_str} | {s.market_cap_tier} | "
                           f"{s.price:.2f} | {s.week_52_percentile:.1f}% | {s.year_10_percentile:.1f}% |\n")
            else:
                f.write(f"无符合条件的股票\n\n")

            # 按行业分类
            f.write(f"\n## 行业分布\n\n")
            industries = {}
            for s in filtered:
                if s.industry:
                    industries[s.industry] = industries.get(s.industry, 0) + 1
            if industries:
                for ind, count in sorted(industries.items(), key=lambda x: -x[1]):
                    f.write(f"- **{ind}**: {count}只\n")

            # 市值分布
            f.write(f"\n## 市值分布\n\n")
            cap_tiers = {}
            for s in filtered:
                tier = s.market_cap_tier
                cap_tiers[tier] = cap_tiers.get(tier, 0) + 1
            if cap_tiers:
                for tier, count in sorted(cap_tiers.items()):
                    f.write(f"- **{tier}**: {count}只\n")

            # 低位股标记
            f.write(f"\n## 52周低位股 (<30%)\n\n")
            low_stocks = [s for s in filtered if s.is_near_52w_low]
            if low_stocks:
                f.write(f"| 代码 | 名称 | 52周% |\n")
                f.write(f"|------|------|-------|\n")
                for s in sorted(low_stocks, key=lambda x: x.week_52_percentile):
                    f.write(f"| {s.code} | {s.name} | {s.week_52_percentile:.1f}% |\n")
            else:
                f.write(f"无\n")

            # 全部股票列表
            f.write(f"\n## 全部股票列表 ({len(self.stocks)}只)\n\n")
            if self.stocks:
                f.write(f"| 代码 | 名称 | 行业 | 市值 | 52周% | 10年% |\n")
                f.write(f"|------|------|------|------|-------|-------|\n")
                for s in sorted(self.stocks, key=lambda x: x.week_52_percentile):
                    status = "[OK]" if s in filtered else " "
                    mv_str = f"{s.market_cap:.0f}" if s.market_cap else "N/A"
                    f.write(f"| {status} {s.code} | {s.name} | {s.industry} | {mv_str} | "
                           f"{s.week_52_percentile:.1f}% | {s.year_10_percentile:.1f}% |\n")

        print(f"\n报告已生成: {report_path}")
        return report_path

    def auto_analyze(self, stocks: List[StockInfo]):
        """自动触发定性分析"""
        print(f"\n=== 自动分析队列 ===")

        for i, stock in enumerate(stocks, 1):
            print(f"\n[{i}/{len(stocks)}] 分析 {stock.code} {stock.name}...")
            print(f"    (功能待实现: 调用 /business-analysis {stock.code})")

        print(f"\n提示: 自动分析需要通过 Claude Code 技能调用")


def main():
    parser = argparse.ArgumentParser(description="港股选股器")
    parser.add_argument("--codes", help="股票代码列表，逗号分隔，如 00700.HK,09988.HK")
    parser.add_argument("--file", help="股票列表文件")
    parser.add_argument("--provider", default="akshare", help="数据提供商 (akshare/tushare)")
    parser.add_argument("--price-percentile", help="价格百分位范围，如 0-30")
    parser.add_argument("--output-dir", default="output/hk_screener", help="输出目录")
    parser.add_argument("--auto-analyze", action="store_true", help="自动触发分析")

    args = parser.parse_args()

    # 解析价格筛选条件
    price_filter = None
    if args.price_percentile:
        match = re.match(r"(\d+)-(\d+)", args.price_percentile)
        if match:
            price_filter = (float(match.group(1)), float(match.group(2)))

    # 加载股票代码
    codes = []
    if args.file:
        screener = HkStockScreener(
            output_dir=args.output_dir,
            provider=args.provider,
            price_filter=price_filter,
        )
        codes = screener.load_codes_from_file(args.file)
    elif args.codes:
        codes = [(c.strip(), "") for c in args.codes.split(",")]
        screener = HkStockScreener(
            output_dir=args.output_dir,
            provider=args.provider,
            price_filter=price_filter,
        )
    else:
        # 默认港股列表
        codes = [
            ("00700.HK", "腾讯控股"),
            ("09988.HK", "阿里巴巴"),
            ("01810.HK", "小米集团"),
            ("02318.HK", "中国平安"),
            ("03690.HK", "美团"),
        ]
        screener = HkStockScreener(
            output_dir=args.output_dir,
            provider=args.provider,
            price_filter=price_filter,
        )

    # 采集数据
    screener.fetch_data(codes)

    # 筛选
    filtered = screener.filter_by_price()

    # 生成报告
    report_path = screener.generate_report(filtered)
    print(f"\n[OK] 筛选完成!")

    # 自动分析
    if args.auto_analyze and filtered:
        screener.auto_analyze(filtered)


if __name__ == "__main__":
    main()
