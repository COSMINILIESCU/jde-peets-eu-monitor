"""Polite HTTP fetcher: robots.txt, per-domain rate limiting, retries with backoff, timeouts.

All network access in the pipeline MUST go through Fetcher.
"""

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.common.config import settings


class RobotsDisallowed(Exception):
    pass


class FetchError(Exception):
    pass


class _Retryable(FetchError):
    pass


class Fetcher:
    def __init__(self) -> None:
        cfg = settings()["collection"]
        self.timeout = cfg["request_timeout_seconds"]
        self.delay = cfg["per_domain_delay_seconds"]
        self.respect_robots = cfg["respect_robots_txt"]
        self.session = requests.Session()
        self.session.headers["User-Agent"] = cfg["user_agent"]
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self.session.get(f"{urlparse(url).scheme}://{host}/robots.txt", timeout=self.timeout)
                if resp.status_code >= 400:
                    self._robots[host] = None  # no robots.txt -> allowed
                else:
                    rp.parse(resp.text.splitlines())
                    self._robots[host] = rp
            except requests.RequestException:
                self._robots[host] = None
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        rp = self._robots_for(url)
        return True if rp is None else rp.can_fetch(self.session.headers["User-Agent"], url)

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last_hit.get(host, 0.0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_hit[host] = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_Retryable),
        reraise=True,
    )
    def get(self, url: str, conditional: dict | None = None) -> requests.Response:
        """GET with politeness. `conditional` may carry {'etag':..., 'last_modified':...}."""
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        self._throttle(url)
        headers = {}
        if conditional:
            if conditional.get("etag"):
                headers["If-None-Match"] = conditional["etag"]
            if conditional.get("last_modified"):
                headers["If-Modified-Since"] = conditional["last_modified"]
        try:
            resp = self.session.get(url, timeout=self.timeout, headers=headers)
        except requests.RequestException as exc:
            raise _Retryable(f"{url}: {exc}") from exc
        if resp.status_code in (429, 500, 502, 503, 504):
            raise _Retryable(f"{url}: HTTP {resp.status_code}")
        if resp.status_code >= 400 and resp.status_code != 304:
            raise FetchError(f"{url}: HTTP {resp.status_code}")
        return resp
