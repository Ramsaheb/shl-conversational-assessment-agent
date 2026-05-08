import json

with open("app/data/catalog.json", "r", encoding="utf-8") as f:
    catalog = json.load(f)

# Find "Solution" entries (likely pre-packaged job solutions)
solutions = []
for i, item in enumerate(catalog):
    name = item["name"]
    if "solution" in name.lower():
        solutions.append((i, name, item.get("url", "")))

print(f"Found {len(solutions)} entries with 'Solution' in name:")
for idx, name, url in solutions:
    print(f"  [{idx}] {name}")
    print(f"       URL: {url}")

# Also check for "Job Solution" or "Pre-packaged" 
prepackaged = [item for item in catalog if "pre-packaged" in item.get("description","").lower() or "job solution" in item.get("description","").lower()]
print(f"\nFound {len(prepackaged)} with 'pre-packaged' or 'job solution' in description")

print(f"\nTotal catalog: {len(catalog)}")
print(f"After removing Solution entries: {len(catalog) - len(solutions)}")
