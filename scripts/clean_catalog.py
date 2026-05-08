"""Remove any pre-packaged Solution entries from catalog.json."""
import json

with open("app/data/catalog.json", "r", encoding="utf-8") as f:
    catalog = json.load(f)

original_count = len(catalog)

# Filter out entries with "Solution" in name (these look like pre-packaged job solutions)
filtered = [item for item in catalog if "solution" not in item["name"].lower()]

removed = original_count - len(filtered)
print(f"Original: {original_count}")
print(f"Removed: {removed}")
print(f"Remaining: {len(filtered)}")

# Show removed items
for item in catalog:
    if "solution" in item["name"].lower():
        print(f"  REMOVED: {item['name']}")

with open("app/data/catalog.json", "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print("\ncatalog.json updated.")
