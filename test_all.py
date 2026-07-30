import urllib.request, json, asyncio

# Test skills API
try:
    r = urllib.request.urlopen('http://127.0.0.1:8001/api/v1/skills', timeout=5)
    data = json.loads(r.read())
    items = data.get('skills', [])
    print(f"Skills count: {len(items)}")
    for s in items:
        name = s.get('name', '')
        if 'annotation' in name.lower():
            print(f"SKILL FOUND: {name}")
except Exception as e:
    print(f"Skills API error: {e}")

# Test annotation_check tool via ToolRegistry
print("\nTesting annotation_check via registry...")
from deeptutor.runtime.registry.tool_registry import get_tool_registry
registry = get_tool_registry()
registry.load_builtins()
tool = registry.get("annotation_check")
if tool:
    print(f"Tool loaded: {tool.name}")
    definition = tool.get_definition()
    print(f"Description: {definition.description[:80]}")
    print(f"Parameters: {[p.name for p in definition.parameters]}")

    # Test execute
    result = asyncio.run(tool.execute(
        predictions='[{"x":80,"y":120,"w":140,"h":160,"label":"cat"}]',
        ground_truth='[{"x":80,"y":120,"w":140,"h":160,"label":"cat"}]',
        task_type='bbox'
    ))
    print(f"\nExecute test: success={result.success}")
    print(f"Result: {result.content[:200]}")
else:
    print("ERROR: Tool not found in registry!")

print("\nAll tests completed!")
