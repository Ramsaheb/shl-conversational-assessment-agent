"""Scrape the FULL SHL Individual Test Solutions catalog.

The catalog at https://www.shl.com/solutions/products/product-catalog/
shows 12 items per page. Page 1 has two tables (Pre-packaged + Individual);
pages 2+ have only the Individual Test Solutions table.

We identify the correct table by checking for the header "Individual Test Solutions".
"""

import json
import re
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.shl.com/solutions/products/product-catalog/"
OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "data", "catalog.json"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def find_individual_table(soup: BeautifulSoup):
    """Find the 'Individual Test Solutions' table regardless of position."""
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if rows:
            header_text = rows[0].get_text(strip=True)
            if "Individual Test Solutions" in header_text:
                return table
    return None


def scrape_page(start: int, client: httpx.Client) -> list[dict]:
    """Scrape individual test solutions from one catalog page."""
    url = f"{BASE_URL}?start={start}&type=1"
    print(f"  Fetching: {url}")

    resp = client.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = find_individual_table(soup)
    if not table:
        return []

    items = []
    rows = table.find_all("tr")

    for row in rows[1:]:  # Skip header row
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        # Cell 0: Name + link
        link = cells[0].find("a", href=True)
        if not link:
            continue

        name = link.get_text(strip=True)
        if not name:
            continue

        href = link["href"]
        if href.startswith("/"):
            href = f"https://www.shl.com{href}"

        # Cell 1: Remote Testing (green dots / spans)
        remote_cell_html = str(cells[1])
        remote_testing = "catalogue__circle--yes" in remote_cell_html or bool(cells[1].find("span"))

        # Cell 2: Adaptive/IRT
        adaptive_cell_html = str(cells[2])
        adaptive = "catalogue__circle--yes" in adaptive_cell_html or bool(cells[2].find("span"))

        # Cell 3: Test Type codes (e.g., "K", "AKP", "AEBCDP")
        test_type = cells[3].get_text(strip=True)
        if not test_type:
            test_type = "K"

        # Build clean ID
        item_id = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:60]

        items.append({
            "id": item_id,
            "name": name,
            "url": href,
            "test_type": test_type,
            "remote_testing": remote_testing,
            "adaptive": adaptive,
        })

    return items


