#!/usr/bin/env python3
"""Convert embedded CSS to inline styles; output is a separate upload copy."""
import argparse
from pathlib import Path
import css_inline

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.source.resolve() == a.output.resolve():
        p.error('Keep the editable original; choose a different output path')
    a.output.write_text(css_inline.CSSInliner(keep_style_tags=False).inline(
        a.source.read_text(encoding='utf-8')), encoding='utf-8')
    print('Inline upload copy saved')
