# ProScience fork — academic-research-skills

**Версия форка:** 4.2.3
**База:** upstream `v3.21.0` (Cheng-I Wu, CC-BY-NC-4.0, лицензия и авторство сохранены)
**Апстрим:** https://github.com/Imbad0202/academic-research-skills

## Как устроен форк

Форк — это ОДИН коммит поверх апстримного тега. Ветка `ps`, база `v3.21.0`.
Никакой ручной переупаковки: обновление апстрима = перебазирование этого коммита.

```bash
git fetch upstream --tags
git rebase v3.22.0 ps          # подставить новый тег
# разрешить конфликты -> поднять version в .claude-plugin/*.json -> задеплоить
```

Номер версии форка (4.x) НЕ сравним с апстримным (3.x) — база всегда указана в
`base_upstream` в `plugin.json` и в этом файле. Ориентироваться на неё, не на номер.

## Что добавляет слой ProScience

| Файл | Патч |
|---|---|
| `academic-pipeline/SKILL.md` | Stage 4.6 VENUE (блокирующий гейт целевого журнала); Stage 4.75 DESTYLE (ru); file-gate enforcement (`ars_run/<slug>/`, `state.json`, валидатор); INJECTION IRON RULE (дословная вставка style/venue-блоков в пишущих суб-агентов); Execution Discipline; ask-first formatting intake |
| `academic-pipeline/references/file_gate_protocol.md` | карта артефактов по стадиям + контракт Stage 4.6 |
| `academic-pipeline/scripts/validate_stage_gate.py` | блокирующий валидатор стадий: `4.6` + `ВЕРДИКТ ГЕЙТА: PASS`; **потолок источников** (Stage 1), **бюджет объёма** ±10 % (Stage 2/4/4'/5), **ранний стилевой гейт** `scan_axes.py --gate` по черновику Stage 2 для ru, режим `--ledger` для входа в новом чате |
| `academic-paper/SKILL.md` | ГОСТ Р 7.0.100-2018 в списке форматов; ask-first formatting intake; настраиваемый языковой набор аннотации вместо зашитого zh-TW+EN |
| `academic-paper/agents/intake_agent.md` | Step 9 (вопросы про авторов отключены — всегда плейсхолдеры), Step 10 (style_profile задан файлами `ars-style/`), Step 10b (детекция venue → venue_profile) |
| `academic-paper/agents/draft_writer_agent.md` | жёсткое style+venue enforcement с self-fetch fallback |
| `shared/style_calibration_protocol.md` | приоритет локальных жанровых профилей стиля |
| `commands/ars-destyle.md` | слэш-команда дестилизации |
| `academic-pipeline/SKILL.md` Stage 5 | сборка .docx через pandoc с шаблоном `~/.claude/ars-docx/reference_<id>.docx` (журнал или ГОСТ); самодельная сборка .docx запрещена |
| `agents/*.md` | три plugin-агента переименованы без подчёркиваний (требование валидатора установки) |
| `hooks/hooks.json` | SessionStart-баннер снят: он печатал ~2,1 КБ в КАЖДУЮ сессию любого проекта. PreToolUse write-scope guard оставлен |

## Что НЕ переносится из старой сборки 4.1.x (и почему)

- **«Разведчиков — на Sonnet 5».** Заменено на штатный `ARS_MODEL_TIERING` (upstream #517).
  Апстрим классифицирует `research_question`, `research_architect`, `synthesis`,
  `source_verification`, `literature_strategist` как judgment-type — только модель сессии,
  и держит пол Opus-class для всех понижаемых агентов. Старое правило опускало ниже пола
  ровно тех агентов, что собирают доказательную базу.
- **Самодельный distinctness-гейт рецензентов (v2.1 overlay в `academic-paper-reviewer`).**
  У апстрима с 3.17.0 есть исполняемый panel checker (`scripts/check_panel_synthesis.py`,
  `scripts/check_phase_conformance.py`) + role-separated seats с pinned output grammar.
  Файл возвращён к апстримному состоянию.
- **Ре-нумерация «v4.1.0 (Fable, base 3.14.0)» внутри SKILL.md.** Версии скиллов —
  апстримные; версия форка живёт только в манифестах.

## Зависимости на машине

`~/.claude/ars-style/` (жанровые профили стиля) и `~/.claude/ars-review/<venue>/`
(venue-профили журналов). Без них соответствующие агенты обязаны остановиться и
сообщить пользователю, а не писать «по памяти» — правило зашито в патчи.
