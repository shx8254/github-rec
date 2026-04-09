#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))

from github_rec import __version__
from github_rec.config import load_config, save_config
from github_rec.storage import Storage
from github_rec.recommender import GitHubRecommender


def cmd_fetch(client: GitHubRecommender, _args):
    client.fetch_stars()
    print("Star 数据拉取完成 ✓")


def cmd_recommend(client: GitHubRecommender, _args):
    recs = client.recommend()
    if not recs:
        print("没有找到推荐，请先运行 --fetch")
        return

    print(f"\n{'='*60}")
    print(f"  为你推荐以下 {len(recs)} 个仓库")
    print(f"{'='*60}\n")

    for i, rec in enumerate(recs, 1):
        stars = rec.get("stargazers_count", rec.get("stars", 0))
        lang = rec.get("language") or "N/A"
        print(f"  {i}. [{lang}] {rec['name']} ★{stars}")
        print(f"     {rec.get('html_url', '')}")
        for reason in rec.get("reasons", []):
            print(f"     • {reason}")
        print()


def cmd_list_stars(storage: Storage, args):
    repos = storage.get_starred_repos()
    print(f"\n你共 Star 了 {len(repos)} 个仓库:\n")
    for repo in repos[: args.limit]:
        stars = repo.get("stars", 0)
        lang = repo.get("language") or "N/A"
        topics = json.loads(repo.get("topics") or "[]")
        topics_str = f"[{', '.join(topics[:3])}]" if topics else ""
        print(f"  ★ {repo['full_name']} ({lang}) {topics_str} ★{stars}")


def cmd_filters(storage: Storage, args):
    conn = sqlite3.connect(storage.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM filters_log ORDER BY filtered_at DESC LIMIT ?",
        (args.limit,),
    ).fetchall()
    conn.close()
    if not rows:
        print("无过滤记录")
        return
    print(f"\n共过滤了 {len(rows)} 个仓库:\n")
    for row in rows:
        print(f"  ✗ {row['full_name']} — {row['reason']} ({row['filtered_at']})")


def cmd_export(storage: Storage, args):
    recs = storage.get_recommendations()
    if not recs:
        print("没有推荐结果，请先运行 recommend")
        return

    if args.format == "json":
        path = args.output or "recommendations.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recs, f, indent=2, ensure_ascii=False)
        print(f"已导出 {len(recs)} 条到 {path}")

    elif args.format == "markdown":
        path = args.output or "recommendations.md"
        lines = [
            f"# 为你推荐的 {len(recs)} 个仓库",
            "",
            "| # | 仓库 | 语言 | ★ | 推荐原因 |",
            "|---|------|------|---|----------|",
        ]
        for i, rec in enumerate(recs, 1):
            stars = rec.get("stargazers_count", 0)
            lang = rec.get("language") or "N/A"
            reasons = " · ".join(rec.get("reasons", [])[:2])
            url = rec.get("html_url") or f"https://github.com/{rec['full_name']}"
            lines.append(f"| {i} | [{rec['full_name']}]({url}) | {lang} | {stars} | {reasons} |")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"已导出 {len(recs)} 条到 {path}")

    elif args.format == "csv":
        path = args.output or "recommendations.csv"
        import csv
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["#", "full_name", "language", "stars", "url", "reasons"])
            for i, rec in enumerate(recs, 1):
                writer.writerow([
                    i,
                    rec["full_name"],
                    rec.get("language") or "",
                    rec.get("stargazers_count", 0),
                    rec.get("html_url") or f"https://github.com/{rec['full_name']}",
                    " | ".join(rec.get("reasons", [])),
                ])
        print(f"已导出 {len(recs)} 条到 {path}")


def cmd_init(args):
    src = os.path.join(os.path.dirname(__file__), "config.example.json")
    if os.path.exists(src):
        with open(src) as f:
            config = json.load(f)
        save_config(config, args.config)
        print(f"已生成配置文件: {args.config}")
        print("请编辑配置文件填入 github_token 和 username")
    else:
        print("未找到 config.example.json")


def main():
    parser = argparse.ArgumentParser(
        description="GitHub 推荐引擎 — 基于 Star 历史的个性化项目推荐",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"github-rec {__version__}")
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="配置文件路径 (默认: config.json)",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="生成配置文件模板")
    p_init.add_argument("config", nargs="?", default="config.json")

    sub.add_parser("fetch", help="拉取 Star 列表")
    sub.add_parser("recommend", help="生成推荐")

    p_stars = sub.add_parser("stars", help="查看已缓存的 Star 列表")
    p_stars.add_argument("-n", "--limit", type=int, default=50)

    p_filters = sub.add_parser("filters", help="查看过滤记录")
    p_filters.add_argument("-n", "--limit", type=int, default=50)

    p_export = sub.add_parser("export", help="导出推荐结果到文件")
    p_export.add_argument("-f", "--format", choices=["json", "markdown", "csv"],
                          default="markdown", help="输出格式 (默认: markdown)")
    p_export.add_argument("-o", "--output", help="输出文件路径")

    args = parser.parse_args()

    if args.cmd == "init":
        cmd_init(args)
        return

    if not os.path.exists(args.config):
        print(f"配置文件不存在: {args.config}")
        print("请先运行: python recommend.py init")
        sys.exit(1)

    cfg = load_config(args.config)
    if not cfg.get("github_token") or not cfg.get("username"):
        print("请先编辑 config.json 填入 github_token 和 username")
        sys.exit(1)

    db_path = cfg.get("db_path", "./data/stars.db")
    storage = Storage(db_path)

    if args.cmd == "stars":
        cmd_list_stars(storage, args)
    elif args.cmd == "filters":
        cmd_filters(storage, args)
    elif args.cmd == "export":
        cmd_export(storage, args)
    else:
        client = GitHubRecommender(cfg, storage)
        if args.cmd == "fetch":
            cmd_fetch(client, args)
        elif args.cmd == "recommend":
            cmd_recommend(client, args)


if __name__ == "__main__":
    main()
