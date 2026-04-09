from datetime import datetime, timedelta
from typing import Optional


class RepoFilter:
    def __init__(
        self,
        exclude_topics: list = None,
        exclude_languages: list = None,
        min_stars: int = 10,
        min_size: int = 1,
        recent_days: int = 90,
        logger=None,
    ):
        self.exclude_topics = set(exclude_topics or [])
        self.exclude_languages = set(exclude_languages or [])
        self.min_stars = min_stars
        self.min_size = min_size
        self.recent_days = recent_days
        self.logger = logger

    def should_exclude(self, repo: dict) -> Optional[str]:
        name = repo.get("full_name", "")

        # 空仓库
        if repo.get("size", 0) < self.min_size:
            return "empty_repo"

        # 归档仓库
        if repo.get("archived", False):
            return "archived"

        # Star 数太少
        stars = repo.get("stargazers_count", repo.get("stars", 0))
        if stars < self.min_stars:
            return f"low_stars({stars})"

        # 排除语言
        lang = repo.get("language")
        if lang and lang in self.exclude_languages:
            return f"excluded_language({lang})"

        # 排除主题
        topics = repo.get("topics") or []
        excluded = self.exclude_topics & set(topics)
        if excluded:
            return f"excluded_topic({excluded})"

        return None

    def is_recent(self, repo: dict) -> bool:
        pushed = repo.get("pushed_at")
        if not pushed:
            return False
        try:
            dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            return dt > datetime.now(dt.tzinfo) - timedelta(days=self.recent_days)
        except Exception:
            return False

    def filter_repos(self, repos: list) -> tuple[list, list]:
        kept = []
        filtered = []
        for repo in repos:
            reason = self.should_exclude(repo)
            if reason:
                filtered.append((repo.get("full_name"), reason))
                if self.logger:
                    self.logger.debug(f"排除 {repo.get('full_name')}: {reason}")
            else:
                kept.append(repo)
        return kept, filtered
