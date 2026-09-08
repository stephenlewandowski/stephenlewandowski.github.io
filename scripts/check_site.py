#!/usr/bin/env python3
"""Check source HTML, local URLs, assets, anchors and sitemap (Python stdlib only).

Jekyll teaching .html URLs are resolved to their Markdown source. This is a
source check, not a Jekyll build or an external-link availability check.
"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://stephenlewandowski.github.io'
# Separate GitHub Pages publications are not files in this repository.
EXTERNAL_PROJECTS = {'korean-peninsula-aedes-suitability'}
errors = []


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.ids = []
        self.links = []
        self.tags = Counter()
        self.feed(path.read_text(encoding='utf-8'))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags[tag] += 1
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for attr in ('href', 'src'):
            if attrs.get(attr):
                self.links.append(attrs[attr])
        if tag == 'img' and 'alt' not in attrs:
            errors.append(f'{self.path.relative_to(ROOT)}: image missing alt')


def check_url(source, href):
    if '{{' in href or '{%' in href:
        return  # Liquid expressions are checked by GitHub Pages at build time.
    source_url = ORIGIN + '/' + source.relative_to(ROOT).as_posix()
    url = urlsplit(urljoin(source_url, href))
    if url.scheme not in ('http', 'https') or url.netloc != urlsplit(ORIGIN).netloc:
        return
    path = unquote(url.path).lstrip('/')
    if path.split('/')[0] in EXTERNAL_PROJECTS:
        return
    target = ROOT / path
    if target.is_dir():
        target /= 'index.html'
    if not target.is_file() and target.suffix == '.html':
        markdown = target.with_suffix('.md')
        if markdown.is_file() and markdown.read_text().startswith('---\n'):
            return  # Heading IDs are produced by Jekyll, not inferred here.
    if not target.is_file():
        errors.append(f'{source.relative_to(ROOT)}: missing target {href}')
    elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
        errors.append(f'{source.relative_to(ROOT)}: missing anchor {href}')


pages = {p: Page(p) for p in ROOT.rglob('*.html')
         if not any(part.startswith(('.', '_')) for part in p.relative_to(ROOT).parts)}
for path, page in pages.items():
    for tag in ('html', 'head', 'title', 'body', 'main', 'h1'):
        if page.tags[tag] != 1:
            errors.append(f'{path.relative_to(ROOT)}: expected one {tag}, found {page.tags[tag]}')
    for ident, count in Counter(page.ids).items():
        if count > 1:
            errors.append(f'{path.relative_to(ROOT)}: duplicate ID {ident}')
    for href in page.links:
        check_url(path, href)

sitemap = ROOT / 'sitemap.xml'
try:
    locations = ET.parse(sitemap).getroot().findall('{*}url/{*}loc')
    seen = set()
    for loc in locations:
        if loc.text in seen:
            errors.append(f'sitemap.xml: duplicate URL {loc.text}')
        seen.add(loc.text)
        check_url(sitemap, loc.text)
except ET.ParseError as exc:
    errors.append(f'sitemap.xml: {exc}')

if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'PASS: {len(pages)} HTML pages, local links/assets/HTML anchors, and {len(locations)} sitemap URLs.')
print('Not checked: external availability, rendered Markdown anchors, browser layout, or Jekyll output.')
