#!/usr/bin/env python3
"""Heuristic public-tree scan. Prints paths and rule names, never matched values."""
from pathlib import Path
import re
import sys

RULES = {
    'private key': rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
    'GitHub token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})',
    'API key': rb'\bsk-[A-Za-z0-9_-]{20,}',
    'user home': rb'/(?:Users|home)/[A-Za-z0-9_.-]+/',
    'IPv4 address': rb'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    'WeChat app identifier': rb'\bwx[a-fA-F0-9]{16}\b',
    'private media identifier': rb'\b2Jnl[A-Za-z0-9_-]{30,}',
    'credential assignment': rb'(?im)^[ \t]*(?:WECHAT_SECRET|WECHAT_APPID|ACCESS_TOKEN|API_KEY)[ \t]*=[ \t]*["\x27]?[A-Za-z0-9_-]{8,}',
}
SKIP = {'.git', '.venv', '__pycache__', 'work', 'private', 'receipts'}


def scan(root):
    findings = []
    for p in root.rglob('*'):
        rel = p.relative_to(root)
        if not p.is_file() or any(part in SKIP for part in rel.parts):
            continue
        if p.name == Path(__file__).name:
            continue
        if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif'}:
            # Sample assets are generated locally without metadata; inspect any new media separately.
            continue
        data = p.read_bytes()
        for rule, pattern in RULES.items():
            if re.search(pattern, data):
                findings.append((str(rel), rule))
    return findings


if __name__ == '__main__':
    results = scan(Path(__file__).resolve().parents[1])
    for path, rule in results:
        print(path + ': ' + rule)
    print('Privacy scan: ' + ('FAIL' if results else 'PASS'))
    sys.exit(bool(results))
