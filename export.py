#!/usr/bin/env python3
"""
导出推荐结果
用法:
  python export.py                    # 导出 markdown（默认）
  python export.py --format json      # 导出 json
  python export.py -f csv -o rec.csv # 导出 csv
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from github_rec.storage import Storage

DEFAULT_DB = "data/stars.db"


def main():
    parser = argparse.ArgumentParser(description="导出推荐结果")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"数据库路径 (默认: {DEFAULT_DB})")
    parser.add_argument("-f", "--format", choices=["json", "markdown", "csv"],
                         default="markdown")
    parser.add_argument("-o", "--output", help="输出文件路径")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"数据库不存在: {args.db}")
        sys.exit(1)

    storage = Storage(args.db)
    recs = storage.get_recommendations()

    if not recs:
        print("没有推荐结果，请先运行: python recommend.py recommend")
        sys.exit(1)

    if args.format == "json":
        path = args.output or "recommendations.json"
        data = []
        for r in recs:
            reasons = r.get("reasons", [])
            if isinstance(reasons, str):
                reasons = json.loads(reasons)
            data.append({
                "full_name": r["full_name"],
                "language": r.get("language") or "",
                "stars": r.get("stars", 0),
                "forks": r.get("forks", 0),
                "url": r.get("html_url") or f"https://github.com/{r['full_name']}",
                "description": r.get("description") or "",
                "score": r.get("score", 0),
                "reasons": reasons,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ 已导出 {len(recs)} 条到 {path}")

    elif args.format == "markdown":
        path = args.output or "recommendations.md"
        lines = [
            f"# 为你推荐的 {len(recs)} 个仓库\n",
            "| # | 仓库 | 语言 | ★ | 推荐原因 |",
            "|---|------|------|---|----------|",
        ]
        for i, rec in enumerate(recs, 1):
            stars = rec.get("stars", 0)
            lang = rec.get("language") or "N/A"
            reasons_raw = rec.get("reasons", [])
            if isinstance(reasons_raw, str):
                reasons_raw = json.loads(reasons_raw)
            reasons = " · ".join(reasons_raw[:2])
            url = f"https://github.com/{rec['full_name']}"
            lines.append(f"| {i} | [{rec['full_name']}]({url}) | {lang} | {stars} | {reasons} |")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"✓ 已导出 {len(recs)} 条到 {path}")

    elif args.format == "csv":
        path = args.output or "recommendations.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["#", "full_name", "language", "stars", "forks", "url", "description", "reasons"])
            for i, rec in enumerate(recs, 1):
                reasons_raw = rec.get("reasons", [])
                if isinstance(reasons_raw, str):
                    reasons_raw = json.loads(reasons_raw)
                writer.writerow([
                    i,
                    rec["full_name"],
                    rec.get("language") or "",
                    rec.get("stars", 0),
                    rec.get("forks", 0),
                    f"https://github.com/{rec['full_name']}",
                    (rec.get("description") or "")[:200],
                    " | ".join(reasons_raw),
                ])
        print(f"✓ 已导出 {len(recs)} 条到 {path}")


if __name__ == "__main__":
    main()
