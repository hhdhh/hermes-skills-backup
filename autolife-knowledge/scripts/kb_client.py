"""Shared client for the Autolife / AstrBot knowledge base API.

Standard library only — no third-party dependencies.

Responsibilities:
  * configuration from environment (with optional .env fallback)
  * JWT acquisition and on-disk caching (the token is valid for ~7 days)
  * HTTP calls with bounded retries
  * knowledge-base listing (paginated) and name -> id resolution
  * retrieval, de-duplication and text/JSON formatting
  * multipart document upload with progress polling
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from urllib.request import Request, urlopen

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BASE_URL = "http://100.98.150.220:6185"
# Public retrieval gateway. Reachable from anywhere (no NetBird needed) but
# requires an API token. Exposed by the roster app's /kb proxy route.
DEFAULT_PUBLIC_URL = "https://fae.gz.autolife.ai:8866/kb"
DEFAULT_USERNAME = "autolife"
DEFAULT_PASSWORD = "123455"
DEFAULT_KB_NAMES = "autolife知识库,autolife-docs"
DEFAULT_TOP_K = 5
DEFAULT_MAX_CHARS = 12000
DEFAULT_MAX_PER_DOC = 2
DEFAULT_TIMEOUT = 30
DEFAULT_UPLOAD_TIMEOUT = 900

TOKEN_REFRESH_SKEW = 300
MAX_FETCH_TOP_K = 50
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 1.5

_INSECURE_WARNED = False
_ENV_LOADED = False

# Suffixes that mark a near-duplicate copy of another document, e.g.
# "配置流程 副本.txt", "使用手册 (1).txt", "manual copy.md".
_COPY_SUFFIX = re.compile(
    r"(?:\s*[\(（\[【]\s*\d+\s*[\)）\]】]" r"|\s*[-_ ]?\s*(?:副本|拷贝|copy|backup))+$",
    re.IGNORECASE,
)

# Everything that is not a letter, digit or CJK character. Used to fold
# punctuation variants of the same document name onto one key.
_NON_WORD = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


class KbError(RuntimeError):
    """Raised for configuration, transport and protocol failures."""


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------


def load_dotenv(path: str | None = None) -> bool:
    """Load KEY=VALUE pairs from .env. Never overrides real environment vars."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return False
    _ENV_LOADED = True

    target = path or os.path.join(SKILL_ROOT, ".env")
    if not os.path.isfile(target):
        return False
    try:
        with open(target, encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return False
    return True


def _env_int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        print(
            f"[kb] 环境变量 {name}={raw!r} 不是整数，已回落到默认值 {default}",
            file=sys.stderr,
        )
        return default
    if value < minimum:
        print(
            f"[kb] 环境变量 {name}={value} 小于下限 {minimum}，已回落到默认值 {default}",
            file=sys.stderr,
        )
        return default
    if maximum is not None and value > maximum:
        print(
            f"[kb] 环境变量 {name}={value} 超过上限 {maximum}，已截断为 {maximum}",
            file=sys.stderr,
        )
        return maximum
    return value


class Config:
    """Resolved runtime configuration."""

    def __init__(
        self,
        base_url: str | None = None,
        kb_names: list[str] | None = None,
        public_url: str | None = None,
    ):
        load_dotenv()
        self.base_url = (base_url or os.environ.get("KB_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.username = os.environ.get("KB_USERNAME", DEFAULT_USERNAME)
        self.password = os.environ.get("KB_PASSWORD", DEFAULT_PASSWORD)
        self.kb_names = kb_names if kb_names is not None else split_kb_names(
            os.environ.get("KB_NAMES", DEFAULT_KB_NAMES)
        )
        self.top_k = _env_int("KB_TOP_K", DEFAULT_TOP_K, minimum=1, maximum=MAX_FETCH_TOP_K)
        self.max_chars = _env_int("KB_MAX_CHARS", DEFAULT_MAX_CHARS, minimum=0)
        self.max_per_doc = _env_int("KB_MAX_PER_DOC", DEFAULT_MAX_PER_DOC, minimum=0)
        self.timeout = _env_int("KB_TIMEOUT", DEFAULT_TIMEOUT, minimum=1)
        self.upload_timeout = _env_int("KB_UPLOAD_TIMEOUT", DEFAULT_UPLOAD_TIMEOUT, minimum=1)
        self.cache_tokens = os.environ.get("KB_CACHE_TOKEN", "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }
        self.public_url = (public_url or os.environ.get("KB_PUBLIC_URL") or DEFAULT_PUBLIC_URL).rstrip("/")
        self.api_token = (os.environ.get("KB_API_TOKEN") or "").strip()

    @property
    def mode(self) -> str:
        """``public`` when an API token is configured, else ``internal``.

        Public mode talks to the internet-facing /kb gateway and needs no
        NetBird; internal mode talks to the AstrBot API over the VPN.
        """
        return "public" if self.api_token else "internal"

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"Config(mode={self.mode!r}, base_url={self.base_url!r}, "
            f"public_url={self.public_url!r}, kb_names={self.kb_names!r}, "
            f"top_k={self.top_k})"
        )


def split_kb_names(raw: str) -> list[str]:
    """Split a comma-separated knowledge-base list, preserving order."""
    names, seen = [], set()
    for part in str(raw).split(","):
        name = part.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names or split_kb_names(DEFAULT_KB_NAMES)


def warn_if_insecure(base_url: str) -> bool:
    """Warn once per process when credentials travel over plain HTTP."""
    global _INSECURE_WARNED
    if _INSECURE_WARNED:
        return False
    if os.environ.get("KB_SUPPRESS_HTTP_WARNING", "").strip().lower() in {"1", "true", "yes"}:
        return False
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "http":
        return False
    if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return False
    _INSECURE_WARNED = True
    print(
        "[kb] 安全提示：KB_BASE_URL 为明文 HTTP，账号密码与 JWT 在链路上未加密"
        "（当前服务端未提供 HTTPS，如需消除此风险请为其配置 TLS）。",
        file=sys.stderr,
    )
    return True


# --------------------------------------------------------------------------
# token cache
# --------------------------------------------------------------------------


def _token_cache_path(base_url: str, username: str) -> str:
    digest = hashlib.sha256(f"{base_url}|{username}".encode("utf-8")).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), f"autolife-kb-token-{digest}.json")


def jwt_expiry(token: str) -> int | None:
    """Return the `exp` claim of a JWT, or None when it cannot be read."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (IndexError, ValueError, TypeError, UnicodeDecodeError):
        return None
    exp = claims.get("exp")
    try:
        return int(exp)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# client
# --------------------------------------------------------------------------


class KbClient:
    """Thin client over the AstrBot dashboard API."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self._token: str | None = None
        self._chunk_cache: dict[tuple, list[dict]] = {}
        warn_if_insecure(self.config.base_url)

    # -- transport ---------------------------------------------------------

    def _open(self, url: str, method: str = "GET", payload=None, headers=None, timeout=None):
        body = None
        hdrs = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        request = Request(url, data=body, headers=hdrs, method=method)
        return urlopen(request, timeout=timeout or self.config.timeout)

    def request_json(self, path: str, method: str = "GET", payload=None, token=None, retries=None):
        """Call an API path, retrying transient failures (5xx / network)."""
        url = path if path.startswith("http") else f"{self.config.base_url}{path}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        attempts = RETRY_ATTEMPTS if retries is None else max(1, retries)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                with self._open(url, method=method, payload=payload, headers=headers) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", "replace")[:300]
                except Exception:  # pragma: no cover - body already consumed
                    pass
                last_error = KbError(f"HTTP {exc.code} {exc.reason} {detail}".strip())
                if exc.code < 500 or attempt == attempts:
                    raise last_error from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = KbError(f"网络错误：{exc}")
                if attempt == attempts:
                    raise last_error from exc
            except json.JSONDecodeError as exc:
                last_error = KbError("服务端返回了非法 JSON")
                if attempt == attempts:
                    raise last_error from exc

            time.sleep(RETRY_BACKOFF * attempt)

        raise last_error or KbError("请求失败")

    # -- authentication ----------------------------------------------------

    def login(self, force: bool = False) -> str:
        """Return a JWT, reusing the on-disk cache while it is still valid."""
        if self._token and not force:
            return self._token

        path = _token_cache_path(self.config.base_url, self.config.username)
        if self.config.cache_tokens and not force:
            cached = self._read_cached_token(path)
            if cached:
                self._token = cached
                return cached

        result = self.request_json(
            "/api/auth/login",
            method="POST",
            payload={"username": self.config.username, "password": self.config.password},
        )
        token = ((result or {}).get("data") or {}).get("token")
        if not token:
            raise KbError("登录失败：响应中没有 token")

        self._token = token
        if self.config.cache_tokens:
            self._write_cached_token(path, token)
        return token

    def _read_cached_token(self, path: str) -> str | None:
        try:
            with open(path, encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            return None
        token = record.get("token")
        exp = record.get("exp")
        if not token:
            return None
        if isinstance(exp, (int, float)) and exp - TOKEN_REFRESH_SKEW <= time.time():
            return None
        return token

    def _write_cached_token(self, path: str, token: str) -> None:
        exp = jwt_expiry(token)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"token": token, "exp": exp}, handle)
            os.chmod(path, 0o600)
        except OSError:
            pass

    # -- knowledge bases ---------------------------------------------------

    def list_kbs(self, page_size: int = 50, max_pages: int = 20) -> list[dict]:
        """List every knowledge base, following the API's pagination."""
        token = self.login()
        items: list[dict] = []
        seen_ids = set()

        for page in range(1, max_pages + 1):
            result = self.request_json(
                f"/api/kb/list?page={page}&page_size={page_size}", token=token
            )
            data = (result or {}).get("data")
            if isinstance(data, list):
                batch = data
                total = None
            elif isinstance(data, dict):
                batch = data.get("items") or data.get("list") or []
                total = data.get("total")
            else:
                batch = []
                total = None

            if not isinstance(batch, list) or not batch:
                break

            fresh = 0
            for entry in batch:
                if not isinstance(entry, dict):
                    continue
                key = entry.get("kb_id") or entry.get("id") or entry.get("kb_name")
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                items.append(entry)
                fresh += 1

            if fresh == 0 or len(batch) < page_size:
                break
            if isinstance(total, int) and len(items) >= total:
                break

        return items

    def get_kb_id(self, kb_name: str) -> str:
        """Resolve a knowledge-base name to its id, with a helpful failure message."""
        items = self.list_kbs()
        for entry in items:
            if (entry.get("kb_name") or entry.get("name")) == kb_name:
                kb_id = entry.get("kb_id") or entry.get("id")
                if kb_id:
                    return str(kb_id)
        available = ", ".join(
            str(entry.get("kb_name") or entry.get("name")) for entry in items
        ) or "<无>"
        raise KbError(f"找不到知识库 {kb_name!r}。当前可用：{available}")

    def resolve_kb_names(self, names: list[str] | None = None) -> list[str]:
        """Drop unknown names with a warning so a typo degrades instead of failing."""
        wanted = list(names if names is not None else self.config.kb_names)
        try:
            known = {
                str(entry.get("kb_name") or entry.get("name"))
                for entry in self.list_kbs()
            }
        except KbError:
            return wanted

        valid = [name for name in wanted if name in known]
        for name in wanted:
            if name not in known:
                print(
                    f"[kb] 警告：知识库 {name!r} 不存在，已跳过。可用：{', '.join(sorted(known))}",
                    file=sys.stderr,
                )
        if not valid:
            raise KbError(
                f"指定的知识库均不存在：{', '.join(wanted)}。"
                f"当前可用：{', '.join(sorted(known)) or '<无>'}"
            )
        return valid

    # -- retrieval ---------------------------------------------------------

    def retrieve(self, query: str, kb_names: list[str] | None = None, top_k: int | None = None):
        """Fetch raw result chunks for a query."""
        token = self.login()
        result = self.request_json(
            "/api/kb/retrieve",
            method="POST",
            payload={
                "query": query,
                "kb_names": list(kb_names if kb_names is not None else self.config.kb_names),
                "top_k": int(top_k or self.config.top_k),
            },
            token=token,
        )
        data = (result or {}).get("data") or {}
        results = data.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]
        # The deployed service always returns `results`; `context_text` is a
        # legacy shape kept for compatibility but carries no source document
        # names, which the answering rules require.
        context = data.get("context_text")
        if context:
            print(
                "[kb] 警告：服务端只返回了 context_text，缺少来源文档名，无法引用出处。",
                file=sys.stderr,
            )
            return [{"doc_name": "unknown", "content": str(context), "score": 0.0}]
        return []

    def search(
        self,
        query: str,
        kb_names: list[str] | None = None,
        top_k: int | None = None,
        max_per_doc: int | None = None,
        dedupe: bool = True,
    ) -> list[dict]:
        """Retrieve, de-duplicate and trim to the requested number of chunks."""
        wanted = int(top_k or self.config.top_k)
        per_doc = self.config.max_per_doc if max_per_doc is None else max_per_doc
        over_fetch = min(max(wanted * 4, wanted), MAX_FETCH_TOP_K)

        raw = self.retrieve(query, kb_names=kb_names, top_k=over_fetch)
        if not dedupe:
            return raw[:wanted]
        return dedupe_results(raw, max_per_doc=per_doc)[:wanted]

    # -- context expansion -------------------------------------------------

    def chunks_of(self, kb_id: str, doc_id: str, page_size: int = 200, max_pages: int = 20) -> list[dict]:
        """Return every chunk of one document, ordered by chunk_index.

        The remote chunker produces a contiguous, non-overlapping partition, so
        concatenating these chunks in order reproduces the original document.
        """
        cache_key = (str(kb_id), str(doc_id))
        cached = self._chunk_cache.get(cache_key)
        if cached is not None:
            return cached

        token = self.login()
        items: list[dict] = []
        seen: set = set()
        for page in range(1, max_pages + 1):
            path = (
                f"/api/kb/chunk/list?kb_id={urllib.parse.quote(str(kb_id))}"
                f"&doc_id={urllib.parse.quote(str(doc_id))}"
                f"&page={page}&page_size={page_size}"
            )
            data = (self.request_json(path, token=token) or {}).get("data")
            if isinstance(data, dict):
                batch = data.get("items") or []
                total = data.get("total")
            elif isinstance(data, list):
                batch, total = data, None
            else:
                batch, total = [], None

            if not batch:
                break
            for chunk in batch:
                if not isinstance(chunk, dict):
                    continue
                key = chunk.get("chunk_id") or chunk.get("chunk_index")
                if key in seen:
                    continue
                seen.add(key)
                items.append(chunk)
            if len(batch) < page_size:
                break
            if isinstance(total, int) and len(items) >= total:
                break

        items.sort(key=lambda c: int(c.get("chunk_index") or 0))
        self._chunk_cache[cache_key] = items
        return items

    def expand_hits(
        self,
        results: list[dict],
        mode: str = "section",
        window: int = 1,
        max_chunks: int = 8,
        per_hit_chars: int = 0,
    ) -> list[dict]:
        """Widen each hit from a bare chunk to its surrounding context.

        A fixed-width chunker cuts ~91% of chunks mid-sentence, so the matched
        chunk alone often lacks the condition, heading or step it belongs to.
        Because the remote store keeps every chunk in order, the neighbours can
        be stitched back on without touching the original source.

        Modes:
          * ``none``    — leave the bare chunk untouched
          * ``window``  — take ``window`` chunks either side
          * ``section`` — take the enclosing section (nearest heading above to
                          the chunk before the next heading), falling back to a
                          symmetric window when that span is too wide
        """
        if mode in (None, "", "none"):
            return results

        expanded: list[dict] = []
        for item in results:
            kb_id, doc_id = item.get("kb_id"), item.get("doc_id")
            if not kb_id or not doc_id:
                expanded.append(item)
                continue
            try:
                chunks = self.chunks_of(kb_id, doc_id)
            except KbError:
                expanded.append(item)
                continue

            position = _locate_chunk(item, chunks)
            if position is None:
                expanded.append(item)
                continue

            if mode == "window":
                low = max(0, position - window)
                high = min(len(chunks) - 1, position + window)
            else:
                low, high = _section_bounds(chunks, position, max_chunks)

            before = "".join(str(c.get("content") or "") for c in chunks[low:position])
            hit_text = str(chunks[position].get("content") or "")
            after = "".join(str(c.get("content") or "") for c in chunks[position + 1:high + 1])

            before, hit_text, after = _trim_around_hit(before, hit_text, after, per_hit_chars)
            text = _assemble_hit(before, hit_text, after)

            widened = dict(item)
            widened["content"] = text
            widened["chunk_span"] = {
                "from": low,
                "to": high,
                "count": high - low + 1,
                "total_chunks": len(chunks),
                "hit_index": position,
                "mode": mode,
                "chars": len(text),
            }
            expanded.append(widened)

        return expanded

    # -- upload ------------------------------------------------------------

    def upload_document(self, file_path: str, kb_name: str, title: str | None = None) -> str:
        """Upload one document and return the background task id."""
        token = self.login()
        kb_id = self.get_kb_id(kb_name)
        filename = title or os.path.basename(file_path)
        with open(file_path, "rb") as handle:
            file_data = handle.read()

        boundary = f"----AutolifeKbBoundary{secrets.token_hex(16)}"
        body = _build_multipart(boundary, kb_id, filename, file_data)
        url = f"{self.config.base_url}/api/kb/document/upload"
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=max(self.config.timeout, 60)) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:  # pragma: no cover
                pass
            raise KbError(f"上传失败：HTTP {exc.code} {exc.reason} {detail}".strip()) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise KbError(f"上传失败：{exc}") from exc

        task_id = ((result or {}).get("data") or {}).get("task_id")
        if not task_id:
            raise KbError(f"上传接口未返回 task_id：{result}")
        return str(task_id)

    def wait_for_upload(
        self,
        task_id: str,
        timeout_seconds: int | None = None,
        interval: float = 2.0,
        on_progress=None,
    ) -> dict:
        """Poll until the background indexing task finishes."""
        token = self.login()
        deadline = time.time() + (timeout_seconds or self.config.upload_timeout)
        started = time.time()
        last: dict = {}

        while time.time() < deadline:
            result = self.request_json(
                f"/api/kb/document/upload/progress?task_id={urllib.parse.quote(task_id)}",
                token=token,
            )
            payload = (result or {}).get("data") or {}
            last = payload
            status = payload.get("status")

            if on_progress:
                on_progress(status, payload, time.time() - started)

            if status == "completed":
                outcome = payload.get("result") or {}
                if outcome.get("failed_count"):
                    raise KbError(f"部分文件处理失败：{outcome.get('failed')}")
                return outcome
            if status == "failed":
                raise KbError(payload.get("error") or "知识库处理失败")
            time.sleep(interval)

        raise KbError(f"上传任务 {task_id} 等待超时（{timeout_seconds or self.config.upload_timeout} 秒）")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _build_multipart(boundary: str, kb_id: str, filename: str, file_data: bytes) -> bytes:
    """Build a multipart body with a random boundary and RFC 5987 filename."""
    # The plain `filename` parameter must stay ASCII; the real UTF-8 name goes
    # into `filename*` so Chinese document titles survive the round trip.
    ascii_name = filename.encode("ascii", "ignore").decode("ascii").strip()
    ascii_name = ascii_name.replace('"', "").replace("\r", "").replace("\n", "")
    ascii_name = ascii_name or "document.md"
    encoded_name = urllib.parse.quote(filename, safe="")

    chunks = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="kb_id"\r\n\r\n'
            f"{kb_id}\r\n"
        ).encode("utf-8"),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{ascii_name}"; '
            f"filename*=UTF-8''{encoded_name}\r\n"
            f"Content-Type: text/markdown; charset=utf-8\r\n\r\n"
        ).encode("utf-8"),
        file_data,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(chunks)


