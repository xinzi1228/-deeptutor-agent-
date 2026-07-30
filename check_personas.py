import urllib.request, json

paths = ['/api/v1/personas', '/api/v1/personas/list', '/api/v1/persona',
         '/api/v1/chat/personas', '/api/v1/settings/personas']
for path in paths:
    try:
        r = urllib.request.urlopen(f'http://127.0.0.1:8001{path}', timeout=5)
        print(f'{path}: {r.status}')
        if r.status == 200:
            data = json.loads(r.read())
            persons = data.get('personas', [])
            for p in persons:
                print(f"  - {p.get('name', '?')}")
    except Exception as e:
        print(f'{path}: {type(e).__name__} - {e}')
