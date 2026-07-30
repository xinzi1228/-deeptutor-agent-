import urllib.request, json

r = urllib.request.urlopen('http://127.0.0.1:8001/api/v1/tools', timeout=10)
data = json.loads(r.read())
tools = data.get('tools', [])
found = []
for t in tools:
    name = t.get('name', '')
    if 'ls_' in name or 'annotation' in name:
        found.append(name)
        desc = t.get('description', '')[:60]
        print(f"  {name}: {desc}...")

print(f"\nTotal tools: {len(tools)}")
print(f"Found LS/Annotation tools: {len(found)}")
if found:
    print("All tools registered successfully!")
else:
    print("ERROR: No tools found - backend may still be loading.")
