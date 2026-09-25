"""HTTP downloads with retries, atomic writes, and content hashes for the manifest."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

USER_AGENT = "LLMuni-benchmark/0.1"
PROVENANCE_KEYS = ("url", "sha256", "bytes", "downloaded_at", "http_last_modified")


def fetch(url: str, dest: Path, previous: dict | None, refresh: bool) -> dict:
    """Download url to dest unless the manifest already records this exact file from this url;
    return its provenance record."""
    cached = previous and previous.get("url") == url and dest.exists() and previous.get("sha256") == sha256_file(dest)
    if cached and not refresh:
        log.info("using cached %s", dest.name)
        return {k: previous.get(k) for k in PROVENANCE_KEYS}
    return download(url, dest)


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, max=30),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
def download(url: str, dest: Path) -> dict:
    """Stream url to dest atomically, hashing on the way."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    log.info("downloading %s", url)
    timeout = httpx.Timeout(60.0, read=300.0)
    with httpx.stream("GET", url, follow_redirects=True, headers={"User-Agent": USER_AGENT}, timeout=timeout) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                digest.update(chunk)
        last_modified = r.headers.get("last-modified")
    part.replace(dest)
    return {
        "url": url,
        "sha256": digest.hexdigest(),
        "bytes": dest.stat().st_size,
        "downloaded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "http_last_modified": last_modified,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
