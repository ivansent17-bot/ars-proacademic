#!/usr/bin/env python3
"""ARS ProScience — скачать полные тексты источников Stage 1 в stage1/texts/.

Зачем. Правило дословности (10–20 % текста — куски источников слово в слово,
со ссылкой) выполнимо только по настоящему тексту источника. Пересказчик веба
(WebFetch) возвращает «дословные» цитаты, которых на странице нет, поэтому
тексты качаются этим скриптом напрямую, а сверка идёт по сохранённому файлу.

Запускает оркестратор (Bucket D) после того, как stage1/bibliography.md готов:

    python3 fetch_sources.py <run_dir>                 # все записи с URL или DOI
    python3 fetch_sources.py <run_dir> --force         # перекачать уже скачанное
    python3 fetch_sources.py <run_dir> --add 7 <url|файл.txt|файл.pdf>
                                                       # вручную: источник № 7

Источник без URL (книга, платная статья) скачать нельзя — его можно цитировать
только пересказом, дословно нельзя. Если страница не отдаётся скрипту, текст
можно сохранить из браузера (get_page_text) в .txt и добавить через --add.

Результат: stage1/texts/<NN>_<ключ>.txt (PDF — с маркерами
=====PDFPAGE N=====) и stage1/texts/index.json, который читает
verbatim_share.py для сверки «кусок ↔ ссылка на свой источник».
"""

import argparse
import html
import json
import os
import re
import shutil
import sys
import urllib.request
from html.parser import HTMLParser

SRC_LINE = re.compile(r'^\s*(?:\[?(\d{1,3})[\].)]|[-*•])\s+(.*\S)')
URL = re.compile(r'https?://[^\s<>"\]»]+')
DOI = re.compile(r'\b(10\.\d{4,9}/[^\s<>"\]»]+)', re.IGNORECASE)
KEY = re.compile(r'`?[#@]([A-Za-z][\w-]*)`?')
SURNAME = re.compile(r'([A-ZА-ЯЁ][a-zа-яё]+(?:-[A-ZА-ЯЁ][a-zа-яё]+)?)')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')
MIN_CHARS = 2000
MAX_BYTES = 40 * 1024 * 1024


def entries(bib_text):
    out, auto = [], 0
    for ln in bib_text.split('\n'):
        m = SRC_LINE.match(ln)
        if not m or len(ln.strip()) <= 30:
            continue
        auto += 1
        n = int(m.group(1)) if m.group(1) else auto
        body = m.group(2)
        km = KEY.search(body)
        key = km.group(1) if km else None
        rest = KEY.sub('', body).strip(' `—–-')
        sm = SURNAME.search(rest)
        url = None
        um = URL.search(body)
        if um:
            url = um.group(0).rstrip(').,;:')
        else:
            dm = DOI.search(body)
            if dm:
                url = 'https://doi.org/' + dm.group(1).rstrip(').,;:')
        out.append({'n': n, 'key': key, 'author': sm.group(1) if sm else None,
                    'url': url, 'entry': body[:300]})
    return out


class _Text(HTMLParser):
    BLOCK = {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
             'section', 'article', 'blockquote', 'td', 'table', 'ul', 'ol'}
    SKIP = {'script', 'style', 'noscript', 'nav', 'header', 'footer', 'form', 'svg',
            'aside', 'button', 'select'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw):
    # КиберЛенинка и многие журнальные сайты держат статью в itemprop="articleBody"
    m = re.search(r'<div[^>]+itemprop="articleBody"[^>]*>(.*?)</div>\s*</div>', raw, re.S)
    if m and len(m.group(1)) > 3000:
        raw = m.group(1)
    p = _Text()
    p.feed(raw)
    t = html.unescape(''.join(p.parts))
    t = re.sub(r'[ \t ]+', ' ', t)
    t = re.sub(r'\s*\n\s*', '\n', t)
    return t.strip()


