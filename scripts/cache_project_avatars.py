#!/usr/bin/env python3
"""手动缓存 GitHub 维护者头像；构建和打开看板均不会访问 GitHub。"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets' / 'project-avatars'
MANIFEST = ROOT / 'assets' / 'project-avatars.json'


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    repos = json.loads((ROOT / 'data/latest.json').read_text())['repos']
    owners = sorted({r['repo'].split('/')[0].lower() for r in repos})
    catalog = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

    def cache(owner):
        if owner in catalog and (ROOT / catalog[owner]['src']).exists():
            return owner, catalog[owner]
        url = f'https://github.com/{owner}.png?size=96'
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            body = response.content
            if body.startswith(b'\x89PNG\r\n\x1a\n'):
                mime, ext = 'image/png', 'png'
            elif body.startswith(b'\xff\xd8\xff'):
                mime, ext = 'image/jpeg', 'jpg'
            else:
                return owner, None
            path = ASSETS / f'{owner}.{ext}'
            path.write_bytes(body)
            return owner, {'src': str(path.relative_to(ROOT)), 'mime': mime,
                           'source_url': url, 'kind': 'owner-avatar'}
        except requests.RequestException as error:
            print(f'SKIP {owner}: {type(error).__name__}')
            return owner, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        for owner, entry in pool.map(cache, owners):
            if entry:
                catalog[owner] = entry
    MANIFEST.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    print(f'Cached {sum(owner in catalog for owner in owners)}/{len(owners)} owner avatars')


if __name__ == '__main__':
    main()
