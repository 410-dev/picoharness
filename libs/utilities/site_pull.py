import asyncio
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from libs.picoharness.harness_tools import ModelFactory


@dataclass
class FetchResult:
    url: str
    final_url: str
    title: str
    description: str
    text: str
    links: List[Dict[str, str]]
    llm_summary: Optional[str]
    status: str
    error: Optional[str] = None


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are allowed.")
    if not parsed.netloc:
        raise ValueError("Invalid URL.")
    return url


def _clean_html_to_content(html: str, base_url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "form",
        "input",
        "button",
        "nav",
        "footer",
        "aside",
    ]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    description = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()

    # main/article 우선, 없으면 body 전체
    main = soup.find("main") or soup.find("article") or soup.body or soup

    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()

    links = []
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href = a["href"].strip()
        if label and href and not href.startswith("#"):
            links.append({"text": label[:120], "href": href[:500]})

    # 너무 많은 링크 방지
    links = links[:80]

    return {
        "title": title,
        "description": description,
        "text": text,
        "links": links,
    }


def _llm_extract_relevant_content(
        url: str,
        title: str,
        description: str,
        text: str,
        max_chars: int = 18000,
) -> str:
    trimmed_text = text[:max_chars]

    prompt = f"""
You are extracting useful page content from a rendered website.

URL:
{url}

Title:
{title}

Description:
{description}

Raw extracted text:
{trimmed_text}

Task:
Return a concise Korean extraction with:
1. 페이지의 핵심 주제
2. 주요 본문 내용
3. 중요한 수치, 날짜, 이름, 조건
4. 광고/네비게이션/쿠키/반복 문구로 보이는 내용은 제외
5. 원문에 없는 내용은 추측하지 말 것

Format:
- 핵심 요약:
- 주요 내용:
- 주의할 점:
""".strip()

    # return make_request("mini-llm", prompt, LMResponseType.text)
    return ModelFactory.get_model_for("price").chat(prompt).response()


async def fetch_site_content_async(
        url: str,
        timeout: int = 10,
        use_llm: bool = False,
        headless: bool = True,
) -> FetchResult:
    url = _validate_url(url)
    timeout_ms = timeout * 1000

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        context = await browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1365, "height": 768},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            color_scheme="light",
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        page = await context.new_page()
        page.set_default_timeout(timeout_ms)
        page.set_default_navigation_timeout(timeout_ms)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            # SPA / lazy rendering 대응: 살짝 스크롤하면서 컨텐츠 로딩 유도
            await page.mouse.move(400, 400)
            await page.wait_for_timeout(500)

            for _ in range(3):
                await page.mouse.wheel(0, 900)
                await page.wait_for_timeout(500)

            # networkidle은 일부 사이트에서 끝없이 대기할 수 있으므로 best-effort로만 사용
            try:
                await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
            except PlaywrightTimeoutError:
                pass

            final_url = page.url
            html = await page.content()

            extracted = _clean_html_to_content(html, final_url)

            llm_summary = None
            if use_llm and extracted["text"]:
                llm_summary = _llm_extract_relevant_content(
                    url=final_url,
                    title=extracted["title"],
                    description=extracted["description"],
                    text=extracted["text"],
                )

            return FetchResult(
                url=url,
                final_url=final_url,
                title=extracted["title"],
                description=extracted["description"],
                text=extracted["text"],
                links=extracted["links"],
                llm_summary=llm_summary,
                status="ok",
            )

        except Exception as e:
            return FetchResult(
                url=url,
                final_url=page.url if page else url,
                title="",
                description="",
                text="",
                links=[],
                llm_summary=None,
                status="error",
                error=f"{type(e).__name__}: {e}",
            )

        finally:
            await context.close()
            await browser.close()


def fetch_site_content(
        url: str,
        timeout: int = 10,
        use_llm: bool = False,
        headless: bool = True,
) -> Dict[str, Any]:
    """
    호출 예시:
        result = fetch_site_content("https://example.com", timeout=10)
    """
    result = asyncio.run(
        fetch_site_content_async(
            url=url,
            timeout=timeout,
            use_llm=use_llm,
            headless=headless,
        )
    )
    return asdict(result)