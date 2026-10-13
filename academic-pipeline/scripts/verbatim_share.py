#!/usr/bin/env python3
"""ARS ProScience — доля дословных заимствований из источников прогона.

Правило (Иван, 13.10.2026): в каждой работе 10–20 % основного текста — куски
источников СЛОВО В СЛОВО, каждый со ссылкой на свой источник. Цель — небольшой
процент заимствований в отчёте Антиплагиата, как у живой работы, опирающейся
на источники. Заимствование видно в отчёте, только если источник есть в базе
системы, поэтому тексты берутся из открытого интернета (stage1/texts/).

Как меряется. Основной текст (без заголовков, таблиц, сносок-определений и
всего, что после заголовка списка литературы) режется на слова; совпадением
считается непрерывный кусок от --min-words слов (по умолчанию 10), который
встречается в одном из текстов stage1/texts/*.txt. Сравнение без учёта
регистра, пунктуации и е/ё. Доля = знаки совпавших кусков / знаки основного
текста — так же, как процент считает отчёт.

Ссылка проверяется по абзацу: в нём должен стоять маркер ИМЕННО этого
источника — [n], [n, с. X], [#key], [@key] или сноска [^k], в тексте которой
есть фамилия автора. Соответствие файл → источник берётся из
stage1/texts/index.json (его пишет fetch_sources.py).

    python3 verbatim_share.py <текст.md> <папка_texts> [--min 10] [--max 20]
                              [--json out.json] [--spans out.txt]

Коды выхода: 0 = в коридоре и всё со ссылками; 1 = вне коридора или есть
куски без ссылки; 2 = мерить нечем (нет текстов источников).
"""

import argparse
import glob
import json
import os
import re
import sys

WORD = re.compile(r'[0-9A-Za-zА-Яа-яЁё]+')
BIB_HEAD = re.compile(
    r'^#{1,6}\s*(?:\d+[.)]?\s*)?(?:список\s+(?:использованн\w+\s+|литератур\w*|источник\w*)|'
    r'библиограф\w*|литература|источники|references|bibliography)',
    re.IGNORECASE)
FN_DEF = re.compile(r'^\[\^([^\]]+)\]:\s*(.*)$')
FN_REF = re.compile(r'\[\^([^\]]+)\]')
BR_CITE = re.compile(r'\[([^\[\]\^][^\[\]]{0,80})\]')


def norm_word(w):
    return w.lower().replace('ё', 'е')


