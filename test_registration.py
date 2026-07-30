import urllib.request, json

r = urllib.request.urlopen('http://127.0.0.1:8001/api/v1/tools', timeout=5)
tools = json.loads(r.read())
found = False
for t in tools.get('tools', []):
    if 'annotation' in t['name'].lower() or 'check' in t['name'].lower():
        print(f"TOOL FOUND: {t['name']} - {t['description'][:80]}")
        found = True
if not found:
    print("WARNING: annotation_check tool NOT found!")

r = urllib.request.urlopen('http://127.0.0.1:8001/api/v1/personas', timeout=5)
personas = json.loads(r.read())
print("\nPERSONAS:")
for p in personas.get('personas', []):
    print(f"  {p['name']} - {p.get('description','')[:60]}")
