#!/usr/bin/env python3
"""Manifest-driven draft operations. No public publishing or mass-send endpoint."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from bs4 import BeautifulSoup
import requests

API = 'https://api.weixin.qq.com/cgi-bin/'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inside(base, name):
    require(isinstance(name, str) and name and '\n' not in name, 'Invalid relative path')
    p = (base / name).resolve()
    require(not Path(name).is_absolute() and p.is_relative_to(base), 'Path escapes article directory')
    return p


def load_article(manifest):
    manifest = Path(manifest).resolve()
    cfg = json.loads(manifest.read_text(encoding='utf-8'))
    base = manifest.parent
    source, cover, receipt = [inside(base, cfg[k]) for k in ('source', 'cover', 'receipt')]
    require(receipt.suffix == '.json', 'Receipt must be JSON')
    soup = BeautifulSoup(source.read_text(encoding='utf-8'), 'html.parser')
    require(soup.title and soup.body, 'HTML needs title and body')
    title = soup.title.get_text(strip=True)
    require(0 < len(title) <= 64, 'Title must contain 1–64 characters; check current platform limits')
    require(not soup.select('h1, style, script, ul, ol, li'), 'Inline styles first; remove h1, scripts and native lists')
    require(isinstance(cfg.get('digest', ''), str) and len(cfg.get('digest', '')) <= 120, 'Digest too long')
    require(not soup.find(['iframe', 'object', 'embed', 'form']), 'Unsupported embedded content')
    require('file://' not in str(soup.body), 'Local file URL in body')
    images = []
    for img in soup.body.find_all('img'):
        require(img.get('alt', '').strip(), 'Every body image needs alt text')
        name = img.get('src', '')
        require(not re.match(r'^[a-zA-Z]+:', name), 'Save body images locally before uploading')
        p = inside(base, name)
        require(p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif'), 'Use raster body images')
        images.append((name, p))
    require(cover.suffix.lower() in ('.png', '.jpg', '.jpeg'), 'Use PNG/JPEG cover')
    files = list(dict.fromkeys([manifest, source, cover] + [p for _, p in images]))
    require(receipt not in files, 'Receipt must not overwrite an input')
    digest = hashlib.sha256()
    for p in files:
        require(p.is_file(), 'Required article asset is missing')
        name = p.relative_to(base).as_posix().encode()
        data = p.read_bytes()
        digest.update(len(name).to_bytes(8, 'big') + name)
        digest.update(len(data).to_bytes(8, 'big') + data)
    return dict(cfg=cfg, base=base, source=source, cover=cover, receipt=receipt,
                soup=soup, title=title, images=images, files=files, fingerprint=digest.hexdigest())


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(tmp, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(state, out, ensure_ascii=False, indent=2)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lockfile = path.with_suffix(path.suffix + '.lock')
    try:
        fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError('Receipt locked; inspect running jobs before removing the lock') from None
    try:
        os.close(fd)
        yield
    finally:
        lockfile.unlink()


class WeChat:
    def __init__(self):
        appid, secret = os.environ.get('WECHAT_APPID'), os.environ.get('WECHAT_SECRET')
        require(appid and secret, 'Missing server WeChat configuration')
        self.token = self.request('GET', 'token', params={
            'grant_type': 'client_credential', 'appid': appid, 'secret': secret})['access_token']

    def request(self, method, endpoint, **kwargs):
        # Never expose HTTP exception strings: they can include credential-bearing URLs.
        try:
            response = requests.request(method, API + endpoint, timeout=60, **kwargs)
            if not response.ok:
                raise RuntimeError('WeChat HTTP request failed; inspect state before retrying')
            response.encoding = 'utf-8'
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError('WeChat network/response failure; inspect state before retrying') from None
        if data.get('errcode', 0):
            raise RuntimeError('WeChat API error code ' + str(data['errcode']))
        return data

    def post(self, endpoint, payload):
        return self.request('POST', endpoint, params={'access_token': self.token},
                            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                            headers={'Content-Type': 'application/json; charset=utf-8'})

    def upload(self, endpoint, path, **params):
        with path.open('rb') as stream:
            return self.request('POST', endpoint, params={'access_token': self.token, **params},
                                files={'media': (path.name, stream)})


def normalized_text(soup):
    return ''.join(soup.get_text().split())


def verify(api, article, state):
    item = api.post('draft/get', {'media_id': state['media_id']})['news_item'][0]
    saved = BeautifulSoup(item['content'], 'html.parser')
    require(item['title'] == article['title'], 'Saved draft title differs')
    require(item['thumb_media_id'] == state['thumb_media_id'], 'Saved draft cover differs')
    require(len(saved.find_all('img')) == len(article['images']), 'Saved image count differs')
    for img in saved.find_all('img'):
        url = img.get('data-src') or img.get('src') or ''
        require(url.startswith('https://'), 'Saved image has no HTTPS source')
    require(not saved.find(['h1', 'script', 'style']), 'Unsupported saved HTML')
    require(normalized_text(saved) == normalized_text(article['soup'].body), 'Saved body text differs')
    state.update(verified=True, in_flight=None)
    save_state(article['receipt'], state)


def run(mode, article, api):
    path = article['receipt']
    with lock(path):
        state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if mode == 'verify':
            require(state.get('media_id'), 'No saved draft ID')
            require(state.get('fingerprint') == article['fingerprint'], 'Verify needs the submitted revision')
            verify(api, article, state)
            return
        require(not state.get('in_flight'), 'Earlier write has uncertain status; inspect receipt and drafts')
        if mode == 'create' and state.get('media_id'):
            require(state.get('fingerprint') == article['fingerprint'], 'Revision changed; use update')
            verify(api, article, state)
            return
        if mode == 'update':
            require(state.get('media_id'), 'Update requires an existing receipt and draft ID')
        if state.get('fingerprint') != article['fingerprint']:
            if state.get('media_id'):
                state.setdefault('history', []).append({k: v for k, v in state.items() if k != 'history'})
            state.update(fingerprint=article['fingerprint'], images={}, thumb_media_id=None, verified=False)
            save_state(path, state)
        if not state.get('thumb_media_id'):
            state['thumb_media_id'] = api.upload('material/add_material', article['cover'], type='image')['media_id']
            save_state(path, state)
        for name, p in article['images']:
            if name not in state['images']:
                state['images'][name] = api.upload('media/uploadimg', p)['url']
                save_state(path, state)
        body = BeautifulSoup(str(article['soup'].body), 'html.parser').body
        for img in body.find_all('img'):
            img['src'] = state['images'][img['src']]
            require(img['src'].startswith('https://'), 'Upload returned a non-HTTPS image')
        payload = dict(title=article['title'], digest=article['cfg'].get('digest', ''),
                       content=''.join(str(n) for n in body.contents), thumb_media_id=state['thumb_media_id'],
                       show_cover_pic=0, need_open_comment=0, only_fans_can_comment=0)
        author = os.environ.get('WECHAT_AUTHOR', '')
        if author:
            payload['author'] = author
        state.update(in_flight=mode, verified=False)
        save_state(path, state)
        if mode == 'create':
            state['media_id'] = api.post('draft/add', {'articles': [payload]})['media_id']
        else:
            api.post('draft/update', {'media_id': state['media_id'], 'index': 0, 'articles': payload})
        # Persist returned ID before readback, retaining in_flight until verified.
        save_state(path, state)
        verify(api, article, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['check', 'create', 'update', 'verify'])
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    article = load_article(args.manifest)
    if args.mode == 'check':
        print(f'Local check passed: {len(article["images"])} body images; no network request')
    else:
        run(args.mode, article, WeChat())
        print('Draft readback verified; private receipt saved')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Only controlled validation/runtime messages; no raw HTTP exceptions or response dumps.
        print(str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__, file=sys.stderr)
        sys.exit(1)
