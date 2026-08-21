# File-Gate Enforcement Protocol (v4.1, Fable)

Ответ на главный дефект prompt-only оркестрации: модель может «симулировать» выполнение стейджей. v4.1 переводит контроль на проверяемые артефакты: **стейдж считается выполненным только тогда, когда его файлы лежат на диске и `academic-pipeline/scripts/validate_stage_gate.py` вернул PASS (exit 0).**

Протокол совместим с #134 write-scope guard (v3.10+): он НЕ ослабляет фенсы Bucket A агентов, а строится поверх них.

## Роли и права записи (#134)

| Кто | Права | Обязанности в протоколе |
|---|---|---|
| Оркестратор / основная сессия (Bucket D) | без фенса, Bash разрешён | создаёт `ars_run/<slug>/` + `state.json`; собирает канонические копии артефактов из phase-каталогов субагентов; ЕДИНСТВЕННЫЙ, кто запускает валидатор и скрипты destyle |
| `integrity_verification_agent`, `compliance_agent` и др. Bucket C | без фенса | пишут свои отчёты напрямую в `ars_run/<slug>/stage2_5/`, `stage4_5/` |
| Bucket A субагенты (5 рецензентов, draft_writer, formatter, …) | записи только в `allowed_write_globs` из `scripts/ars_phase_scope_manifest.json`; **Bash запрещён** | пишут свои выходы в СВОИ phase-каталоги: рецензенты → `phase1_<slug>/review_<role>.md`, синтезатор → `phase2_<slug>/…`, writer → `phase4_<slug>/…`, formatter → `phase7_<slug>/…` |

⚠️ IRON RULE: не поручать Bucket A агенту запись в `ars_run/` или запуск любого скрипта — гвард это заблокирует, а попытка обойти гвард сама по себе анти-паттерн.

## Рабочая папка прогона

При старте пайплайна оркестратор создаёт `ars_run/<slug>/` (slug — короткое имя работы) и `state.json`:

```json
{
  "paper": "<название>",
  "language": "ru",
  "created": "<ISO-дата>",
  "stages": [
    {"stage": "1", "status": "completed", "gate": "PASS", "ts": "..."},
    {"stage": "2", "status": "in_progress"}
  ]
}
```

`state.json` обновляется при каждом переходе (вместе с Material Passport, если тот включён). Возобновление в новой сессии: прочитать `state.json` → `validate_stage_gate.py <run_dir> --all-completed` → продолжить с первого не-PASS стейджа.

## Карта обязательных артефактов (`ars_run/<slug>/`)

| Stage | Папка | Обязательные файлы | Кто произвёл / кто скопировал |
|---|---|---|---|
| 1 RESEARCH | `stage1/` | `rq_brief.md`, `bibliography.md`, `synthesis.md` | deep-research агенты → оркестратор |
| 2 WRITE | `stage2/` | `paper_config.md`, `outline.md`, `paper_draft.md` | academic-paper агенты (phase-каталоги) → оркестратор |
| 2.5 INTEGRITY | `stage2_5/` | `integrity_report.md` (явный вердикт PASS/FAIL) | integrity_verification_agent (Bucket C, напрямую) |
| 3 REVIEW | `stage3/` | `review_eic.md`, `review_methodology.md`, `review_domain.md`, `review_perspective.md`, `review_devils_advocate.md`, `editorial_decision.md`, `revision_roadmap.md` | 5 субагентов → `phase1_<slug>/`; синтезатор → `phase2_<slug>/`; оркестратор копирует |
| 4 REVISE | `stage4/` | `paper_revised.md`, `response_to_reviewers.md`, `rr_matrix.md` (каждая строка со статусом) | academic-paper → оркестратор |
| 3' RE-REVIEW | `stage3p/` | `re_review_report.md` | reviewer (re-review) → оркестратор |
| 4' RE-REVISE | `stage4p/` | `paper_revised2.md`, `rr_matrix2.md` | academic-paper → оркестратор |
| 4.5 FINAL INTEGRITY | `stage4_5/` | `final_integrity_report.md` (PASS обязателен) | integrity_verification_agent (напрямую) |
| 4.6 VENUE (гейт журнала) | `stage4_6/` | `venue_review.md` (строка `ВЕРДИКТ ГЕЙТА: PASS` обязательна) | скилл `venue-review`, исполняется оркестратором/основной сессией |
| 4.75 DESTYLE (ru) | `stage4_75/` | `paper_destyled.md`, `before.json`, `after.json`, `invariants.json` (verdict=PASS), `destyle_report.md` | ru-academic-destyle, исполняется оркестратором/основной сессией |
| 5 FINALIZE | `stage5/` | `formatting_spec.md` (зафиксированный ответ пользователя: методичка/ГОСТ/журнал/стиль), `final_paper.md` + конвертированные форматы | formatter → `phase7_<slug>/`; оркестратор копирует |
| 6 PROCESS SUMMARY | `stage6/` | `process_summary.md` (+ полный лог гейтов из state.json) | оркестратор |

