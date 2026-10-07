import io
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


def metadata(**overrides):
    info = {
        "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Test.png",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test.png",
        "mime": "image/png",
        "size": len(png()),
        "width": 4,
        "height": 4,
        "extmetadata": {
            "LicenseShortName": {"value": "CC BY 4.0"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"},
            "Artist": {"value": '<a href="https://example.org">Test author</a>'},
            "ImageDescription": {"value": "A factory photograph"},
            "Restrictions": {"value": ""},
        },
    }
    info.update(overrides)
    return {"pageid": 10, "title": "File:Test.png", "imageinfo": [info]}


class Response(io.BytesIO):
    status = 200

    def __init__(self, content, mime="application/json", url=None):
        super().__init__(content)
        self.headers = {"Content-Type": mime, "Content-Length": str(len(content))}
        self.url = url

    def geturl(self):
        return self.url


def provider(pages):
    from newsflow.providers.commons_images import CommonsImageProvider

    calls = []

    def opener(request, timeout):
        calls.append(request)
        assert 0 < timeout <= 10
        return Response(json.dumps({"query": {"pages": pages}}).encode(), url=request.full_url)

    return CommonsImageProvider(opener=opener), calls


def test_free_search_sanitizes_query_and_preserves_plain_text_rights():
    images, calls = provider([metadata()])
    result = images.search('factory incategory:"private" https://secret.test')
    query = parse_qs(urlsplit(calls[0].full_url).query)
    assert query["generator"] == ["search"] and query["gsrnamespace"] == ["6"]
    assert '"' not in query["gsrsearch"][0] and "https://" not in query["gsrsearch"][0]
    assert result[0].license_code == "CC-BY"
    assert "Test author" in result[0].attribution and "<a" not in result[0].attribution
    assert "creativecommons.org/licenses/by/4.0" in result[0].attribution


def test_canonical_license_url_without_trailing_slash_is_supported():
    page = metadata()
    page["imageinfo"][0]["extmetadata"]["LicenseUrl"]["value"] = (
        "https://creativecommons.org/licenses/by/4.0"
    )
    images, _ = provider([page])
    assert len(images.search("factory")) == 1


def test_api_tracking_query_is_removed_without_accepting_arbitrary_query():
    page = metadata()
    info = page["imageinfo"][0]
    original = info["url"]
    info["url"] += "?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original"
    images, _ = provider([page])
    assert images.search("factory")[0].download_url == original
    info["url"] = original + "?redirect=http://127.0.0.1"
    assert images.search("factory") == []


def test_explicit_cc_by_three_license_preserves_its_exact_version():
    page = metadata()
    info = page["imageinfo"][0]
    info["extmetadata"]["LicenseShortName"]["value"] = "CC BY 3.0"
    info["extmetadata"]["LicenseUrl"]["value"] = "https://creativecommons.org/licenses/by/3.0"
    images, _ = provider([page])
    assert "CC BY 3.0" in images.search("factory")[0].attribution


@pytest.mark.parametrize("license_name", ["CC BY-SA 4.0", "CC BY-NC", "Public domain", "Unknown"])
def test_ambiguous_or_unsupported_licenses_are_not_download_candidates(license_name):
    page = metadata()
    page["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"] = license_name
    images, _ = provider([page])
    assert images.search("factory") == []


@pytest.mark.parametrize(
    "url",
    [
        "http://upload.wikimedia.org/wikipedia/commons/a/ab/Test.png",
        "https://upload.wikimedia.org.evil.test/Test.png",
        "https://user@upload.wikimedia.org/wikipedia/commons/a/ab/Test.png",
        "https://127.0.0.1/Test.png",
        "https://upload.wikimedia.org:444/wikipedia/commons/a/ab/Test.png",
        "https://upload.wikimedia.org/wikipedia/commons/../Test.png",
    ],
)
def test_untrusted_download_destinations_are_rejected_before_network(url):
    images, calls = provider([metadata(url=url)])
    assert images.search("factory") == []
    assert len(calls) == 1


def test_download_decodes_real_image_and_rejects_signature_only_content():
    from newsflow.providers.commons_images import CommonsImageProvider, ImageProviderUnavailable

    images, _ = provider([metadata()])
    result = images.search("factory")[0]
    transport = CommonsImageProvider(
        opener=lambda request, timeout: Response(png(), "image/png", request.full_url)
    )
    assert transport.download(result) == png()
    malformed = CommonsImageProvider(
        opener=lambda request, timeout: Response(
            b"\x89PNG\r\n\x1a\ninvalid", "image/png", request.full_url
        )
    )
    with pytest.raises(ImageProviderUnavailable):
        malformed.download(result)


def test_response_redirect_or_wrong_mime_cannot_be_imported():
    from newsflow.providers.commons_images import CommonsImageProvider, ImageProviderUnavailable

    images, _ = provider([metadata()])
    result = images.search("factory")[0]
    transport = CommonsImageProvider(
        opener=lambda request, timeout: Response(png(), "text/html", "http://127.0.0.1/")
    )
    with pytest.raises(ImageProviderUnavailable):
        transport.download(result)


@pytest.mark.parametrize(
    "change", ["artist", "restrictions", "oversize", "pixels", "svg", "license_url"]
)
def test_missing_or_unsafe_metadata_is_not_a_download_candidate(change):
    page = metadata()
    info = page["imageinfo"][0]
    if change == "artist":
        info["extmetadata"]["Artist"]["value"] = ""
    elif change == "restrictions":
        info["extmetadata"]["Restrictions"]["value"] = "trademarked"
    elif change == "oversize":
        info["size"] = 16 * 1024 * 1024 + 1
    elif change == "pixels":
        info["width"] = info["height"] = 100000
    elif change == "svg":
        info["mime"] = "image/svg+xml"
    else:
        info["extmetadata"]["LicenseUrl"]["value"] = "https://evil.test/license"
    images, _ = provider([page])
    assert images.search("factory") == []


@pytest.mark.parametrize(
    "payload", [b'{"query":{},"query":{}}', b'{"error":{}}', b'{"query":{"pages":{}}}', b"not-json"]
)
def test_malformed_catalog_fails_closed_without_private_error_text(payload):
    from newsflow.providers.commons_images import CommonsImageProvider, ImageProviderUnavailable

    images = CommonsImageProvider(
        opener=lambda request, timeout: Response(payload, url=request.full_url)
    )
    with pytest.raises(ImageProviderUnavailable):
        images.search("factory")


@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (404, False)])
def test_http_failures_distinguish_bounded_retry_from_terminal_error(status, retryable):
    from urllib.error import HTTPError

    from newsflow.providers.commons_images import (
        CommonsImageProvider,
        ImageProviderRetryable,
        ImageProviderUnavailable,
    )

    def fail(request, timeout):
        raise HTTPError(request.full_url, status, "private upstream message", {}, None)

    with pytest.raises(ImageProviderUnavailable) as failure:
        CommonsImageProvider(opener=fail).search("factory")
    assert isinstance(failure.value, ImageProviderRetryable) is retryable
    assert "private" not in str(failure.value)
