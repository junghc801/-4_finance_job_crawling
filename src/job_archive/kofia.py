import re
import time
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://m.kofia.or.kr"
LIST_URL = f"{BASE_URL}/brd/m_33/list.do"
DATE_PATTERN = re.compile(r"20\d{2}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Listing:
    external_id: str
    title: str
    url: str
    posted_at: date | None


@dataclass(frozen=True)
class Detail:
    body_text: str
    attachments: list[dict[str, str]]


def _clean_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _external_id(href: str) -> str | None:
    values = parse_qs(urlparse(href).query).get("seq")
    return values[0] if values else None


def _nearby_date(link) -> date | None:
    container = link.find_parent(["li", "tr", "article", "div"])
    candidate = container.get_text(" ", strip=True) if container else ""
    match = DATE_PATTERN.search(candidate)
    if not match:
        following = link.find_next(string=DATE_PATTERN)
        match = DATE_PATTERN.search(str(following)) if following else None
    return date.fromisoformat(match.group(0)) if match else None


def parse_list(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[Listing] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=re.compile(r"(?:/brd/m_33/|\./)?view\.do")):
        external_id = _external_id(link.get("href", ""))
        title = _clean_text(link.get_text(" ", strip=True))
        if not external_id or not title or external_id in seen:
            continue
        seen.add(external_id)
        results.append(
            Listing(
                external_id=external_id,
                title=title,
                url=urljoin(LIST_URL, link["href"]),
                posted_at=_nearby_date(link),
            )
        )
    return results


def parse_detail(html: str, title: str) -> Detail:
    soup = BeautifulSoup(html, "html.parser")
    content = (
        soup.select_one(".view_cont")
        or soup.select_one(".board_view")
        or soup.select_one(".contents")
        or soup.select_one("#content")
        or soup.body
    )
    if content is None:
        return Detail("", [])

    for tag in content.select("script, style, nav, header, footer"):
        tag.decompose()
    text = _clean_text(content.get_text("\n", strip=True))

    title_position = text.find(title)
    if title_position >= 0:
        text = text[title_position + len(title) :].lstrip()
    text = re.sub(r"^20\d{2}-\d{2}-\d{2}\s*", "", text)

    attachments = []
    for link in content.find_all("a", href=True):
        label = _clean_text(link.get_text(" ", strip=True))
        href = link["href"]
        if "첨부" in label or re.search(r"\.(pdf|docx?|xlsx?|hwp|zip)(?:\?|$)", href, re.I):
            attachments.append({"name": label, "url": urljoin(BASE_URL, href)})
    return Detail(text, attachments)


class KofiaClient:
    def __init__(self, delay: float = 1.5) -> None:
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "finance-job-archive/0.1 (personal research; low-rate crawler)"}
        )

    def _get(self, url: str, params: dict | None = None) -> str:
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        time.sleep(self.delay)
        return response.text

    def get_list(self, page: int) -> tuple[str, list[Listing]]:
        html = self._get(
            LIST_URL,
            params={
                "itm_seq_1": 0,
                "itm_seq_2": 0,
                "multi_itm_seq": 0,
                "page": page,
            },
        )
        return html, parse_list(html)

    def get_detail(self, listing: Listing) -> tuple[str, Detail]:
        html = self._get(listing.url)
        return html, parse_detail(html, listing.title)
