"""
模糊匹配候选生成器
核心：基于功能描述（做什么）匹配，而非语言（用什么写）
"""

import re
import time
from collections import Counter
from typing import Optional

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
    从文本中提取核心功能短语（用于搜索同类型项目）
    优先提取固定搭配，其次提取连续的实词组合
    """
    if not text:
        return []
    text_lower = text.lower()

    # 固定专业搭配（最有区分力）
    COMBO_PHRASES = [
        "api gateway", "web api", "rest api", "graphql api",
        "command line", "cli tool", "terminal emulator",
        "machine learning", "deep learning", "neural network",
        "data pipeline", "stream processing", "batch processing",
        "message queue", "event driven", "pub sub",
        "service mesh", "api gateway", "load balancer",
        "secret manager", "config management", "feature flag",
        "code generation", "boilerplate", "scaffolding",
        "rate limiting", "circuit breaker", "bulkhead",
        "fault tolerance", "retry policy", "dead letter",
        "real time", "realtime", "server sent events", "websocket",
        "container orchestration", "ci cd pipeline", "gitops",
        "distributed tracing", "metrics collection", "log aggregation",
        "auth server", "token issuer", "session store",
        "job scheduler", "cron replacement", "workflow engine",
        "data serialization", "schema evolution", "api versioning",
        "request validation", "response caching", "query builder",
        "connection pool", "retry logic", "timeout handling",
        "hot reload", "live reload", "watch mode",
        "plugin system", "extension framework", "middleware chain",
        "rule engine", "expression eval", "template engine",
    ]

    phrases = []
    for phrase in COMBO_PHRASES:
        if phrase in text_lower:
            phrases.append(phrase)

    # 提取 2-gram 名词短语（过滤掉通用词）
    STOP_NGRAMS = {
        "the", "and", "for", "with", "from", "that", "this",
        "using", "based", "fast", "simple", "easy", "lightweight",
        "powerful", "modern", "open source", "github",
    }
    words = re.findall(r"[a-z][a-z0-9-]{2,}", text_lower)
    for i in range(len(words) - 1):
        ngram = f"{words[i]} {words[i+1]}"
        if ngram not in STOP_NGRAMS and len(ngram) > 6:
            phrases.append(ngram)

    # 3-gram
    for i in range(len(words) - 2):
        ngram = f"{words[i]} {words[i+1]} {words[i+2]}"
        if ngram not in STOP_NGRAMS and len(ngram) > 8:
            phrases.append(ngram)

    return list(set(phrases))[:30]


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

    # 如果没有识别出领域，尝试从描述中再提取
    if not domains and desc:
        # 按空格切分，取 3-5 词的片段
        for size in [3, 4, 5]:
            words = re.findall(r"[a-z][a-z0-9]{2,}", desc.lower())
            for i in range(len(words) - size + 1):
                phrase = " ".join(words[i:i+size])
                if phrase not in STOPWORDS and len(phrase) > 8:
                    phrases.append(phrase)

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

    def _search_by_phrases(self, phrases: list, seen: set, starred: set,
                           min_stars: int = 30, limit: int = 100) -> list:
        """
        用功能短语搜索同类项目
        搜索时故意不带 language: 参数，以找到所有语言的同类项目
        """
        candidates = []
        tried_phrases = 0

        for phrase in phrases:
            if tried_phrases >= 20:
                break
            tried_phrases += 1

            # 搜索：功能短语 + 排除已 star + 排除 fork + 最小 star
            query = f'"{phrase}" in:description,readme stars:>{min_stars} NOT fork:true'
            try:
                results = self.client.search_repos(query, sort="stars", per_page=25)
                for r in results:
                    fn = r["full_name"]
                    if fn not in starred and fn not in seen:
                        # 记录这个项目是被哪个短语推荐来的
                        r["_matched_phrase"] = phrase
                        candidates.append(r)
                        seen.add(fn)
                time.sleep(1.2)
                if len(candidates) >= limit:
                    break
            except Exception as e:
                print(f"    搜索失败 '{phrase}': {e}")
                time.sleep(2)

        return candidates

    def _search_by_domain(self, domains: list, seen: set, starred: set,
                          limit: int = 40) -> list:
        """用功能领域搜索"""
        candidates = []
        for domain in domains[:8]:
            if len(candidates) >= limit:
                break
            # 用领域名作为搜索关键词
            query = f"{domain} stars:>20 NOT fork:true pushed:>2023-01-01"
            try:
                results = self.client.search_repos(query, sort="stars", per_page=20)
                for r in results:
                    fn = r["full_name"]
                    if fn not in starred and fn not in seen:
                        r["_matched_phrase"] = f"领域:{domain}"
                        candidates.append(r)
                        seen.add(fn)
                time.sleep(1)
            except Exception as e:
                print(f"    领域搜索失败 '{domain}': {e}")
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

        for ftype in set(func_types)[:5]:
            if len(candidates) >= limit:
                break
            query = f"{ftype} stars:>50 NOT fork:true"
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
