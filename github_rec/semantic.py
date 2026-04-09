"""
模糊匹配候选生成器
核心：基于功能描述（做什么）匹配，而非语言（用什么写）
"""

import re
import time
import urllib3
import requests
from collections import Counter

from .client import GitHubClient


# 功能领域定义：关键词 → 领域名
# 用于识别 Star 仓库的功能属性
DOMAIN_KEYWORDS = {
    "web_api":         ["web api", "rest api", "http server", "http client", "graphql", "gRPC", "router", "middleware", "endpoint", "openapi", "swagger", "api gateway"],
    "database":        ["database", "db", "sql", "nosql", "postgres", "mysql", "redis", "mongodb", "sqlite", "orm", "migration", "schema", "data store"],
    "cli":             ["cli", "command line", "terminal", "tool", "utility", "command", "argparse", "flags", "shell"],
    "machine_learning":["machine learning", "deep learning", "neural network", "tensorflow", "pytorch", "llm", "gpt", "model training", "inference", "data science", "nlp", "cv"],
    "devops":          ["docker", "kubernetes", "k8s", "deploy", "ci cd", "pipeline", "helm", "terraform", "ansible", "container", "orchestration"],
    "crypto":          ["crypto", "encryption", "hash", "signature", "wallet", "blockchain", "defi", "web3", "solidity", "cryptography"],
    "image_video":     ["image", "vision", "ocr", "video", "ffmpeg", "media", "thumbnail", "resize", "compress", "encode", "decode"],
    "network":         ["proxy", "tunnel", "vpn", "tcp", "udp", "socket", "quic", "http3", "proxy server", "reverse proxy", "load balancer", "cdn"],
    "gui":             ["gui", "desktop", "electron", "gtk", "qt", "wxwidgets", "ui framework", "widget"],
    "async":           ["async", "concurrency", "actor", "channel", "coroutine", "event loop", "futures", "parallel", "thread pool"],
    "serialization":   ["json", "xml", "yaml", "toml", "protobuf", "avro", "msgpack", "serialize", "encode", "decode"],
    "testing":         ["testing", "test", "mock", "fixture", "coverage", "benchmark", "fuzz", "assertion"],
    "auth":            ["auth", "oauth", "jwt", "sso", "rbac", "permission", "login", "session", "password", "2fa", "mfa"],
    "logging":         ["logging", "tracing", "metrics", "observability", "prometheus", "grafana", "dashboard", "alerting", "opentelemetry"],
    "parser":          ["parser", "lexer", "ast", "compiler", "interpreter", "grammar", "regex", "template", "templating"],
    "queue":           ["queue", "message", "broker", "pubsub", "kafka", "rabbitmq", "nats", "zmq", "event bus"],
    "cache":           ["cache", "lru", "ttl", "memcached", "hot data", "session store"],
    "config":          ["config", "env", "settings", "feature flag", "flags", "options", "configuration"],
    "sdk":             ["sdk", "client library", "official client", "api client", "bindings"],
    "kubernetes":      ["kubernetes", "k8s", "operator", "helm chart", "ingress", "service mesh", "istio", "prometheus operator"],
    "distributed":     ["distributed", "consensus", "raft", "paxos", "consistency", "replication", "sharding", "partition"],
    "realtime":        ["realtime", "websocket", "live", "streaming", "server sent", " SSE ", "server-sent"],
    "auth_infra":      ["secret", "vault", "secrets manager", "key management", "certificate", "tls", "ssl", "pki"],
    "code_gen":        ["code generation", "codegen", "boilerplate", "scaffolding", "generator", "metaprogramming"],
    "data_pipeline":   ["pipeline", "etl", "dataflow", "stream processing", "flink", "spark", "airflow", "dag"],
}


def detect_domains(text: str) -> list[str]:
    """从文本中识别项目所属的功能领域"""
    text_lower = f" {text.lower()} "
    found = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score >= 1:
            found.append(domain)
    return found


