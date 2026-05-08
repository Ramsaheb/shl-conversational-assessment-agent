"""Check if Solution entries are from the Pre-packaged table."""
import httpx
from bs4 import BeautifulSoup

r = httpx.get(
    "https://www.shl.com/solutions/products/product-catalog/?start=0&type=1",
    timeout=30, follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0"}
)
soup = BeautifulSoup(r.text, "html.parser")
tables = soup.find_all("table")

for i, t in enumerate(tables):
    header = t.find("tr").get_text(strip=True)[:80]
    print(f"Table {i}: {header}")
    
    # Check if any of the Solution entries are in this table
    solution_names = [
        "Customer Service Phone Solution",
        "Entry Level Cashier Solution", 
        "Entry Level Sales Solution",
        "Sales & Service Phone Solution",
    ]
    rows = t.find_all("tr")[1:]
    for row in rows:
        link = row.find("a")
        if link:
            name = link.get_text(strip=True)
            if "solution" in name.lower():
                print(f"  FOUND: '{name}' in table {i}")
