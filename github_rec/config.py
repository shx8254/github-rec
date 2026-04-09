import json
import os
from pathlib import Path


DEFAULT_CONFIG = {
    "github_token": "",
    "username": "",
    "db_path": "./data/stars.db",
    "max_recommendations": 50,
    "max_stars_to_scan": 500,
    "min_stars_threshold": 10,
    "exclude_topics": ["tutorial", "example", "demo", "learn", "course"],
    "exclude_languages": ["HTML", "CSS", "JavaScript", "Shell", "Makefile"],
    "weights": {
        "language_match": 5,
        "topic_overlap": 2,
        "keyword_match": 1,
        "has_readme": 1,
        "recent_update": 2,
    },
    "recent_update_days": 90,
}


def load_config(path: str = "config.json") -> dict:
    if not os.path.exists(path):
        return DEFAULT_CONFIG.copy()
    with open(path, "r", encoding="utf-8") as f:
        return {**DEFAULT_CONFIG, **json.load(f)}


def save_config(config: dict, path: str = "config.json"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