# 项目命名模式（提取功能类型）
NAME_FUNCTIONAL_PATTERNS = [
    (r"^awesome[-_](.+)$",      "awesome-list"),
    (r"^(\w+[-_]cli)$",         "cli-tool"),
    (r"^(\w+[-_]client)$",      "api-client"),
    (r"^(\w+[-_]server)$",      "server"),
    (r"^(\w+[-_]proxy)$",       "proxy"),
    (r"^(\w+[-_]gateway)$",     "gateway"),
    (r"^(\w+[-_]agent)$",       "agent"),
    (r"^(\w+[-_]runner)$",      "runner"),
    (r"^(\w+[-_]worker)$",      "worker"),
    (r"^(\w+[-_]exporter)$",    "exporter"),
    (r"^(\w+[-_]sdk)$",         "sdk"),
    (r"^(\w+[-_]sdk[-_])",      "sdk"),
    (r"^(\w+[-_]operator)$",    "k8s-operator"),
    (r"^(\w+[-_]sidecar)$",     "sidecar"),
    (r"^(\w+[-_]proxy)$",       "proxy"),
    (r"^(\w+[-_]cache)$",       "cache"),
    (r"^(\w+[-_]queue)$",       "queue"),
    (r"^(\w+[-_]stream)$",      "stream"),
    (r"^(\w+[-_]bridge)$",      "bridge"),
    (r"^(\w+[-_]adapter)$",    "adapter"),
    (r"^(\w+[-_]wrapper)$",     "wrapper"),
]


def extract_functional_type(name: str) -> str | None:
    """从仓库名中提取功能类型"""
    name_lower = name.lower()
    for pattern, ftype in NAME_FUNCTIONAL_PATTERNS:
        if re.match(pattern, name_lower):
            return ftype
    return None


def extract_core_phrases(text: str) -> list[str]:
    """
    只提取预定义的固定专业搭配，不做 n-gram 自动提取（n-gram 噪音太多）
    """
    if not text:
        return []
    text_lower = f" {text.lower()} "

    COMBO_PHRASES = [
        "api gateway", "web api", "rest api", "graphql api",
        "command line", "cli tool", "terminal emulator",
        "machine learning", "deep learning", "neural network",
        "data pipeline", "stream processing", "batch processing",
        "message queue", "event driven", "pub sub",
        "service mesh", "load balancer",
        "secret manager", "config management", "feature flag",
        "code generation", "boilerplate", "scaffolding",
        "rate limiting", "circuit breaker",
        "fault tolerance", "retry policy", "dead letter",
        "real time", "realtime", "server sent events", "websocket",
        "container orchestration", "ci cd pipeline", "gitops",
        "distributed tracing", "metrics collection", "log aggregation",
        "auth server", "token issuer", "session store",
        "job scheduler", "workflow engine",
        "data serialization", "schema evolution", "api versioning",
        "request validation", "response caching", "query builder",
        "connection pool", "hot reload", "live reload",
        "plugin system", "middleware chain",
        "rule engine", "template engine",
        "object detection", "image segmentation", "speech recognition",
        "natural language", "text generation", "llm inference",
        "code editor", "syntax highlight", "autocomplete",
        "cross platform", "native app", "desktop app", "mobile app",
        "database migration", "data sync", "data export", "data import",
        "http client", "http server", "tcp proxy", "reverse proxy",
        "background job", "task queue", "cron job", "scheduler",
        "image generation", "video generation", "voice clone", "speech synthesis",
        "text to speech", "speech to text", "audio processing",
        "video editing", "media processing", "image editing",
        "file transfer", "file sync", "cloud storage",
        "api client", "http framework", "web framework",
        "code review", "static analysis", "linter", "formatter",
        "test framework", "test runner", "mock library",
        "key value store", "document database", "time series",
        "container runtime", "serverless", "edge computing",
    ]

    return [p for p in COMBO_PHRASES if p in text_lower]


def build_repo_profile(repo: dict) -> dict:
    """
    为单个仓库构建语义画像
    只关注功能/用途，不关注语言
    """
    desc = repo.get("description") or ""
    name = repo.get("name", "")
    topics = [t.lower() for t in (repo.get("topics") or [])]
    text = f"{name} {desc} {' '.join(topics)}"

    domains = detect_domains(text)
    phrases = extract_core_phrases(text)
    func_type = extract_functional_type(name)

    return {
        "full_name": repo.get("full_name"),
        "name": name.lower(),
        "domains": domains,
        "phrases": phrases,
        "func_type": func_type,
        "topics": topics,
        "description": desc,
        "stars": repo.get("stargazers_count", repo.get("stars", 0)),
    }


STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "your", "their",
    "also", "into", "more", "than", "used", "using", "allows", "provide",
    "provides", "support", "supports", "enable", "enables", "make", "makes",
    "help", "helps", "build", "built", "create", "created", "simple", "easy",
    "fast", "lightweight", "powerful", "modern", "open source", "written",
    "github", "library", "framework", "tool", "system", "application",
}