def normalize_doc_name(name: str) -> str:
    """Reduce a document name to a comparison key for near-duplicate detection.

    The corpus stores the same document under several spellings — copy suffixes
    (`手册 副本`, `手册 (1)`) and punctuation drift (`手册（多图需修）` vs
    `手册_多图需修_`, `AI语音&导航` vs `AI语音_导航`). Copy suffixes are stripped
    first, then everything that is not a letter, digit or CJK character is
    removed, so all of those collapse to one key.
    """
    stem = os.path.splitext(str(name or ""))[0]
    previous = None
    while previous != stem:
        previous = stem
        stem = _COPY_SUFFIX.sub("", stem).strip()
    return _NON_WORD.sub("", stem.lower())


class PublicKbClient:
    """Retrieval client for the internet-facing ``/kb`` gateway.

    The gateway fronts the same corpus as the internal AstrBot API, so a token
    is all a customer needs — no NetBird tunnel, no AstrBot account. Only
    retrieval is exposed; the gateway returns sections that are already
    context-expanded, so de-duplication and expansion are not repeated here.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        if not self.config.api_token:
            raise KbError("未配置 KB_API_TOKEN，无法使用公网检索模式")
        warn_if_insecure(self.config.public_url)

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Return the top matches for ``query``, newest gateway shape."""
        wanted = max(1, min(int(top_k or self.config.top_k), MAX_FETCH_TOP_K))
        payload = json.dumps({"query": query, "top_k": wanted}).encode("utf-8")
        url = f"{self.config.public_url}?token={urllib.parse.quote(self.config.api_token)}"

        last_error: object = None
        body: dict = {}
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            request = Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.config.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    raise KbError("API 密钥无效或已被吊销（HTTP 401）") from exc
                if exc.code == 404:
                    raise KbError(
                        f"公网检索端点不存在（HTTP 404）：{self.config.public_url}"
                    ) from exc
                last_error = exc
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF ** attempt)
        else:
            raise KbError(f"公网检索失败：{last_error}")

        results: list[dict] = []
        for item in body.get("results") or []:
            if not isinstance(item, dict):
                continue
            try:
                score = float(item.get("score") or 0)
            except (TypeError, ValueError):
                score = 0.0
            results.append(
                {
                    "doc_name": item.get("doc_name") or "unknown",
                    "content": str(item.get("content") or ""),
                    "score": score,
                    "section": item.get("section") or "",
                    "matched_by": item.get("matched_by") or [],
                    "vector_score": item.get("vector_score"),
                    "keyword_score": item.get("keyword_score"),
                    "source": "public",
                }
            )
        return results

    def probe(self) -> dict:
        """Cheap call used by setup to prove the token works."""
        return {"results": self.search("ping", top_k=1)}


