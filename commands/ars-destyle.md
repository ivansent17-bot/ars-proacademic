---
description: ARS destyle — снять AI-маркеры с русского академического текста (12 осей + скрипт-гейты)
model: opus
---

Trigger the standalone `ru-academic-destyle` skill (companion to this plugin; installed separately). Mode is auto-selected by input type: chat fragment → минимальная хирургия; attached .docx/.md/.txt → полный документ; dispatched by `academic-pipeline` Stage 4.75 → pipeline mode. File inputs REQUIRE the verifiable cycle: `scan_axes.py --json before` → edit → `scan_axes.py --gate --compare` → `check_invariants.py`; both gates blocking. Scripts run from the main session / orchestrator only (#134: Bucket A agents have no Bash).

Mode reference: `MODE_REGISTRY.md` § ru-academic-destyle.
Pipeline stage contract: `academic-pipeline/references/file_gate_protocol.md` § Stage 4.75.