def enrich_item(item: dict) -> dict:
    """Add description, keywords, skills, tags based on name and type."""
    name_lower = item["name"].lower()
    test_type = item["test_type"]

    type_names = {
        "A": "Ability/Cognitive", "B": "Behavioral", "C": "Competency",
        "D": "Development", "E": "Evaluation", "K": "Knowledge",
        "P": "Personality", "S": "Simulation",
    }

    # Build description from type codes
    type_labels = [type_names[c] for c in test_type if c in type_names]
    type_str = ", ".join(type_labels) if type_labels else "Assessment"
    item["description"] = f"{item['name']} - {type_str} assessment from the SHL catalog."

    # Keywords from assessment name
    keywords = []
    name_words = re.findall(r'[a-zA-Z#\+\.]+', item["name"])
    for word in name_words:
        if len(word) >= 2 and word.lower() not in {"new", "the", "and", "for", "shl", "form", "short", "of", "in"}:
            keywords.append(word.lower())

    # Type-based keywords
    type_kw = {
        "A": ["cognitive", "ability", "aptitude", "reasoning"],
        "B": ["behavioral", "situational judgment", "workplace behavior"],
        "C": ["competency", "skills assessment"],
        "K": ["knowledge", "technical knowledge", "domain expertise"],
        "P": ["personality", "behavioral traits", "work style"],
        "S": ["simulation", "practical", "hands-on"],
    }
    for code in test_type:
        keywords.extend(type_kw.get(code, []))

    # Domain enrichment from name patterns
    tech_kw = {
        "java": ["java", "programming", "backend", "developer", "software"],
        "python": ["python", "programming", "scripting", "developer"],
        "javascript": ["javascript", "frontend", "web", "developer"],
        ".net": [".net", "c#", "microsoft", "backend"],
        "c++": ["c++", "programming", "systems"],
        "c#": ["c#", ".net", "microsoft"],
        "sql": ["sql", "database", "data", "query"],
        "html": ["html", "web", "frontend"],
        "css": ["css", "web", "frontend", "styling"],
        "php": ["php", "web", "backend"],
        "ruby": ["ruby", "programming", "rails"],
        "angular": ["angular", "frontend", "typescript", "web"],
        "react": ["react", "frontend", "javascript", "web"],
        "node": ["node.js", "backend", "javascript", "server"],
        "spring": ["spring", "java", "backend", "framework"],
        "django": ["django", "python", "web", "framework"],
        "docker": ["docker", "devops", "containers"],
        "kubernetes": ["kubernetes", "devops", "orchestration"],
        "linux": ["linux", "operating system", "sysadmin"],
        "windows server": ["windows", "server", "administration"],
        "excel": ["excel", "spreadsheet", "data", "office"],
        "accounting": ["accounting", "finance", "bookkeeping"],
        "accounts payable": ["accounts payable", "finance", "AP"],
        "accounts receivable": ["accounts receivable", "finance", "AR"],
        "typing": ["typing", "data entry", "speed", "clerical"],
        "customer service": ["customer service", "support", "communication"],
        "call center": ["call center", "customer service", "BPO"],
        "sales": ["sales", "revenue", "client", "business development"],
        "agile": ["agile", "scrum", "project management"],
        "automata": ["coding", "programming", "algorithm", "developer"],
        "coding": ["coding", "programming", "developer", "software"],
        "entry level": ["entry-level", "graduate", "junior"],
        "graduate": ["graduate", "entry-level", "junior"],
        "manager": ["manager", "leadership", "supervisory"],
        "administrative": ["administrative", "office", "clerical"],
        "mechanical": ["mechanical", "engineering", "physics"],
        "numerical": ["numerical", "math", "quantitative", "data"],
        "verbal": ["verbal", "reading", "comprehension", "language"],
        "deductive": ["deductive", "logic", "reasoning"],
        "inductive": ["inductive", "pattern", "abstract", "reasoning"],
        "personality": ["personality", "OPQ", "behavioral traits"],
        "motivation": ["motivation", "engagement", "drive"],
        "situational": ["situational judgment", "SJT", "behavioral"],
        "checking": ["attention to detail", "accuracy", "data checking"],
        "english": ["english", "language", "proficiency"],
        "reading": ["reading", "comprehension"],
        "calculation": ["arithmetic", "math", "numeracy"],
        "hadoop": ["big data", "distributed systems", "data engineering"],
        "aws": ["cloud", "infrastructure", "amazon web services"],
        "azure": ["cloud", "infrastructure", "microsoft"],
        "salesforce": ["CRM", "salesforce", "cloud"],
        "sap": ["ERP", "enterprise", "SAP"],
        "oracle": ["database", "oracle", "enterprise"],
        "wordpress": ["web", "CMS", "content management"],
        "photoshop": ["design", "creative", "adobe"],
        "illustrator": ["design", "creative", "adobe", "vector"],
        "autocad": ["CAD", "design", "engineering", "drafting"],
        "power bi": ["business intelligence", "data visualization", "analytics"],
        "tableau": ["business intelligence", "data visualization", "analytics"],
    }

    for pattern, extra in tech_kw.items():
        if pattern in name_lower:
            keywords.extend(extra)

    item["keywords"] = list(dict.fromkeys(keywords))
    item["skills"] = item["keywords"][:8]
    item["tags"] = [type_names.get(c, "") for c in test_type if c in type_names]

    return item


def main():
    print("=" * 60)
    print("SHL Full Catalog Scraper — Individual Test Solutions Only")
    print("=" * 60)

    all_items = []
    seen_names = set()
    consecutive_empty = 0

    with httpx.Client(headers=HEADERS) as client:
        for page_num in range(50):  # Up to 50 pages (600 items max)
            start = page_num * 12
            try:
                items = scrape_page(start, client)

                if not items:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        print(f"  Two consecutive empty pages. Done.")
                        break
                    continue
                else:
                    consecutive_empty = 0

                new_count = 0
                for item in items:
                    key = item["name"].lower().strip()
                    if key not in seen_names:
                        seen_names.add(key)
                        all_items.append(item)
                        new_count += 1

                print(f"  Page {page_num + 1}: {len(items)} items, {new_count} new. Total: {len(all_items)}")

                if new_count == 0:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                else:
                    consecutive_empty = 0

                time.sleep(0.3)

            except Exception as e:
                print(f"  ERROR on page {page_num + 1}: {e}")
                time.sleep(1)
                continue

    print(f"\nScraped {len(all_items)} individual test solutions.")

    # Enrich
    print("Enriching with keywords, tags, descriptions...")
    all_items = [enrich_item(item) for item in all_items]

    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {OUTPUT_PATH}")

    # Stats
    type_counts = {}
    for item in all_items:
        for code in item["test_type"]:
            type_counts[code] = type_counts.get(code, 0) + 1

    type_names = {"A": "Ability", "B": "Behavioral", "C": "Competency",
                  "D": "Development", "E": "Evaluation", "K": "Knowledge",
                  "P": "Personality", "S": "Simulation"}
    print("\nTest type distribution:")
    for code in sorted(type_counts):
        print(f"  {code} ({type_names.get(code, '?')}): {type_counts[code]}")

    print(f"\nSample items:")
    for item in all_items[:5]:
        print(f"  {item['name']} [{item['test_type']}] -> {item['url'][:70]}...")


if __name__ == "__main__":
    main()