# Lines that plausibly open a new section: markdown headings, 第X章, 一、, 1.2),
# 【标题】, and bullet leaders. Used to find section boundaries when widening a
# hit. Deliberately loose — a bad guess only costs a slightly wider span.
_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s+\S"
    r"|第[一二三四五六七八九十百零两\d]+[章节篇部分]"
    r"|[一二三四五六七八九十]+[、.．)）]"
    r"|\d+(?:\.\d+)*[、.．)）]\s*"
    r"|【[^】\n]{1,24}】"
    r"|[◆●■★▲▶]\s*)"
)


def looks_like_heading(text: str) -> bool:
    """True when the first non-empty line of a chunk looks like a section start."""
    stripped = str(text or "").strip()
    if not stripped:
        return False
    first_line = stripped.splitlines()[0]
    return bool(_HEADING_RE.match(first_line))


def _locate_chunk(item: dict, chunks: list[dict]) -> int | None:
    """Find the position of a retrieval hit inside its document's chunk list."""
    chunk_id = item.get("chunk_id")
    if chunk_id:
        for index, chunk in enumerate(chunks):
            if chunk.get("chunk_id") == chunk_id:
                return index

    chunk_index = item.get("chunk_index")
    if chunk_index is not None:
        for index, chunk in enumerate(chunks):
            if str(chunk.get("chunk_index")) == str(chunk_index):
                return index

    probe = re.sub(r"\s+", " ", str(item.get("content") or "")).strip()[:60]
    if probe:
        for index, chunk in enumerate(chunks):
            haystack = re.sub(r"\s+", " ", str(chunk.get("content") or ""))
            if probe in haystack:
                return index
    return None


