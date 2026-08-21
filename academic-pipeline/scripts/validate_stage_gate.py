#!/usr/bin/env python3
"""ARS v4.1 (Fable) — блокирующий валидатор файловых гейтов пайплайна.

⚠️ Правило #134: этот скрипт запускает ТОЛЬКО оркестратор / основная сессия
(Bucket D). Bucket A субагентам (рецензенты, draft_writer и т.д.) Bash запрещён
PreToolUse-гвардом (scripts/ars_write_scope_guard.py) — не поручайте им ни запуск
валидатора, ни запись в ars_run/. Субагенты пишут только в свои phaseN_*/ каталоги;
оркестратор собирает канонические копии в ars_run/<slug>/stageN/ и валидирует.

Проверяет, что стейдж реально выполнен: обязательные артефакты существуют
в рабочей папке прогона, не пустые, и проходят содержательные проверки
(вердикты integrity/гейтов, различимость отчётов рецензентов, полнота
R&R-матрицы). Оркестратор НЕ имеет права объявлять стейдж завершённым
и переходить дальше, пока этот скрипт не вернул exit 0.

Использование:
    python3 validate_stage_gate.py <run_dir> --stage 2
    python3 validate_stage_gate.py <run_dir> --stage 3
    python3 validate_stage_gate.py <run_dir> --stage 4.75
    python3 validate_stage_gate.py <run_dir> --all-completed

Коды выхода: 0 = PASS, 1 = FAIL (артефакты отсутствуют/неполны), 2 = ошибка вызова.
"""

import argparse

import json
import os
import re
import subprocess
import sys

# Карта обязательных артефактов: stage -> [(относительный путь, мин. байт)]
REQUIRED = {
    '1': [
        ('stage1/rq_brief.md', 300),
        ('stage1/bibliography.md', 500),
        ('stage1/synthesis.md', 1000),
    ],
    '2': [
        ('stage2/paper_config.md', 300),
        ('stage2/outline.md', 800),
        ('stage2/paper_draft.md', 5000),
    ],
    '2.5': [
        ('stage2_5/integrity_report.md', 500),
    ],
    '3': [
        ('stage3/review_eic.md', 1200),
        ('stage3/review_methodology.md', 1200),
        ('stage3/review_domain.md', 1200),
        ('stage3/review_perspective.md', 1200),
        ('stage3/review_devils_advocate.md', 1200),
        ('stage3/editorial_decision.md', 500),
        ('stage3/revision_roadmap.md', 300),
    ],
    '4': [
        ('stage4/paper_revised.md', 5000),
        ('stage4/response_to_reviewers.md', 800),
        ('stage4/rr_matrix.md', 300),
    ],
    "3'": [
        ('stage3p/re_review_report.md', 800),
    ],
    "4'": [
        ('stage4p/paper_revised2.md', 5000),
        ('stage4p/rr_matrix2.md', 200),
    ],
    '4.5': [
        ('stage4_5/final_integrity_report.md', 500),
    ],
    '4.6': [
        ('stage4_6/venue_review.md', 800),
    ],
    '4.75': [
        ('stage4_75/paper_destyled.md', 5000),
        ('stage4_75/before.json', 10),
        ('stage4_75/after.json', 10),
        ('stage4_75/invariants.json', 10),
        ('stage4_75/destyle_report.md', 300),
    ],
    '5': [
        ('stage5/formatting_spec.md', 200),
        ('stage5/final_paper.md', 5000),
    ],
    '6': [
        ('stage6/process_summary.md', 800),
    ],
}

RR_STATUS = re.compile(r'\b(ACCEPTED|REVISED|REVIEWER_DISAGREE|ACKNOWLEDGED|'
                       r'ПРИНЯТО|ИСПРАВЛЕНО|НЕСОГЛАСИЕ|ОГРАНИЧЕНИЕ)\b')
PASS_TOKEN = re.compile(r'\b(PASS|ПРОЙДЕНО)\b')
FAIL_TOKEN = re.compile(r'\b(FAIL|ПРОВАЛ)\b')


def read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def check_files(run_dir, stage, problems):
    for rel, min_bytes in REQUIRED[stage]:
        p = os.path.join(run_dir, rel)
        if not os.path.isfile(p):
            problems.append(f'{rel}: файл отсутствует')
        elif os.path.getsize(p) < min_bytes:
            problems.append(
                f'{rel}: подозрительно мал ({os.path.getsize(p)} байт, '
                f'минимум {min_bytes}) — стейдж выполнен формально?')


