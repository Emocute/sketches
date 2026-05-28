"""infra-r2-cost-estimator — Cloudflare R2 ストレージ費用試算.

`r2 rclone size` で得たバケットサイズと月間 egress 想定から月額試算。
R2 は egress 無料、ストレージ $0.015/GB/月、Class A ops $4.50/百万。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-r2-cost-estimator"

STORAGE_PER_GB = 0.015
CLASS_A_PER_M = 4.50
CLASS_B_PER_M = 0.36


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra r2-cost-estimator")
    p.add_argument("--storage-gb", type=float, required=True)
    p.add_argument("--class-a-ops", type=int, default=0)
    p.add_argument("--class-b-ops", type=int, default=0)
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    free_gb = 10
    billable_gb = max(0, args.storage_gb - free_gb)
    storage_cost = billable_gb * STORAGE_PER_GB
    class_a_cost = (args.class_a_ops / 1_000_000) * CLASS_A_PER_M
    class_b_cost = (args.class_b_ops / 1_000_000) * CLASS_B_PER_M
    total = storage_cost + class_a_cost + class_b_cost
    breakdown = {
        "storage_gb": args.storage_gb,
        "billable_gb": billable_gb,
        "storage_usd": round(storage_cost, 4),
        "class_a_usd": round(class_a_cost, 4),
        "class_b_usd": round(class_b_cost, 4),
        "total_monthly_usd": round(total, 4),
    }
    if args.json:
        import json
        print(json.dumps(breakdown, indent=2))
    else:
        for k, v in breakdown.items():
            print(f"  {k:<22} {v}")
    logger.done(TOOL_ID, f"R2 monthly ≈ ${total:.2f}")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