def _section_bounds(chunks: list[dict], position: int, max_chunks: int = 8) -> tuple[int, int]:
    """Span from the nearest heading above the hit to just before the next one."""
    low = position
    while low > 0 and not looks_like_heading(str(chunks[low].get("content") or "")):
        low -= 1
    high = position
    while high + 1 < len(chunks) and not looks_like_heading(str(chunks[high + 1].get("content") or "")):
        high += 1

    if max_chunks and high - low + 1 > max_chunks:
        # The document has no usable headings, or the section is huge: fall back
        # to a symmetric window so one hit cannot swallow the whole document.
        half = max_chunks // 2
        low = max(0, position - half)
        high = min(len(chunks) - 1, low + max_chunks - 1)
    return low, high


HIT_OPEN = "--- 命中片段开始 ---"
HIT_CLOSE = "--- 命中片段结束，以下为后文 ---"


def _trim_around_hit(before: str, hit: str, after: str, max_chars: int) -> tuple[str, str, str]:
    """Shrink the context but never the hit itself.

    A symmetric window buries the matched chunk in the middle of the payload,
    which is exactly where models attend least. Trimming keeps the hit whole and
    discards the context furthest from it, so the answer stays at the seam.
    """
    if max_chars <= 0 or len(before) + len(hit) + len(after) <= max_chars:
        return before, hit, after

    remaining = max_chars - len(hit)
    if remaining <= 0:
        return "", hit, ""

    before_budget = remaining // 2
    after_budget = remaining - before_budget
    kept_before = before[-before_budget:] if before_budget else ""
    kept_after = after[:after_budget] if after_budget else ""
    if len(kept_before) < len(before):
        kept_before = "…" + kept_before.lstrip()
    if len(kept_after) < len(after):
        kept_after = kept_after.rstrip() + "…"
    return kept_before, hit, kept_after