def _shingles(text, n=3):
    words = re.findall(r'[а-яёa-z0-9]+', text.lower())
    return {tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def check_reviews_distinct(run_dir, problems):
    """5 отчётов рецензентов должны быть реально разными текстами.
    Мера: Jaccard по 3-словным шинглам (устойчива к общей лексике домена;
    ловит копипасту и однопроходную симуляцию панели)."""
    names = ['review_eic.md', 'review_methodology.md', 'review_domain.md',
             'review_perspective.md', 'review_devils_advocate.md']
    sh = {}
    for n in names:
        p = os.path.join(run_dir, 'stage3', n)
        if os.path.isfile(p):
            sh[n] = _shingles(read(p))
    keys = list(sh)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = sh[keys[i]], sh[keys[j]]
            if not a or not b:
                continue
            jac = len(a & b) / len(a | b)
            if jac > 0.35:
                problems.append(
                    f'stage3: {keys[i]} и {keys[j]} пересекаются на '
                    f'{round(jac * 100)}% (Jaccard, 3-словные шинглы; порог 35%) '
                    f'— рецензенты не независимы (похоже на симуляцию панели)')


def check_verdict(run_dir, rel, problems, what):
    p = os.path.join(run_dir, rel)
    if not os.path.isfile(p):
        return
    text = read(p)
    if FAIL_TOKEN.search(text) and not PASS_TOKEN.search(text):
        problems.append(f'{rel}: вердикт FAIL — {what} не пройдена')
    elif not PASS_TOKEN.search(text):
        problems.append(f'{rel}: нет явного вердикта PASS — {what} не '
                        f'подтверждена (отчёт обязан содержать строку с PASS/FAIL)')


def check_rr_matrix(run_dir, rel, problems):
    p = os.path.join(run_dir, rel)
    if not os.path.isfile(p):
        return
    rows = [ln for ln in read(p).split('\n')
            if ln.strip().startswith('|') and not set(ln.strip()) <= {'|', '-', ' ', ':'}]
    data_rows = rows[1:] if rows else []
    if len(data_rows) < 1:
        problems.append(f'{rel}: матрица R&R пуста')
        return
    for ln in data_rows:
        if not RR_STATUS.search(ln):
            problems.append(
                f'{rel}: строка без статуса '
                f'(ACCEPTED/REVISED/REVIEWER_DISAGREE/ACKNOWLEDGED): {ln.strip()[:80]}')


def check_destyle(run_dir, problems):
    p = os.path.join(run_dir, 'stage4_75', 'invariants.json')
    if os.path.isfile(p):
        try:
            data = json.loads(read(p))
            if data.get('verdict') != 'PASS':
                problems.append('stage4_75/invariants.json: verdict != PASS — '
                                'дестилизация задела защищённое содержимое')
        except (ValueError, KeyError):
            problems.append('stage4_75/invariants.json: не парсится как JSON')


# --- Лимиты прогона (state.json -> "limits"); дефолты из Execution Discipline ---
DEFAULT_LIMITS = {
    'sources_min': 12,
    'sources_max': 20,
    'target_chars': None,   # целевой объём текста; None = не проверять
    'tolerance': 0.10,      # допуск по объёму (доля)
    'language': None,       # 'ru' включает стилевой гейт
    'style_gate': True,
}

SRC_LINE = re.compile(r'^\s*(?:\[?\d{1,3}[\].)]|[-*•])\s+\S')


def load_limits(run_dir):
    lim = dict(DEFAULT_LIMITS)
    p = os.path.join(run_dir, 'state.json')
    if os.path.isfile(p):
        try:
            st = json.loads(read(p))
        except ValueError:
            return lim
        if isinstance(st.get('language'), str):
            lim['language'] = st['language']
        for k, v in (st.get('limits') or {}).items():
            if k in lim:
                lim[k] = v
    return lim


def count_sources(text):
    """Записи списка литературы: нумерованные или маркированные строки длиной > 30."""
    return sum(1 for ln in text.split('\n')
               if SRC_LINE.match(ln) and len(ln.strip()) > 30)


def check_sources(run_dir, problems, lim):
    p = os.path.join(run_dir, 'stage1', 'bibliography.md')
    if not os.path.isfile(p):
        return
    n = count_sources(read(p))
    if n == 0:
        problems.append('stage1/bibliography.md: не распознано ни одной записи '
                        '(нумерованный или маркированный список)')
        return
    if n > lim['sources_max']:
        problems.append(
            'stage1/bibliography.md: %d источников при потолке %d — разведка вышла '
            'за соразмерность (Execution Discipline §2). Сократить до ядра или '
            'осознанно поднять limits.sources_max в state.json'
            % (n, lim['sources_max']))
    if n < lim['sources_min']:
        problems.append('stage1/bibliography.md: %d источников при минимуме %d — '
                        'база недостаточна' % (n, lim['sources_min']))


def check_volume(run_dir, rel, problems, lim):
    target = lim.get('target_chars')
    if not target:
        return
    p = os.path.join(run_dir, rel)
    if not os.path.isfile(p):
        return
    n = len(read(p))
    pct = int(lim['tolerance'] * 100)
    hi = int(target * (1 + lim['tolerance']))
    lo = int(target * (1 - lim['tolerance']))
    if n > hi:
        problems.append('%s: %d знаков при цели %d (+%d%% = %d) — превышение на %d знаков; '
                        'сокращать сейчас, а не «на потом»' % (rel, n, target, pct, hi, n - hi))
    elif n < lo:
        problems.append('%s: %d знаков при цели %d (-%d%% = %d) — недобор объёма'
                        % (rel, n, target, pct, lo))


def _scan_axes_path():
    cands = []
    env = os.environ.get('ARS_DESTYLE_SCRIPTS')
    if env:
        cands.append(os.path.join(env, 'scan_axes.py'))
    cands.append(os.path.join(os.path.expanduser('~'), '.claude', 'skills',
                              'ru-academic-destyle', 'scripts', 'scan_axes.py'))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def check_style_scan(run_dir, rel, out_rel, problems, lim):
    """Стилевой гейт НА ЭТАПЕ ПИСЬМА: если жанровый профиль не применён,
    оси AI-маркеров вылезут уже в первом черновике, а не на Stage 4.75."""
    lang = (lim.get('language') or '').lower()
    if lang not in ('ru', 'rus', 'russian') or not lim.get('style_gate'):
        return
    src = os.path.join(run_dir, rel)
    if not os.path.isfile(src):
        return
    scan = _scan_axes_path()
    if not scan:
        problems.append(
            'стилевой гейт не выполнен: не найден scan_axes.py '
            '(~/.claude/skills/ru-academic-destyle/scripts/ или $ARS_DESTYLE_SCRIPTS). '
            'Профиль стиля молча не применять — остановиться и доложить пользователю')
        return
    out = os.path.join(run_dir, out_rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        r = subprocess.run([sys.executable, scan, src, '--json', out, '--gate'],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        problems.append('стилевой гейт не запустился: %s' % exc)
        return
    if r.returncode != 0:
        tail = [ln.strip() for ln in (r.stdout or '').split('\n')
                if ln.strip().startswith('FAIL')]
        detail = '; '.join(tail[:6]) or 'пороги превышены'
        problems.append(
            '%s: стилевой гейт FAIL — %s. Значит, жанровый профиль ars-style НЕ был '
            'применён при письме (отчёт: %s). Переписывать по профилю сейчас, '
            'а не откладывать на Stage 4.75' % (rel, detail, out_rel))


def validate(run_dir, stage):
    problems = []
    if stage not in REQUIRED:
        print(f'Неизвестный стейдж: {stage}. Допустимые: {", ".join(REQUIRED)}')
        sys.exit(2)
    check_files(run_dir, stage, problems)
    lim = load_limits(run_dir)
    if stage == '1':
        check_sources(run_dir, problems, lim)
    if stage == '2':
        check_volume(run_dir, 'stage2/paper_draft.md', problems, lim)
        check_style_scan(run_dir, 'stage2/paper_draft.md',
                         'stage2/style_scan.json', problems, lim)
    if stage == '4':
        check_volume(run_dir, 'stage4/paper_revised.md', problems, lim)
    if stage == "4'":
        check_volume(run_dir, 'stage4p/paper_revised2.md', problems, lim)
    if stage == '5':
        check_volume(run_dir, 'stage5/final_paper.md', problems, lim)
    if stage == '2.5':
        check_verdict(run_dir, 'stage2_5/integrity_report.md', problems,
                      'проверка целостности (Stage 2.5)')
    if stage == '3':
        check_reviews_distinct(run_dir, problems)
    if stage == '4':
        check_rr_matrix(run_dir, 'stage4/rr_matrix.md', problems)
    if stage == "4'":
        check_rr_matrix(run_dir, 'stage4p/rr_matrix2.md', problems)
    if stage == '4.5':
        check_verdict(run_dir, 'stage4_5/final_integrity_report.md', problems,
                      'финальная проверка целостности (Stage 4.5)')
    if stage == '4.6':
        check_verdict(run_dir, 'stage4_6/venue_review.md', problems,
                      'venue-гейт целевого журнала (Stage 4.6)')
    if stage == '4.75':
        check_destyle(run_dir, problems)
        check_verdict(run_dir, 'stage4_75/destyle_report.md', problems,
                      'дестилизация (Stage 4.75)')
    return problems


STAGE_ORDER = ['1', '2', '2.5', '3', '4', "3'", "4'", '4.5', '4.6', '4.75', '5', '6']


def ledger(run_dir):
    """Карта прогона для входа в НОВОМ чате: где остановились и что уже на диске.
    Тяжёлые проверки не запускает — только наличие и размер артефактов."""
    print('\n=== ЛЕДЖЕР ПРОГОНА: %s ===\n' % run_dir)
    lim = load_limits(run_dir)
    print('  язык: %s | источники %s-%s | цель объёма: %s знаков (±%d%%)\n'
          % (lim.get('language') or 'не задан', lim['sources_min'], lim['sources_max'],
             lim.get('target_chars') or 'не задана', int(lim['tolerance'] * 100)))
    last_done = None
    for st in STAGE_ORDER:
        req = REQUIRED[st]
        have = [rel for rel, mb in req
                if os.path.isfile(os.path.join(run_dir, rel))
                and os.path.getsize(os.path.join(run_dir, rel)) >= mb]
        if len(have) == len(req):
            mark, last_done = 'ГОТОВО   ', st
        elif have:
            mark = 'ЧАСТИЧНО '
        else:
            mark = '—        '
        print('  Stage %-5s %s %d/%d артефактов' % (st, mark, len(have), len(req)))
    nxt = None
    for st in STAGE_ORDER:
        req = REQUIRED[st]
        if not all(os.path.isfile(os.path.join(run_dir, rel)) for rel, _ in req):
            nxt = st
            break
    print('\n  Последний завершённый: %s' % (last_done or 'нет'))
    print('  Точка входа: Stage %s' % (nxt or 'всё выполнено'))
    print('\n  Перед продолжением в новом чате прогнать:'
          '\n    validate_stage_gate.py %s --stage %s' % (run_dir, last_done or '1'))


def main():
    ap = argparse.ArgumentParser(description='ARS v4.0 валидатор файловых гейтов')
    ap.add_argument('run_dir', help='рабочая папка прогона (ars_run/<slug>)')
    ap.add_argument('--stage', help="стейдж: 1, 2, 2.5, 3, 4, 3', 4', 4.5, 4.6, 4.75, 5, 6")
    ap.add_argument('--all-completed', action='store_true',
                    help='проверить все стейджи, отмеченные completed в state.json')
    ap.add_argument('--ledger', action='store_true',
                    help='карта прогона: что уже на диске и с какого стейджа входить '
                         '(для продолжения в новом чате)')
    args = ap.parse_args()

    if not os.path.isdir(args.run_dir):
        print(f'FAIL: рабочая папка не существует: {args.run_dir}')
        sys.exit(1)

    if args.ledger:
        ledger(args.run_dir)
        return

    stages = []
    if args.all_completed:
        state_path = os.path.join(args.run_dir, 'state.json')
        if not os.path.isfile(state_path):
            print('FAIL: нет state.json — состояние пайплайна не ведётся')
            sys.exit(1)
        state = json.loads(read(state_path))
        stages = [s['stage'] for s in state.get('stages', [])
                  if s.get('status') == 'completed' and s['stage'] in REQUIRED]
    elif args.stage:
        stages = [args.stage]
    else:
        print('Укажите --stage <id> или --all-completed')
        sys.exit(2)

    all_problems = []
    for st in stages:
        probs = validate(args.run_dir, st)
        tag = 'PASS' if not probs else 'FAIL'
        print(f'\n=== Stage {st}: {tag} ===')
        for p in probs:
            print(f'  FAIL  {p}')
        all_problems += probs

    if all_problems:
        print(f'\nИТОГ: FAIL ({len(all_problems)} проблем). '
              f'Переход к следующему стейджу ЗАПРЕЩЁН.')
        sys.exit(1)
    print('\nИТОГ: PASS. Переход к следующему стейджу разрешён.')


if __name__ == '__main__':
    main()
