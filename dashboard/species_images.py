# dashboard/species_images.py
"""Resolve a representative image URL for a species from external sources.

Wikipedia/Wikimedia is tried first (clean, representative lead image with
Commons-sourced attribution and license), GBIF occurrence media second.

Notes
-----
`image_url` returned here is always a direct image-file URL; `source_url` is an
HTML page to credit/link back to. Callers persist these onto `Species`.
"""
import dataclasses
import re
from urllib.parse import quote, unquote

import requests

USER_AGENT = (
    "gbif-alert/2.x species-image-fetcher "
    "(+https://github.com/riparias/gbif-alert)"
)
_TIMEOUT = 15

_WIKIPEDIA_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_GBIF_OCCURRENCE_SEARCH = "https://api.gbif.org/v1/occurrence/search"

_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Wikimedia thumbnail filenames are "<width>px-<original name>" (e.g.
# "320px-Vulpes_vulpes.jpg"); the Commons File: title uses the original name.
_THUMB_PREFIX_RE = re.compile(r"^\d+px-(.+)$")


@dataclasses.dataclass
class ResolvedImage:
    """A resolved species image and its credit metadata.

    Attributes
    ----------
    image_url : str
        Direct image-file URL.
    source_url : str
        HTML page to credit/link back to.
    attribution : str
        Author / rights-holder, plain text.
    license : str
        License short name (may be empty if unknown).
    source_type : str
        Either ``"wikipedia"`` or ``"gbif"``.
    """

    image_url: str
    source_url: str
    attribution: str
    license: str
    source_type: str


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}


def _strip_html(value: str) -> str:
    return _HTML_TAG_RE.sub("", value).strip()


def resolve_wikipedia_image(scientific_name: str) -> ResolvedImage | None:
    """Resolve a lead image from the English Wikipedia for a scientific name."""
    url = _WIKIPEDIA_SUMMARY.format(title=quote(scientific_name))
    try:
        resp = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    # Prefer the summary's sized thumbnail over the full-resolution original:
    # originals can be several MB / thousands of px, which is wasteful when we
    # only ever display a small image (tooltip <= 200px, admin thumbnail 40px).
    # Fall back to the original when no thumbnail is offered.
    thumbnail = (data.get("thumbnail") or {}).get("source")
    original = (data.get("originalimage") or {}).get("source")
    image_url = thumbnail or original
    if not image_url:
        return None

    page_url = (
        data.get("content_urls", {}).get("desktop", {}).get("page", "")
    )
    attribution, license_name = _wikimedia_credit(image_url)
    return ResolvedImage(
        image_url=image_url,
        source_url=page_url,
        attribution=attribution,
        license=license_name,
        source_type="wikipedia",
    )


def _commons_filename(image_url: str) -> str:
    """Derive the canonical Commons File: name from an image URL.

    Works for both a full-resolution original URL and a sized thumbnail URL
    (the latter has a ``<width>px-`` prefix that must be stripped so the Commons
    extmetadata lookup targets the real file).
    """
    name = unquote(image_url.rsplit("/", 1)[-1])
    match = _THUMB_PREFIX_RE.match(name)
    return match.group(1) if match else name


def _wikimedia_credit(image_url: str) -> tuple[str, str]:
    """Fetch Commons extmetadata (author + license) for an image file URL."""
    filename = _commons_filename(image_url)
    try:
        resp = requests.get(
            _COMMONS_API,
            params={
                "action": "query",
                "titles": f"File:{filename}",
                "prop": "imageinfo",
                "iiprop": "extmetadata",
                "format": "json",
            },
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        pages = resp.json().get("query", {}).get("pages", {})
        page: dict = next(iter(pages.values()), {})
        ext = page.get("imageinfo", [{}])[0].get("extmetadata", {})
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return "", ""
    artist = _strip_html(ext.get("Artist", {}).get("value", ""))
    license_name = _strip_html(ext.get("LicenseShortName", {}).get("value", ""))
    return artist, license_name


def resolve_gbif_image(gbif_taxon_key: int) -> ResolvedImage | None:
    """Resolve a StillImage from GBIF occurrence media for a taxon key."""
    try:
        resp = requests.get(
            _GBIF_OCCURRENCE_SEARCH,
            params={
                "taxonKey": str(gbif_taxon_key),
                "mediaType": "StillImage",
                "limit": "20",
            },
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        results = resp.json().get("results", [])
    except (requests.RequestException, ValueError):
        return None

    for occ in results:
        for media in occ.get("media", []):
            identifier = media.get("identifier")
            if media.get("type") == "StillImage" and identifier:
                return ResolvedImage(
                    image_url=identifier,
                    source_url=f"https://www.gbif.org/occurrence/{occ.get('key')}",
                    attribution=media.get("rightsHolder")
                    or media.get("creator")
                    or "",
                    license=media.get("license", ""),
                    source_type="gbif",
                )
    return None


def resolve_species_image(
    scientific_name: str, gbif_taxon_key: int
) -> ResolvedImage | None:
    """Wikipedia first, GBIF occurrence media as fallback."""
    return resolve_wikipedia_image(scientific_name) or resolve_gbif_image(
        gbif_taxon_key
    )