def _assemble_hit(before: str, hit: str, after: str) -> str:
    """Join context and hit, marking where the actual match sits."""
    if not before and not after:
        return hit.strip()
    segments = []
    if before.strip():
        segments.append(before.rstrip())
        segments.append(HIT_OPEN)
    segments.append(hit.strip())
    if after.strip():
        segments.append(HIT_CLOSE)
        segments.append(after.lstrip())
    return "\n".join(segments)


def _center_crop(text: str, max_chars: int) -> str:
    """Keep the head and tail of an oversized span, dropping the middle."""
    if len(text) <= max_chars:
        return text
    head = (max_chars * 2) // 3
    tail = max_chars - head
    omitted = len(text) - max_chars
    return (
        text[:head].rstrip()
        + f"\n\n[…中间省略 {omitted} 字符…]\n\n"
        + text[-tail:].lstrip()
    )


def dedupe_results(results: list[dict], max_per_doc: int = DEFAULT_MAX_PER_DOC) -> list[dict]:
    """Keep the best-scoring chunks, capping how many come from one document.

    The remote corpus stores many near-identical copies of the same document
    (each copy has its own doc_id and slightly different bytes), so the same
    logical chunk comes back several times. Three keys are collapsed:

      * identical normalized content
      * the same document name (copy suffixes stripped)
      * the same (document, chunk index) pair
    """
    ordered = sorted(results, key=lambda item: float(item.get("score") or 0), reverse=True)
    kept: list[dict] = []
    per_doc: dict[str, int] = {}
    seen_content: set[str] = set()
    seen_slots: set[tuple] = set()

    for item in ordered:
        content = re.sub(r"\s+", " ", str(item.get("content") or "")).strip()
        if content and content in seen_content:
            continue

        key = normalize_doc_name(item.get("doc_name"))
        chunk_index = item.get("chunk_index")
        slot = (key, chunk_index)
        if chunk_index is not None and slot in seen_slots:
            continue
        if max_per_doc and per_doc.get(key, 0) >= max_per_doc:
            continue

        if content:
            seen_content.add(content)
        seen_slots.add(slot)
        per_doc[key] = per_doc.get(key, 0) + 1
        kept.append(item)

    return kept


