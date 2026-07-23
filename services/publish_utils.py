import asyncio
import re
import os
import threading
import webbrowser
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse


def classify_publish_error(status_code: Optional[int] = None, message: str = "") -> Dict[str, Any]:
    msg = (message or "").lower()
    if any(token in msg for token in ["image upload", "media", "thumbnail", "attachment", "source_url", "cdn"]):
        return {"error_type": "image_upload", "retryable": True}
    if any(token in msg for token in ["html", "sanitize", "invalid content", "malformed", "script tag"]):
        return {"error_type": "html_invalid", "retryable": False}
    if status_code in (401, 403) or any(token in msg for token in ["auth", "token", "unauthorized", "forbidden", "permission"]):
        return {"error_type": "auth", "retryable": False}
    if status_code == 429 or "rate limit" in msg or "quota" in msg or "resource has been exhausted" in msg:
        return {"error_type": "rate_limit", "retryable": True}
    if status_code == 400:
        return {"error_type": "validation", "retryable": False}
    if status_code and 500 <= status_code < 600:
        return {"error_type": "upstream", "retryable": True}
    if any(token in msg for token in ["timeout", "network", "connection", "temporarily"]):
        return {"error_type": "network", "retryable": True}
    return {"error_type": "unknown", "retryable": False}


def normalize_publish_result(platform: str, result: Optional[dict]) -> dict:
    normalized = dict(result or {})
    normalized["platform"] = platform
    if normalized.get("status") == "ok":
        normalized.setdefault("error_type", None)
        normalized.setdefault("retryable", False)
        return normalized

    message = str(normalized.get("error") or normalized.get("message") or "")
    classified = classify_publish_error(normalized.get("status_code"), message)
    normalized.setdefault("error_type", classified["error_type"])
    normalized.setdefault("retryable", classified["retryable"])
    return normalized


def is_auto_open_enabled() -> bool:
    """Return whether successful published post URLs should open in a browser."""
    env_value = os.getenv("AUTO_OPEN_PUBLISHED_POSTS")
    if env_value is not None:
        return env_value.strip().lower() in ("1", "true", "yes", "on")

    try:
        import database as db
        value = db.get_global_setting("auto_open_published_posts", "true")
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return True


def _iter_publish_results(results: Any) -> Iterable[dict]:
    if isinstance(results, dict):
        if "status" in results and ("url" in results or "results" not in results):
            yield results
        nested = results.get("results")
        if nested is not None:
            yield from _iter_publish_results(nested)
            return
        for value in results.values():
            yield from _iter_publish_results(value)
    elif isinstance(results, list):
        for item in results:
            yield from _iter_publish_results(item)


def collect_published_urls(results: Any) -> List[str]:
    """Collect unique successful http(s) post URLs from nested publish results."""
    urls = []
    seen = set()
    for result in _iter_publish_results(results):
        if result.get("status") != "ok":
            continue
        url = str(result.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def open_published_urls(results: Any, context: str = "publish") -> List[str]:
    """Open successful published URLs in the default browser, antigravity-style."""
    urls = collect_published_urls(results)
    if not urls or not is_auto_open_enabled():
        return urls

    def _open_all():
        for url in urls:
            try:
                print(f"[BrowserOpen:{context}] Opening published post: {url}")
                webbrowser.open(url, new=2)
            except Exception as e:
                print(f"[BrowserOpen:{context}] Failed to open {url}: {e}")

    threading.Thread(target=_open_all, daemon=True).start()
    return urls


def validate_blog_post_payload(title: str, content: str, platforms: List[str]) -> dict:
    errors = []
    warnings = []
    clean_title = (title or "").strip()
    clean_content = re.sub(r"<[^>]+>", " ", content or "")
    clean_content = re.sub(r"\s+", " ", clean_content).strip()

    if not clean_title:
        errors.append("title is required")
    elif len(clean_title) > 220:
        errors.append("title is too long (over 220 characters)")
    elif len(clean_title) > 180:
        warnings.append("title is longer than 180 characters")

    if len(clean_content) < 30:
        errors.append("content is too short")

    if not platforms:
        errors.append("at least one platform is required")

    if re.search(r"<img\b", content or "", re.IGNORECASE) and not re.search(r'<img\b[^>]+src=["\'][^"\']+["\']', content or "", re.IGNORECASE):
        errors.append("one or more image tags are missing src attributes")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_publish_html(content: str) -> dict:
    html = content or ""
    errors = []
    warnings = []

    if not html.strip():
        errors.append("html content is empty")
        return {"ok": False, "errors": errors, "warnings": warnings}

    disallowed_tags = ["script", "iframe", "object", "embed", "form"]
    for tag in disallowed_tags:
        if re.search(rf"<\s*{tag}\b", html, re.IGNORECASE):
            errors.append(f"disallowed html tag detected: <{tag}>")

    img_tags = re.findall(r"<img\b[^>]*>", html, re.IGNORECASE)
    for img in img_tags:
        src_match = re.search(r'src=["\']([^"\']+)["\']', img, re.IGNORECASE)
        if not src_match:
            errors.append("one or more image tags are missing src attributes")
            continue
        src = src_match.group(1).strip()
        if src.startswith("/output/"):
            warnings.append("local output image path found; ensure public upload before posting")
        elif not (src.startswith("http://") or src.startswith("https://") or src.startswith("/")):
            warnings.append(f"non-standard image src detected: {src[:50]}")

    clean_content = re.sub(r"<[^>]+>", " ", html)
    clean_content = re.sub(r"\s+", " ", clean_content).strip()
    if len(clean_content) < 30:
        errors.append("html content is too short")

    open_p = len(re.findall(r"<p\b", html, re.IGNORECASE))
    close_p = len(re.findall(r"</p>", html, re.IGNORECASE))
    if open_p != close_p:
        warnings.append("possible malformed html: <p> tags not balanced")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


async def run_with_backoff(
    operation: Callable[[], Awaitable[dict]],
    platform: str = "unknown",
    max_attempts: int = 3,
    base_delay: float = 0.8,
    factor: float = 2.0,
    max_delay: float = 8.0,
) -> dict:
    attempt = 0
    delay = base_delay
    last_result = {"status": "error", "error": "operation was not executed"}

    while attempt < max_attempts:
        attempt += 1
        try:
            result = await operation()
        except Exception as e:
            result = {"status": "error", "error": str(e)}

        normalized = normalize_publish_result(platform, result)
        normalized["attempt"] = attempt
        last_result = normalized

        if normalized.get("status") == "ok":
            return normalized
        if not normalized.get("retryable"):
            return normalized
        if attempt >= max_attempts:
            return normalized

        await asyncio.sleep(min(delay, max_delay))
        delay *= factor

    return last_result
