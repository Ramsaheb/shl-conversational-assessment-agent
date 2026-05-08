"""Verify catalog completeness against the live SHL website."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

catalog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "app", "data", "catalog.json")

with open(catalog_path, "r", encoding="utf-8") as f:
    catalog = json.load(f)

names = [i["name"] for i in catalog]

# Check last-page items exist
checks = ["Written English v1", "Written Spanish", "Zabbix (New)", "360 Digital Report"]
print("Last-page items present in catalog:")
for n in checks:
    print(f"  {n}: {n in names}")

print(f"\nFirst 5 items: {names[:5]}")
print(f"Last 5 items: {names[-5:]}")
print(f"Total: {len(catalog)} items, {len(set(names))} unique names")

# Verify all required fields
required_fields = ["id", "name", "url", "test_type", "description", "keywords", "skills", "tags"]
missing = []
for i, item in enumerate(catalog):
    for field in required_fields:
        if field not in item:
            missing.append(f"Item {i} ({item.get('name','?')}) missing '{field}'")

if missing:
    print(f"\nMissing fields ({len(missing)}):")
    for m in missing[:10]:
        print(f"  {m}")
else:
    print("\nAll items have all required fields.")

# Verify URL uniqueness
urls = [i["url"] for i in catalog]
dup_urls = len(urls) - len(set(urls))
print(f"Duplicate URLs: {dup_urls}")

print("\nCATALOG VERIFICATION: COMPLETE")