def format_results(results: list[dict], max_chars: int = 0) -> str:
    """Render chunks as text with rounded scores and source document names."""
    blocks = []
    for index, item in enumerate(results, 1):
        doc = item.get("doc_name") or "unknown"
        kb_name = item.get("kb_name")
        try:
            score = float(item.get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0

        header = f"[{index}] {doc}"
        if kb_name:
            header += f"  (kb: {kb_name})"
        header += f"  (score: {score:.3f})"
        span = item.get("chunk_span")
        if isinstance(span, dict):
            header += (
                f"  (块 {span.get('from')}–{span.get('to')}/{span.get('total_chunks')}"
                f", 补至 {span.get('count')} 块 / {span.get('chars')} 字符)"
            )
        blocks.append(f"{header}\n{str(item.get('content') or '').strip()}")

    text = "\n\n---\n\n".join(blocks)
    if max_chars and len(text) > max_chars:
        original = len(text)
        text = text[:max_chars].rstrip() + f"\n\n[已截断：原文 {original} 字符，上限 {max_chars} 字符]"
    return text


def results_as_json(results: list[dict]) -> str:
    """Machine-readable form, with scores rounded and content intact."""
    payload = []
    for index, item in enumerate(results, 1):
        try:
            score = round(float(item.get("score") or 0), 4)
        except (TypeError, ValueError):
            score = 0.0
        payload.append(
            {
                "rank": index,
                "doc_name": item.get("doc_name"),
                "kb_name": item.get("kb_name"),
                "chunk_index": item.get("chunk_index"),
                "score": score,
                "content": str(item.get("content") or "").strip(),
                **({"chunk_span": item["chunk_span"]} if item.get("chunk_span") else {}),
            }
        )
    return json.dumps(payload, ensure_ascii=False, indent=2)