def pdf_to_text(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, 'нет пакета pypdf (pip install pypdf)'
    try:
        r = PdfReader(path)
        chunks = []
        for i, pg in enumerate(r.pages, 1):
            chunks.append('=====PDFPAGE %d=====\n%s' % (i, pg.extract_text() or ''))
        return '\n'.join(chunks), None
    except Exception as exc:  # noqa: BLE001 — битый PDF = источник не скачан
        return None, 'PDF не читается: %s' % exc


def decode(data, ctype):
    cs = None
    m = re.search(r'charset=([\w-]+)', ctype or '', re.I)
    if m:
        cs = m.group(1)
    else:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', data[:4000], re.I)
        if m:
            cs = m.group(1).decode('ascii', 'ignore')
    for enc in (cs, 'utf-8', 'cp1251'):
        if not enc:
            continue
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode('utf-8', 'replace')


def fetch(url, tmp_pdf):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Accept-Language': 'ru,en;q=0.8',
        'Accept': 'text/html,application/pdf,*/*;q=0.8'})
    with urllib.request.urlopen(req, timeout=45) as r:
        data = r.read(MAX_BYTES + 1)
        ctype = r.headers.get('Content-Type', '')
    if len(data) > MAX_BYTES:
        return None, 'файл больше 40 МБ'
    if data[:5] == b'%PDF-' or 'pdf' in ctype.lower():
        with open(tmp_pdf, 'wb') as f:
            f.write(data)
        return pdf_to_text(tmp_pdf)
    return html_to_text(decode(data, ctype)), None


def slug(e):
    base = e.get('key') or e.get('author') or 'src'
    base = re.sub(r'[^\w-]+', '_', base, flags=re.U).strip('_')[:40] or 'src'
    return '%02d_%s' % (e['n'], base)


def from_local(path, tmp_pdf):
    if path.lower().endswith('.pdf'):
        shutil.copyfile(path, tmp_pdf)
        return pdf_to_text(tmp_pdf)
    return open(path, encoding='utf-8', errors='replace').read(), None


def main():
    ap = argparse.ArgumentParser(description='Скачать тексты источников Stage 1')
    ap.add_argument('run_dir')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--add', nargs=2, metavar=('N', 'URL_ИЛИ_ФАЙЛ'),
                    help='добавить источник № N по ссылке или из локального файла')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    bib = os.path.join(args.run_dir, 'stage1', 'bibliography.md')
    if not os.path.isfile(bib):
        print('Нет %s — сначала список литературы Stage 1' % bib)
        sys.exit(2)
    outdir = os.path.join(args.run_dir, 'stage1', 'texts')
    os.makedirs(outdir, exist_ok=True)
    idx_path = os.path.join(outdir, 'index.json')
    old = {}
    if os.path.isfile(idx_path):
        try:
            old = {e['n']: e for e in json.load(open(idx_path, encoding='utf-8'))['sources']}
        except (ValueError, KeyError):
            old = {}
    ents = entries(open(bib, encoding='utf-8', errors='replace').read())
    tmp_pdf = os.path.join(outdir, '_download.pdf')

    targets = ents
    if args.add:
        n = int(args.add[0])
        targets = [e for e in ents if e['n'] == n]
        if not targets:
            print('В bibliography.md нет записи № %d' % n)
            sys.exit(2)
        targets[0]['url'] = args.add[1]

    result = dict(old)
    for e in targets:
        prev = old.get(e['n'])
        if prev and prev.get('ok') and not args.force and not args.add:
            result[e['n']] = prev
            continue
        rec = {k: e[k] for k in ('n', 'key', 'author', 'url')}
        rec.update({'file': None, 'chars': 0, 'ok': False, 'reason': None})
        src = e['url']
        if not src:
            rec['reason'] = 'нет URL/DOI — дословно не цитировать'
            result[e['n']] = rec
            continue
        try:
            if os.path.isfile(src):
                text, err = from_local(src, tmp_pdf)
            else:
                text, err = fetch(src, tmp_pdf)
        except Exception as exc:  # noqa: BLE001 — сеть/сервер: фиксируем причину
            text, err = None, '%s: %s' % (type(exc).__name__, exc)
        if text and len(text) >= MIN_CHARS:
            name = slug(e) + '.txt'
            with open(os.path.join(outdir, name), 'w', encoding='utf-8') as f:
                f.write(text)
            rec.update({'file': name, 'chars': len(text), 'ok': True})
        else:
            rec['reason'] = err or ('текста %d зн. — похоже на заглушку/капчу'
                                    % len(text or ''))
        result[e['n']] = rec
    if os.path.isfile(tmp_pdf):
        os.remove(tmp_pdf)

    srcs = [result[n] for n in sorted(result)]
    json.dump({'sources': srcs}, open(idx_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    ok = [s for s in srcs if s['ok']]
    for s in srcs:
        print('  %3s  %-8s %8s  %s' % (s['n'], 'ok' if s['ok'] else 'нет',
                                       s['chars'] or '', s['file'] or s['reason']))
    print('\nТЕКСТЫ ИСТОЧНИКОВ: скачано %d из %d -> %s' % (len(ok), len(srcs), outdir))


if __name__ == '__main__':
    main()
