"""Free Wikimedia topic search; bounded allowlisted photos and explicit rights.

Search relevance is not proof that a photo depicts the actual reported event.
No paid model, arbitrary URL, redirects, publication or copyright inference.
"""

import io
import json
import re
import warnings
from dataclasses import dataclass
from html.parser import HTMLParser
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image, UnidentifiedImageError

API = "https://commons.wikimedia.org/w/api.php"
MAX_PHOTO = 16 * 1024 * 1024
MAX_PIXELS = 25_000_000


class ImageProviderUnavailable(ValueError):
    """Safe terminal error; never leak provider body/private query in exceptions."""


class ImageProviderRetryable(ImageProviderUnavailable):
    """Transient connection/rate-limit failure, bounded by durable job attempts."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _plain(value):
    if not isinstance(value, str) or len(value) > 10000:
        raise ImageProviderUnavailable("IMAGE_METADATA_INVALID")
    parser = PlainText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def _safe_url(url, *, file=False):
    if not isinstance(url, str) or len(url) > 1500 or any(ord(c) < 32 for c in url):
        return False
    try:
        parts = urlsplit(url)
        expected = "upload.wikimedia.org" if file else "commons.wikimedia.org"
        path = unquote(parts.path)
        return bool(
            parts.scheme == "https"
            and parts.netloc == expected
            and not parts.query
            and not parts.fragment
            and "\\" not in path
            and ".." not in path.split("/")
            and "\x00" not in path
            and (path.startswith("/wikipedia/commons/") if file else path.startswith("/wiki/File:"))
            and (path.lower().endswith((".png", ".jpg", ".jpeg")) if file else True)
        )
    except ValueError:
        return False


def search_terms(text: str) -> str:
    if not isinstance(text, str) or len(text) > 10000:
        raise ImageProviderUnavailable("IMAGE_QUERY_INVALID")
    # Remove links and syntax so source content cannot inject Commons operators.
    text = re.sub(r"https?://\S+", " ", text)
    words = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    query = " ".join(dict.fromkeys(word.casefold() for word in words if len(word) >= 3))[:300]
    if not query:
        raise ImageProviderUnavailable("IMAGE_QUERY_EMPTY")
    return query


def _download_url(url):
    if not isinstance(url, str) or len(url) > 1500:
        raise ImageProviderUnavailable("IMAGE_URL_INVALID")
    parts = urlsplit(url)
    # Imageinfo currently attaches UTM tracking; strip only those known keys.
    if any(
        key not in {"utm_source", "utm_campaign", "utm_content"}
        for key, _ in parse_qsl(parts.query, keep_blank_values=True)
    ):
        raise ImageProviderUnavailable("IMAGE_URL_INVALID")
    canonical = parts._replace(query="").geturl()
    if not _safe_url(canonical, file=True):
        raise ImageProviderUnavailable("IMAGE_URL_INVALID")
    return canonical


@dataclass(frozen=True, slots=True)
class ImageSearchResult:
    page_id: int
    title: str
    download_url: str
    source_url: str
    license_code: str
    attribution: str
    mime_type: str
    size: int
    width: int
    height: int
    tags: tuple[str, ...]


def _parse_page(page) -> ImageSearchResult:
    info = page["imageinfo"][0]
    meta = info["extmetadata"]

    def field(key):
        return _plain(meta.get(key, {}).get("value", ""))

    name, license_url = field("LicenseShortName"), field("LicenseUrl").rstrip("/") + "/"
    if field("Restrictions"):
        raise ImageProviderUnavailable("IMAGE_RIGHTS_RESTRICTED")
    if name == "CC0" and license_url == "https://creativecommons.org/publicdomain/zero/1.0/":
        license_code = "CC0"
    elif (
        name in {"CC BY 3.0", "CC BY 4.0"}
        and license_url == f"https://creativecommons.org/licenses/by/{name.removeprefix('CC BY ')}/"
    ):
        license_code = "CC-BY"
    else:
        raise ImageProviderUnavailable("IMAGE_LICENSE_UNSUPPORTED")
    source, url, author = info["descriptionurl"], _download_url(info["url"]), field("Artist")
    if not _safe_url(source) or not _safe_url(url, file=True) or not author:
        raise ImageProviderUnavailable("IMAGE_PROVENANCE_INVALID")
    dimensions = [info[key] for key in ("size", "width", "height")]
    if any(type(value) is not int or value <= 0 for value in dimensions):
        raise ImageProviderUnavailable("IMAGE_DIMENSIONS_INVALID")
    size, width, height = dimensions
    mime = info["mime"]
    title = _plain(page["title"])
    attribution = f"{title} — {author}; {name}; {license_url}; {source}; иллюстрация"
    if (
        size > MAX_PHOTO
        or width * height > MAX_PIXELS
        or mime not in {"image/png", "image/jpeg"}
        or len(attribution) > 2048
        or type(page["pageid"]) is not int
        or page["pageid"] <= 0
    ):
        raise ImageProviderUnavailable("IMAGE_METADATA_INVALID")
    tags = tuple(search_terms(title + " " + field("ImageDescription")).split()[:40])
    return ImageSearchResult(
        page["pageid"],
        title,
        url,
        source,
        license_code,
        attribution,
        mime,
        size,
        width,
        height,
        tags,
    )


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ImageProviderUnavailable("IMAGE_METADATA_DUPLICATE_KEY")
        result[key] = value
    return result


class CommonsImageProvider:
    def __init__(self, *, opener=None):
        self._open = opener or build_opener(NoRedirect()).open

    def _fetch(self, url, mime, limit):
        request = Request(
            url,
            headers={
                "User-Agent": "ContentStudio/0.1 (https://github.com/borovojarkadij-png/content-studio)",
                "Accept": mime,
            },
        )
        deadline = monotonic() + 10
        try:
            with self._open(request, timeout=10) as response:
                if response.status != 200 or response.geturl() != url:
                    raise ImageProviderUnavailable("IMAGE_HTTP_INVALID")
                if response.headers.get("Content-Type", "").split(";")[0] != mime:
                    raise ImageProviderUnavailable("IMAGE_CONTENT_TYPE_INVALID")
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdigit() or int(length) > limit):
                    raise ImageProviderUnavailable("IMAGE_RESPONSE_TOO_LARGE")
                content = bytearray()
                read = getattr(response, "read1", response.read)
                while True:
                    if monotonic() >= deadline:
                        raise ImageProviderRetryable("IMAGE_TIMEOUT")
                    chunk = read(min(65536, limit + 1 - len(content)))
                    if not chunk:
                        break
                    content.extend(chunk)
                    if len(content) > limit:
                        raise ImageProviderUnavailable("IMAGE_RESPONSE_TOO_LARGE")
                return bytes(content)
        except HTTPError as error:
            if error.code == 429 or error.code >= 500:
                raise ImageProviderRetryable("IMAGE_NETWORK_UNAVAILABLE") from None
            raise ImageProviderUnavailable("IMAGE_HTTP_INVALID") from None
        except (URLError, OSError, TimeoutError):
            raise ImageProviderRetryable("IMAGE_NETWORK_UNAVAILABLE") from None

    def search(self, text: str, *, limit: int = 5) -> list[ImageSearchResult]:
        if type(limit) is not int or not 1 <= limit <= 5:
            raise ImageProviderUnavailable("IMAGE_LIMIT_INVALID")
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": search_terms(text),
            "gsrnamespace": "6",
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
        }
        try:
            data = json.loads(
                self._fetch(API + "?" + urlencode(params), "application/json", 512 * 1024),
                object_pairs_hook=_unique,
            )
            if not isinstance(data, dict) or "error" in data:
                raise ImageProviderUnavailable("IMAGE_SEARCH_FAILED")
            pages = data.get("query", {}).get("pages", [])
            if not isinstance(pages, list) or len(pages) > 5:
                raise ImageProviderUnavailable("IMAGE_SEARCH_INVALID")
            results = []
            for page in pages:
                try:
                    results.append(_parse_page(page))
                except (ImageProviderUnavailable, KeyError, TypeError, IndexError, AttributeError):
                    continue  # No inference of permission for missing/ambiguous metadata.
            return results[:limit]
        except (ValueError, TypeError, AttributeError) as error:
            if isinstance(error, ImageProviderUnavailable):
                raise
            raise ImageProviderUnavailable("IMAGE_SEARCH_INVALID") from None

    def download(self, result: ImageSearchResult) -> bytes:
        if not _safe_url(result.download_url, file=True):
            raise ImageProviderUnavailable("IMAGE_URL_INVALID")
        data = self._fetch(result.download_url, result.mime_type, MAX_PHOTO)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if (
                        image.format not in {"PNG", "JPEG"}
                        or image.width * image.height > MAX_PIXELS
                        or image.size != (result.width, result.height)
                        or image.get_format_mimetype() != result.mime_type
                        or getattr(image, "n_frames", 1) != 1
                        or len(data) != result.size
                    ):
                        raise ImageProviderUnavailable("IMAGE_DECODE_INVALID")
                    image.verify()
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ):
            raise ImageProviderUnavailable("IMAGE_DECODE_INVALID") from None
        return data
