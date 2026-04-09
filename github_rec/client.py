import time
import requests

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({**HEADERS, "Authorization": f"Bearer {token}"})

    def _get(self, url: str, params=None):
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    def _paginate(self, url: str, params=None, per_page=100):
        params = params or {}
        params["per_page"] = per_page
        page = 1
        while True:
            params["page"] = page
            resp = self._get(url, params)
            data = resp.json()
            if not data:
                break
            yield from data
            if len(data) < per_page:
                break
            page += 1
            time.sleep(0.5)

    def get_starred_repos(self, username: str, max_count: int = 0):
        url = f"https://api.github.com/users/{username}/starred"
        repos = []
        for repo in self._paginate(url, {"sort": "updated", "direction": "desc"}):
            repos.append(repo)
            if max_count > 0 and len(repos) >= max_count:
                break
        return repos

    def get_repo_details(self, owner: str, repo: str) -> dict:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = self._get(url)
        return resp.json()

    def get_repo_topics(self, owner: str, repo: str) -> list:
        url = f"https://api.github.com/repos/{owner}/{repo}/topics"
        resp = self._get(url)
        data = resp.json()
        return data.get("names", [])

    def get_similar_repos(self, owner: str, repo: str) -> list:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_data = self._get(url).json()
        return repo_data.get("related", [])

    def search_repos(self, query: str, sort="stars", per_page=30) -> list:
        url = "https://api.github.com/search/repositories"
        resp = self._get(url, {"q": query, "sort": sort, "per_page": per_page})
        return resp.json().get("items", [])
