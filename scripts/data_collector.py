"""统一数据采集入口 — 根据配置自动选择 Tushare 或 AKShare。

龟龟框架的所有 Phase 1A 调用都通过此脚本执行，无需修改 coordinator。

用法:
    # 自动选择（根据 .env 中的 DATA_PROVIDER 配置）
    python scripts/data_collector.py --code 600887 --output output/data_pack.md

    # 强制指定数据源
    python scripts/data_collector.py --code 600887 --output output/data_pack.md --provider akshare
    python scripts/data_collector.py --code 600887 --output output/data_pack.md --provider tushare

    # 试运行
    python scripts/data_collector.py --code 600887 --dry-run

配置优先级:
    1. --provider 命令行参数（最高）
    2. DATA_PROVIDER 环境变量 / .env 文件
    3. 自动检测：有 TUSHARE_TOKEN → tushare，无 → akshare
"""

import argparse
import os
import subprocess
import sys


def _resolve_provider(provider_arg: str = None) -> str:
    """解析数据源，优先级：命令行 > 环境变量 > 自动检测"""
    if provider_arg:
        p = provider_arg.lower().strip()
        if p in ("tushare", "ts"):
            return "tushare"
        if p in ("akshare", "ak"):
            return "akshare"
        print(f"[WARN] Unknown provider '{provider_arg}', falling back to auto-detect")

    # 用 config.py 的逻辑
    sys.path.insert(0, os.path.dirname(__file__))
    from config import get_data_provider
    return get_data_provider()


def main():
    parser = argparse.ArgumentParser(
        description="统一数据采集入口 (Tushare / AKShare 自动切换)"
    )
    parser.add_argument("--code", required=True, help="股票代码 (如 600887, 00700.HK)")
    parser.add_argument("--output", default="output/data_pack_market.md", help="输出文件路径")
    parser.add_argument("--provider", default=None,
                        help="数据源: tushare / ts / akshare / ak (不填则自动检测)")
    parser.add_argument("--refresh-market", action="store_true",
                        help="仅刷新市场敏感数据段 (§1/§2/§11/§14)")
    parser.add_argument("--dry-run", action="store_true", help="仅显示配置，不执行采集")
    parser.add_argument("--extra-fields", default=None, help="附加字段 (仅 Tushare)")
    args = parser.parse_args()

    provider = _resolve_provider(args.provider)

    print(f"=== Data Collector ===")
    print(f"  Code:     {args.code}")
    print(f"  Provider: {provider}")
    print(f"  Output:   {args.output}")
    if args.refresh_market:
        print(f"  Mode:     refresh-market")
    print()

    if args.dry_run:
        return

    # 构建子进程命令
    if provider == "tushare":
        script = os.path.join(os.path.dirname(__file__), "tushare_collector.py")
        cmd = [sys.executable, script, "--code", args.code, "--output", args.output]
        if args.refresh_market:
            cmd.append("--refresh-market")
        if args.extra_fields:
            cmd.extend(["--extra-fields", args.extra_fields])
    else:
        script = os.path.join(os.path.dirname(__file__), "akshare_collector.py")
        cmd = [sys.executable, script, "--code", args.code, "--output", args.output]
        # akshare 暂不支持 --refresh-market，忽略

    result = subprocess.run(cmd, cwd=os.path.join(os.path.dirname(__file__), ".."))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