## Правила гейта (IRON RULES)

1. **Переход между стейджами разрешён только после** `python3 "${CLAUDE_PLUGIN_ROOT}/academic-pipeline/scripts/validate_stage_gate.py" <run_dir> --stage <N>` → PASS. Фактический stdout скрипта включается в чекпоинт.
2. **Артефакт производит тот, кто делал работу** — в своём phase-каталоге. Оркестратор копирует БАЙТ-В-БАЙТ; редактирование при копировании запрещено.
3. **Запрещено генерировать артефакт задним числом** ради прохождения гейта. Нет файла — стейдж не выполнен.
4. **Запрещено пересказывать вывод валидатора без его реального запуска.**
5. **Stage 3 — различимость:** синтезатор запускается только после того, как валидатор подтвердил 5 существующих и попарно различных отчётов (Jaccard по 3-словным шинглам ≤ 35%). FAIL → передиспатчить провинившихся рецензентов свежими субагентами; «подправить отчёты руками» — запрещено.
6. Если Python недоступен, оркестратор явно сообщает о деградированном (prompt-only) режиме и получает подтверждение пользователя.

## Formatting Intake (ask-first, IRON RULE)

Никакой стандарт оформления не предполагается. На интейке и повторно перед Stage 5:

1. Спросить, что регламентирует оформление: **методичка вуза** (запросить файл), **ГОСТ Р 7.0.100-2018 / ГОСТ 7.32-2017**, требования журнала, generic-стиль (APA/Chicago/MLA/IEEE/Vancouver).
2. Методичка первична: извлечь поля, шрифт, интервалы, оформление списка литературы, сноски → `stage5/formatting_spec.md`.
3. Нет документа — предложить варианты, записать выбор с пометкой «подтверждено пользователем».

Stage 5 не начинается без `formatting_spec.md`. Язык(и) аннотации — тоже вопрос интейка, без зашитой языковой пары.

## Stage 4.6 VENUE — интеграционный контракт (гейт целевого журнала)

Пред-подачный барьер под требования целевого журнала. Ставится между Stage 4.5 (контент зафиксирован верификацией) и Stage 4.75 (заморозка стиля): venue проверяет СОДЕРЖАНИЕ, поэтому до стилевой заморозки.

Условие запуска: `style_profile`/конфиг содержит целевой журнал с известным venue-профилем в `C:\Users\Admin\.claude\ars-review\<venue>\` (по умолчанию `nota-bene`). Журнал без профиля → стадия пропускается с явной пометкой в `state.json` (гейт не применяется).

Вход: near-final текст после Stage 4.5. Исполнение: скилл `venue-review`, режим «Пайплайн Stage 4.6», из оркестратора/основной сессии. Логика: каскад фильтров профиля (имитация → самостоятельность → «заявлено=сделано» → доказательность → косметика) + 8-критериальная сетка + AI-детектор. Выход: `stage4_6/venue_review.md` с обязательной финальной строкой `ВЕРДИКТ ГЕЙТА: PASS|FAIL`.

- **PASS** (вердикт ∈ {Доработка→публикация, Принять после правок, Рекомендована}, блоки A/B чек-листа закрыты) → переход к Stage 4.75.
- **FAIL** (сработал fatal-фильтр имитации/самостоятельности либо остались незакрытые major) → возврат на **Stage 4** (доработка по листу правок venue_review), затем 4.5 → 4.6 повторно. Это content-цикл, он законно переоткрывает текст (заморозка наступает только после 4.75).

## Stage 4.75 DESTYLE (ru) — интеграционный контракт

Вход: файл работы после Stage 4.6 (или 4.5, если venue-стадия пропущена) + `terms.txt` (термины из Paper Configuration Record). Исполнение: скилл `ru-academic-destyle`, режим «Пайплайн» (его `references/modes.md` §5), из оркестратора/основной сессии. Гейты: `scan_axes.py --gate` (пороги, ≤3 итераций) и `check_invariants.py` (числа/цитаты/сноски/заголовки/термины) — оба блокирующие. Выход: 5 файлов в `stage4_75/` (см. карту). После PASS текст ЗАМОРОЖЕН — дальше только конвертация формата.
