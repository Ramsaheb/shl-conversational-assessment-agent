"""Scrape SHL product catalog pages (optional utility).

This script scrapes product names and URLs from the SHL catalog.
The catalog.json is already pre-built from research, so this is
provided as a supplementary tool for future catalog updates.
"""

import json
import httpx
from bs4 import BeautifulSoup
from app.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://www.shl.com/products/product-catalog/"


def scrape_catalog_page(url: str) -> list[dict]:
    """Scrape a single catalog page for product links."""
    items = []
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find product links (they contain /product-catalog/view/)
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/product-catalog/view/" in href:
                name = link.get_text(strip=True)
                if name:
                    full_url = href if href.startswith("http") else f"https://www.shl.com{href}"
                    items.append({"name": name, "url": full_url})

    except Exception as e:
        logger.error("Error scraping %s: %s", url, str(e))

    return items


def scrape_all_pages(max_pages: int = 35) -> list[dict]:
    """Scrape all paginated catalog pages."""
    all_items = []
    seen_urls = set()

    for page_type in [1]:  # type=1 (individual skills), removed type=2 (solutions)
        for start in range(0, max_pages * 12, 12):
            url = f"{BASE_URL}?start={start}&type={page_type}"
            logger.info("Scraping: %s", url)
            items = scrape_catalog_page(url)

            if not items:
                break

            for item in items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    all_items.append(item)

    return all_items


if __name__ == "__main__":
    items = scrape_all_pages()
    print(f"Scraped {len(items)} items")
    with open("scraped_catalog.json", "w") as f:
        json.dump(items, f, indent=2)
    print("Saved to scraped_catalog.json")