def paragraphs(md_text):
    """Абзацы основного текста + словарь определений сносок."""
    fn_defs = {}
    paras, buf, in_code = [], [], False
    for line in md_text.split('\n'):
        s = line.strip()
        if s.startswith('```') or s.startswith('~~~'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if BIB_HEAD.match(s):
            break
        fm = FN_DEF.match(s)
        if fm:
            fn_defs[fm.group(1)] = fm.group(2)
            if buf:
                paras.append(' '.join(buf))
                buf = []
            continue
        if not s or s.startswith(('#', '|', '<!--', '![')):
            if buf:
                paras.append(' '.join(buf))
                buf = []
            continue
        buf.append(s)
    if buf:
        paras.append(' '.join(buf))
    # определения сносок, идущие после списка литературы, тоже нужны для сверки
    for line in md_text.split('\n'):
        fm = FN_DEF.match(line.strip())
        if fm:
            fn_defs.setdefault(fm.group(1), fm.group(2))
    return paras, fn_defs


def load_index(texts_dir):
    p = os.path.join(texts_dir, 'index.json')
    if not os.path.isfile(p):
        return {}
    try:
        data = json.load(open(p, encoding='utf-8'))
    except ValueError:
        return {}
    out = {}
    for e in data.get('sources', []):
        if e.get('file'):
            out[e['file']] = e
    return out


def cites_of(para, fn_defs):
    nums, keys, fn_texts = set(), set(), []
    for m in BR_CITE.finditer(para):
        for part in re.split(r'[;]', m.group(1)):
            part = part.strip()
            km = re.match(r'[#@]([\w-]+)', part)
            if km:
                keys.add(km.group(1).lower())
                continue
            nm = re.match(r'(\d{1,3})(?:\s*[,–-]|\s*$)', part)
            if nm:
                nums.add(int(nm.group(1)))
    for m in FN_REF.finditer(para):
        fn_texts.append(fn_defs.get(m.group(1), ''))
    return nums, keys, fn_texts


def is_cited(entry, para, fn_defs):
    """True / False / None (None = нечем сверить: файла нет в index.json)."""
    nums, keys, fn_texts = cites_of(para, fn_defs)
    if entry is None:
        return None if (nums or keys or fn_texts) else False
    if entry.get('n') is not None and int(entry['n']) in nums:
        return True
    if entry.get('key') and entry['key'].lower().lstrip('#@') in keys:
        return True
    author = (entry.get('author') or '').lower().replace('ё', 'е')
    if author and any(author in t.lower().replace('ё', 'е') for t in fn_texts):
        return True
    return False


def measure(paper_path, texts_dir, k=6, min_words=10):
    md = open(paper_path, encoding='utf-8', errors='replace').read()
    paras, fn_defs = paragraphs(md)
    toks = []          # по абзацам: [(norm, start, end)]
    grams = {}         # k-грамма -> [(абзац, позиция)]
    for pi, p in enumerate(paras):
        tl = [(norm_word(m.group(0)), m.start(), m.end()) for m in WORD.finditer(p)]
        toks.append(tl)
        for i in range(len(tl) - k + 1):
            grams.setdefault(tuple(w for w, _, _ in tl[i:i + k]), []).append((pi, i))
    covered = [dict() for _ in paras]   # позиция слова -> файл источника
    files = sorted(f for f in glob.glob(os.path.join(texts_dir, '*.txt'))
                   if not os.path.basename(f).startswith('_'))
    for f in files:
        src = open(f, encoding='utf-8', errors='replace').read()
        sw = [norm_word(m.group(0)) for m in WORD.finditer(src)]
        name = os.path.basename(f)
        for i in range(len(sw) - k + 1):
            hit = grams.get(tuple(sw[i:i + k]))
            if hit:
                for pi, pos in hit:
                    for j in range(pos, pos + k):
                        covered[pi].setdefault(j, name)
    spans = []
    for pi, cov in enumerate(covered):
        if not cov:
            continue
        idx = sorted(cov)
        run = [idx[0]]
        for j in idx[1:] + [None]:
            if j is not None and j == run[-1] + 1:
                run.append(j)
                continue
            if len(run) >= min_words:
                src_counts = {}
                for x in run:
                    src_counts[cov[x]] = src_counts.get(cov[x], 0) + 1
                src = max(src_counts, key=src_counts.get)
                a, b = toks[pi][run[0]][1], toks[pi][run[-1]][2]
                spans.append({'para': pi, 'start': a, 'end': b, 'words': len(run),
                              'file': src, 'text': paras[pi][a:b]})
            if j is not None:
                run = [j]
    body_chars = sum(len(p) for p in paras)
    span_chars = sum(s['end'] - s['start'] for s in spans)
    return paras, fn_defs, files, spans, body_chars, span_chars


def main():
    ap = argparse.ArgumentParser(description='Доля дословного текста из источников')
    ap.add_argument('paper')
    ap.add_argument('texts_dir')
    ap.add_argument('--min', type=float, default=10.0, help='нижняя граница, %%')
    ap.add_argument('--max', type=float, default=20.0, help='верхняя граница, %%')
    ap.add_argument('--min-words', type=int, default=10)
    ap.add_argument('--json', dest='json_out')
    ap.add_argument('--spans', dest='spans_out',
                    help='записать найденные куски (по строке) — для защиты на Stage 4.75')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if not os.path.isdir(args.texts_dir):
        print(f'ДОСЛОВНОСТЬ: мерить нечем — нет папки {args.texts_dir}')
        sys.exit(2)
    paras, fn_defs, files, spans, body, got = measure(
        args.paper, args.texts_dir, min_words=args.min_words)
    if not files:
        print(f'ДОСЛОВНОСТЬ: мерить нечем — в {args.texts_dir} нет текстов источников')
        sys.exit(2)
    index = load_index(args.texts_dir)
    uncited, unchecked = [], []
    for s in spans:
        c = is_cited(index.get(s['file']), paras[s['para']], fn_defs)
        s['cited'] = c
        if c is False:
            uncited.append(s)
        elif c is None:
            unchecked.append(s)
    pct = 100.0 * got / body if body else 0.0
    srcs = sorted({s['file'] for s in spans})
    in_corr = args.min <= pct <= args.max
    print(f'ДОСЛОВНО ИЗ ИСТОЧНИКОВ: {pct:.1f} % основного текста '
          f'({got} из {body} зн.), кусков {len(spans)}, источников {len(srcs)}; '
          f'коридор {args.min:g}–{args.max:g} %')
    for s in spans:
        mark = {True: 'ссылка ok', False: 'БЕЗ ССЫЛКИ', None: 'ссылка не сверена'}[s['cited']]
        print(f"  [{mark}] абз. {s['para'] + 1}, {s['words']} сл., {s['file']}: "
              f"«{s['text'][:90]}{'…' if len(s['text']) > 90 else ''}»")
    problems = []
    if pct < args.min:
        problems.append(f'дословного {pct:.1f} % при минимуме {args.min:g} % — добавить куски '
                        f'источников из stage1/texts/ слово в слово, со ссылкой')
    if pct > args.max:
        problems.append(f'дословного {pct:.1f} % при потолке {args.max:g} % — это уже '
                        f'компиляция; пересказать часть кусков своими словами')
    if uncited:
        problems.append(f'{len(uncited)} дословных кусков без ссылки на свой источник в том же '
                        f'абзаце — без ссылки это некорректное заимствование')
    if unchecked:
        print(f'  примечание: {len(unchecked)} кусков из файлов, которых нет в index.json, — '
              f'ссылка есть, но чья, не сверено')
    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump({'pct': round(pct, 2), 'body_chars': body, 'verbatim_chars': got,
                       'min': args.min, 'max': args.max, 'in_corridor': in_corr,
                       'spans': spans, 'problems': problems},
                      f, ensure_ascii=False, indent=1)
    if args.spans_out:
        with open(args.spans_out, 'w', encoding='utf-8') as f:
            for s in spans:
                f.write(s['text'].replace('\n', ' ') + '\n')
    for p in problems:
        print(f'FAIL  {p}')
    print('ВЕРДИКТ ДОСЛОВНОСТИ: ' + ('PASS' if not problems else 'FAIL'))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
