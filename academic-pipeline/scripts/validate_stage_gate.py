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


def validate(run_dir, stage):
    problems = []
    if stage not in REQUIRED:
        print(f'Неизвестный стейдж: {stage}. Допустимые: {", ".join(REQUIRED)}')
        sys.exit(2)
    check_files(run_dir, stage, problems)
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


def main():
    ap = argparse.ArgumentParser(description='ARS v4.0 валидатор файловых гейтов')
    ap.add_argument('run_dir', help='рабочая папка прогона (ars_run/<slug>)')
    ap.add_argument('--stage', help="стейдж: 1, 2, 2.5, 3, 4, 3', 4', 4.5, 4.6, 4.75, 5, 6")
    ap.add_argument('--all-completed', action='store_true',
                    help='проверить все стейджи, отмеченные completed в state.json')
    args = ap.parse_args()

    if not os.path.isdir(args.run_dir):
        print(f'FAIL: рабочая папка не существует: {args.run_dir}')
        sys.exit(1)

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
