from __future__ import annotations

import time
from typing import Any, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from app.core.config import settings
from app.services.html_extract import extract_records_from_html
from app.services.url_safety import resolve_and_block_private_hosts


def extract_records_with_selenium(
    *,
    url: str,
    css_selector: str,
    wait_time: int,
    cookies: Optional[dict[str, str]] = None,
    scroll_count: int = 0,
    scroll_delay_ms: int = 2000,
) -> list[dict[str, Any]]:
    if settings.block_private_networks:
        resolve_and_block_private_hosts(url)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        if cookies:
            # Must navigate to domain before setting cookies
            # Taking a lightweight approach: visit 404 page or root?
            # Selenium requires us to be on the domain.
            # Best effort: go to url, then set cookies, then refresh.
            try:
                driver.get(url)
                for k, v in cookies.items():
                    driver.add_cookie({"name": k, "value": v})
                driver.refresh()
            except Exception:
                pass  # If first load fails, we can't set cookies easily
        else:
            driver.get(url)

        # Initial wait
        if wait_time > 0:
            time.sleep(wait_time)

        # Auto-scroll loop
        if scroll_count > 0:
            for _ in range(scroll_count):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_delay_ms / 1000.0)

        # Get final HTML
        html_source = driver.page_source

        # consistency check - if we scrolled, give it one last small grace period
        if scroll_count > 0:
            time.sleep(1.0)
            html_source = driver.page_source

        # Use our universal extractor
        return extract_records_from_html(html_source, css_selector=css_selector)

    finally:
        driver.quit()
