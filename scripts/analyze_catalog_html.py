"""Check page 2 structure."""
import httpx
from bs4 import BeautifulSoup

for start in [0, 12, 24]:
    resp = httpx.get(
        f"https://www.shl.com/solutions/products/product-catalog/?start={start}&type=1",
        timeout=30, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")
    print(f"\n--- start={start}: {len(tables)} tables ---")
    for i, t in enumerate(tables):
        rows = t.find_all("tr")
        if rows:
            header = rows[0].find_all(["td", "th"])
            header_text = [c.get_text(strip=True)[:30] for c in header]
            print(f"  Table {i}: {len(rows)} rows, header={header_text}")
            if len(rows) > 1:
                first_row = rows[1].find_all("td")
                first_cell = first_row[0].get_text(strip=True)[:50] if first_row else "empty"
                print(f"    First data: {first_cell}")