class FuzzyMatcher:
    """
    纯功能描述匹配：只看"做什么"，不看"用什么写"
    """

    def __init__(self, client: GitHubClient):
        self.client = client

    def _retry_search(self, query: str, per_page: int = 25) -> list:
        """带重试的搜索，最多重试3次"""
        import urllib3
        for attempt in range(3):
            try:
                return self.client.search_repos(query, sort="stars", per_page=per_page)
            except (
                urllib3.exceptions.HTTPError,
                requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
            ) as e:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    print(f"    重试中 ({attempt+1}/3)，等待 {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"    搜索失败: {e}")
                    return []
        return []

    def _search_by_phrases(self, phrases: list, seen: set, starred: set,
                           min_stars: int = 30, limit: int = 100) -> list:
        """
        用功能短语搜索同类项目
        搜索时不限制语言，以找到所有语言的同类项目
        """
        candidates = []
        tried_phrases = 0

        for phrase in phrases:
            if tried_phrases >= 15:
                break
            tried_phrases += 1

            # 搜索：功能短语 + 排除已 star + 排除 fork + 最小 star
            query = f'"{phrase}" in:description stars:>{min_stars} fork:no'
            results = self._retry_search(query)
            for r in results:
                fn = r["full_name"]
                if fn not in starred and fn not in seen:
                    r["_matched_phrase"] = phrase
                    candidates.append(r)
                    seen.add(fn)
            time.sleep(7)
            if len(candidates) >= limit:
                break

        return candidates

    def _search_by_domain(self, domains: list, seen: set, starred: set,
                          limit: int = 40) -> list:
        """用功能领域搜索"""
        candidates = []
        for domain in domains[:8]:
            if len(candidates) >= limit:
                break
            query = f'"{domain}" in:description stars:>20 fork:no'
            results = self._retry_search(query, per_page=20)
            for r in results:
                fn = r["full_name"]
                if fn not in starred and fn not in seen:
                    r["_matched_phrase"] = f"领域:{domain}"
                    candidates.append(r)
                    seen.add(fn)
            time.sleep(7)
        return candidates

    def _search_by_name_pattern(self, profiles: list, seen: set,
                                 starred: set, limit: int = 30) -> list:
        """
        找同功能模式但不同实现的项目
        Star 了 xxx-gateway → 找其他 gateway 类项目
        """
        candidates = []

        # 收集所有功能类型
        func_types = [p["func_type"] for p in profiles if p["func_type"]]
        if not func_types:
            return candidates

        for ftype in list(set(func_types))[:5]:
            if len(candidates) >= limit:
                break
            query = f"{ftype} stars:>50 fork:no"
            try:
                results = self.client.search_repos(query, sort="stars", per_page=15)
                for r in results:
                    fn = r["full_name"]
                    if fn not in starred and fn not in seen:
                        r["_matched_phrase"] = f"模式:{ftype}"
                        candidates.append(r)
                        seen.add(fn)
                time.sleep(1)
            except Exception:
                pass

        return candidates

    def find_candidates(self, profiles: list, starred: set,
                         limit: int = 200) -> list:
        """
        模糊匹配入口：综合多种策略生成候选
        核心原则：不按语言过滤，找到所有语言的同类项目
        """
        # 合并所有短语
        all_phrases = []
        phrase_counter = Counter()
        for p in profiles:
            for ph in p["phrases"]:
                phrase_counter[ph] += 1

        # 按出现频次排序：越多 Star 仓库包含的短语越优先
        sorted_phrases = [ph for ph, _ in phrase_counter.most_common(40)]
        all_domains = set()
        for p in profiles:
            all_domains.update(p["domains"])

        print(f"    功能短语: {', '.join(sorted_phrases[:10])}")
        if all_domains:
            print(f"    功能领域: {', '.join(list(all_domains)[:8])}")

        candidates = []
        seen = set()

        # 策略1: 功能短语搜索（主要策略）
        phrase_candidates = self._search_by_phrases(
            sorted_phrases, seen, starred, limit=limit
        )
        candidates.extend(phrase_candidates)
        print(f"    短语搜索: +{len(phrase_candidates)} 个候选")

        # 策略2: 功能领域搜索
        domain_candidates = self._search_by_domain(
            list(all_domains), seen, starred, limit=40
        )
        candidates.extend(domain_candidates)
        print(f"    领域搜索: +{len(domain_candidates)} 个候选")

        # 策略3: 功能模式搜索
        pattern_candidates = self._search_by_name_pattern(
            profiles, seen, starred, limit=30
        )
        candidates.extend(pattern_candidates)
        print(f"    模式搜索: +{len(pattern_candidates)} 个候选")

        # 去重
        seen_ids = {}
        unique = []
        for r in candidates:
            fn = r["full_name"]
            if fn not in seen_ids:
                seen_ids[fn] = r["_matched_phrase"]
                unique.append(r)

        return unique[:limit]
