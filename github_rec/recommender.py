"""
GitHub 推荐引擎
核心原则：基于功能/用途匹配，而非语言匹配
"""

import json
import re
import time
from collections import Counter

from .client import GitHubClient
from .filters import RepoFilter
from .semantic import FuzzyMatcher, build_repo_profile
from .storage import Storage


def extract_keywords(text: str) -> set:
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    stop_words = {
        "this", "that", "with", "from", "have", "been", "were",
        "using", "based", "library", "tool", "framework", "system",
        "application", "project", "allows", "provides", "supports",
    }
    return {w for w in words if w not in stop_words}


class GitHubRecommender:
    def __init__(self, config: dict, storage: Storage):
        self.config = config
        self.storage = storage
        self.client = GitHubClient(config["github_token"])
        self.weights = config.get("weights", {})
        self.recent_days = config.get("recent_update_days", 90)
        self._filter = RepoFilter(
            exclude_topics=config.get("exclude_topics", []),
            exclude_languages=config.get("exclude_languages", []),
            min_stars=config.get("min_stars_threshold", 10),
            logger=None,
        )

    def fetch_stars(self) -> list:
        username = self.config["username"]
        max_count = self.config.get("max_stars_to_scan", 0)

        print(f"正在拉取 {username} 的 Star 记录...")
        repos = self.client.get_starred_repos(username, max_count=max_count)
        print(f"共获取 {len(repos)} 个 Star 仓库")

        existing = self.storage.get_repo_full_names()
        new_repos = [r for r in repos if r["full_name"] not in existing]

        if new_repos:
            self.storage.save_starred_repos(new_repos)
            print(f"新增 {len(new_repos)} 条记录")

        self.storage.set_meta("last_star_fetch", repos[0]["updated_at"] if repos else "")
        return repos

    def build_preference_profile(self, repos: list) -> dict:
        """
        构建偏好画像：统计高频功能领域和描述关键词
        不包含语言偏好
        """
        topic_counter = Counter()
        all_keywords = Counter()
        all_domains = Counter()

        for repo in repos:
            topics = repo.get("topics") or []
            topic_counter.update(topics)
            desc = repo.get("description") or ""
            all_keywords.update(extract_keywords(desc))

            # 也从描述中检测功能领域
            from .semantic import detect_domains
            domains = detect_domains(desc + " " + (repo.get("name") or ""))
            all_domains.update(domains)

        top_topics = [t for t, _ in topic_counter.most_common(30)]
        top_keywords = [k for k, _ in all_keywords.most_common(80)]
        top_domains = [d for d, _ in all_domains.most_common(15)]

        return {
            "topics": top_topics,
            "keywords": top_keywords,
            "domains": top_domains,
            "total": len(repos),
        }

    def generate_candidates(self, profile: dict, semantic_profiles: list) -> list:
        """
        纯功能描述匹配：只用语义策略，不按语言搜索
        """
        starred = self.storage.get_repo_full_names()

        fuzzy = FuzzyMatcher(self.client)
        print("\n正在通过功能描述模糊匹配候选仓库...")
        candidates = fuzzy.find_candidates(
            semantic_profiles,
            starred,
            limit=200,
        )

        print(f"\n共生成 {len(candidates)} 个候选仓库")
        return candidates

    def score_repo(self, repo: dict, profile: dict) -> tuple[float, list]:
        """
        纯功能评分：无语言权重
        - 功能领域重叠
        - 描述关键词重叠
        - Topic 重叠
        - 有 README
        - 最近更新
        - 高 Star 加成
        """
        score = 0.0
        reasons = []
        w = self.weights

        repo_desc = (repo.get("description") or "").lower()
        repo_name = (repo.get("name") or "").lower()
        repo_text = f"{repo_name} {repo_desc}"
        from .semantic import detect_domains as detect_repo_domains
        repo_domains = detect_repo_domains(repo_text)

        # 功能领域重叠（最核心的信号）
        overlap_domains = set(repo_domains) & set(profile["domains"])
        if overlap_domains:
            bonus = len(overlap_domains) * w.get("topic_overlap", 3)
            score += bonus
            reasons.append(f"同功能领域: {', '.join(list(overlap_domains)[:3])}")

        # Topic 重叠
        repo_topics = set(t.lower() for t in (repo.get("topics") or []))
        overlap_topics = repo_topics & set(profile["topics"])
        if overlap_topics:
            bonus = len(overlap_topics) * w.get("topic_overlap", 2)
            score += bonus
            reasons.append(f"共同主题: {', '.join(list(overlap_topics)[:3])}")

        # 描述关键词重叠
        repo_keywords = extract_keywords(repo.get("description") or "")
        kw_overlap = repo_keywords & set(profile["keywords"])
        if kw_overlap:
            bonus = len(kw_overlap) * w.get("keyword_match", 1)
            score += bonus
            reasons.append(f"功能相关: {', '.join(list(kw_overlap)[:5])}")

        # 来自哪个匹配短语
        matched_phrase = repo.get("_matched_phrase")
        if matched_phrase:
            reasons.append(f"匹配词: {matched_phrase}")

        # 有 README
        if repo.get("has_wiki", True):
            score += w.get("has_readme", 1)

        # 最近更新
        if self._filter.is_recent(repo):
            score += w.get("recent_update", 2)
            reasons.append("最近三个月有更新")

        # Star 数加成（社区认可度）
        stars = repo.get("stargazers_count", 0)
        if stars > 5000:
            score += 5
        elif stars > 1000:
            score += 3
        elif stars > 500:
            score += 1

        return score, reasons

    def recommend(self) -> list:
        starred = self.storage.get_starred_repos()
        if not starred:
            print("本地无 Star 数据，请先运行 fetch")
            return []

        print(f"加载了 {len(starred)} 个已 Star 仓库\n")

        # 基础偏好画像
        profile = self.build_preference_profile(starred)
        print(f"偏好领域: {', '.join(profile['domains'][:6])}")
        print(f"偏好主题: {', '.join(profile['topics'][:6])}")

        # 为每个 Star 仓库构建语义画像
        print("\n构建语义画像（分析功能用途）...")
        semantic_profiles = [build_repo_profile(r) for r in starred]

        # 统计高频领域
        domain_counter = Counter()
        for p in semantic_profiles:
            domain_counter.update(p["domains"])
        if domain_counter:
            top_domains = domain_counter.most_common(10)
            print(f"识别功能领域分布:")
            for d, c in top_domains:
                print(f"  {d}: {c} 个项目")

        # 生成候选
        candidates = self.generate_candidates(profile, semantic_profiles)

        # 过滤
        candidates, filtered = self._filter.filter_repos(candidates)
        for name, reason in filtered:
            self.storage.log_filter(name, reason)

        print(f"过滤后剩余 {len(candidates)} 个候选，开始评分...")

        # 去重
        seen_ids = set()
        unique = []
        for repo in candidates:
            fn = repo["full_name"]
            if fn not in seen_ids:
                seen_ids.add(fn)
                unique.append(repo)
        candidates = unique

        # 评分
        scored = []
        for repo in candidates:
            score, reasons = self.score_repo(repo, profile)
            repo["score"] = score
            repo["reasons"] = reasons
            scored.append(repo)

        scored.sort(key=lambda r: r["score"], reverse=True)

        max_recs = self.config.get("max_recommendations", 50)
        top = scored[:max_recs]

        self.storage.save_recommendations(top)
        return top
