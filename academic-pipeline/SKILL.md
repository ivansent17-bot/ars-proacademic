---
name: academic-pipeline
description: "Orchestrator for the full academic research pipeline: research -> write -> integrity check -> review -> revise -> re-review -> re-revise -> final integrity check -> finalize. Coordinates deep-research, academic-paper, and academic-paper-reviewer into a seamless 10-stage workflow with mandatory, coverage-bounded integrity checks, two-stage peer review, and auditable quality-assurance artifacts. Triggers on: academic pipeline, research to paper, full paper workflow, paper pipeline, end-to-end paper, research-to-publication, complete paper workflow, 연구부터 논문까지, 연구 주제 설정부터 논문 완성까지, 논문 전체 워크플로."
metadata:
  version: "3.21.0"
  last_updated: "2026-08-18"
  depends_on: "deep-research, academic-paper, academic-paper-reviewer, ru-academic-destyle (ru papers)"
  status: active
  data_access_level: raw
  task_type: open-ended
  related_skills:
    - deep-research
    - academic-paper
    - academic-paper-reviewer
    - ru-academic-destyle
---

# Academic Pipeline v3.21.0 — Full Academic Research Workflow Orchestrator

A lightweight orchestrator that manages the complete academic pipeline from research exploration to final manuscript. It does not perform substantive work — it only detects stages, recommends modes, dispatches skills, manages transitions, and tracks state.

> **Routing discipline (v3.9.2):** see `.claude/CLAUDE.md` "Routing Discipline (v3.9.2)" + `shared/references/intent_clarification_protocol.md` for cross-skill routing rules. This skill assumes routing has already settled — ambiguous cross-phase materials should have been clarified upstream.

**v3.6.3 (opt-in):** Set `ARS_PASSPORT_RESET=1` to promote FULL checkpoints to context-reset boundaries. Use `resume_from_passport=<hash>` in a fresh session to continue from the recorded stage. See [`references/passport_as_reset_boundary.md`](references/passport_as_reset_boundary.md).

**v3.8 (opt-in):** Set `ARS_CLAIM_AUDIT=1` to enable the L3 claim-faithfulness audit gate at the Stage 4 → Stage 5 transition. When the flag is set, the orchestrator dispatches `claim_ref_alignment_audit_agent` after the v3.7.1 Cite-Time Provenance Finalizer and before `formatter_agent`'s hard gate. The audit emits `claim_audit_results[]` + `uncited_assertions[]` + `claim_drifts[]` + `constraint_violations[]` + `audit_sampling_summaries[]` aggregates per the 8-row matrix; HIGH-WARN classes gate-refuse output via the formatter REFUSE rules 6-10. Default OFF for v3.8.0 — ramp-on plan deferred to post-calibration evidence (spec §5 mode flag rationale). See `agents/claim_ref_alignment_audit_agent.md` and the orchestrator §3.6 prose.

**v4.1 (Fable) Core Changes — enforcement rework:**

1. ⚠️ **File-Gate Enforcement** — every stage MUST materialize its deliverables as files in the run directory `ars_run/<slug>/` and pass `python3 "${CLAUDE_PLUGIN_ROOT}/academic-pipeline/scripts/validate_stage_gate.py" <run_dir> --stage <N>` (exit 0) before the pipeline may advance. The validator's actual stdout is shown at the checkpoint. See `references/file_gate_protocol.md`.
2. ⚠️ **Guard-compliant write paths (#134)** — Bucket A subagents keep writing ONLY inside their `allowed_write_globs` (e.g. reviewers → `phase1_*/**`, synthesizer → `phase2_*/**`; Bash denied for Bucket A). The unfenced orchestrator (Bucket D) collects canonical copies into `ars_run/<slug>/stageN/` at stage completion and is the ONLY entity that runs the validator via Bash.
3. ⚠️ **Real subagent dispatch** — Stage 3's five reviewers and Stage 2.5/4.5 integrity verification run as separate clean-context subagents, each writing its own report file. Inline role-play simulation of the panel is a named anti-pattern; the validator's report-similarity check catches it.
4. **Stage 4.75 DESTYLE (ru)** — for Russian-language papers, the standalone `ru-academic-destyle` skill (pipeline mode) runs between FINAL INTEGRITY (4.5) and FINALIZE (5) with two blocking script gates (`scan_axes.py --gate`, `check_invariants.py`). Non-Russian papers skip it with an explicit `state.json` note. After 4.75 the substantive text is FROZEN.
5. ⚠️ **Formatting Intake (ask-first)** — no formatting/citation standard is ever assumed. The orchestrator asks for the governing document (университетская методичка / GOST R 7.0.100-2018 / GOST 7.32 / journal guidelines / APA etc.) at intake and re-confirms before Stage 5; the confirmed answer is recorded in `stage5/formatting_spec.md`. Stage 5 does not start without it.
6. **Pipeline-mode dedup** — inside the pipeline, `academic-paper` Phase 6 (in-pair evaluator) is skipped: Stage 3's external 5-reviewer panel is the single review layer (standalone `academic-paper full` keeps Phase 6).

**v2.0 Core Improvements**:
1. **Mandatory user confirmation checkpoints** — Each stage completion requires user confirmation before proceeding to the next step
2. **Academic integrity checks** — After paper completion and before review submission, run the declared reference, registered-claim, and reported-data checks; expose denominators, sampling, unknown states, and blocking verdicts
3. **Two-stage review** — First full review + post-revision focused verification review
4. **Final integrity check** — After revision completion, rerun the final-check contract from fresh inputs; `100%` applies only where the named registered population is explicitly complete
5. **Auditable** — Version, hash, and retain workflow artifacts; deterministic checks are replayable, while generative outputs are not promised byte-identical
6. **Process documentation** — Stage 6 generates a "Paper Creation Process Record" PDF documenting the human-AI collaboration history (delivered before the terminal acknowledgement that completes the pipeline)

## Quick Start

**Full workflow (from scratch):**
```
I want to write a research paper on the impact of AI on higher education quality assurance
```
--> academic-pipeline launches, starting from Stage 1 (RESEARCH)

**Mid-entry (existing paper):**
```
I already have a paper, help me review it
```
--> academic-pipeline detects mid-entry, starting from Stage 2.5 (INTEGRITY)

**Revision mode (received reviewer feedback):**
```
I received reviewer comments, help me revise
```
--> academic-pipeline detects, starting from Stage 4 (REVISE)

**Resume from passport (cross-session context reset, opt-in):**
```
resume_from_passport=<hash> [stage=<n>] [mode=<m>]
```
--> Loads the Material Passport (Schema 9), locates the `kind: boundary` entry matching `<hash>`, and confirms it has no later `kind: resume` entry consuming it. If `pending_decision` is set, the decision prompt fires first to capture the user's branch choice for the audit ledger; the prompt is never skipped, even when the user supplies `stage=`. After the prompt (or immediately if no `pending_decision`), the next stage is determined by: (a) `stage=<n>` CLI override if provided, else (b) the matched option's `next_stage`, else (c) the `next` field recorded in the boundary entry. CLI `stage=`/`mode=` overrides win over option routing.
- **Gate (emit)**: `ARS_PASSPORT_RESET=1` must be set in the emitting session. Without the flag, no `kind: boundary` entries are written and there is nothing to resume from.
- **Gate (resume)**: No flag required. Any session can invoke `resume_from_passport=<hash>` against a passport that carries a valid boundary entry matching the hash.
- **Intent**: Invoke in a *fresh* Claude Code session. Resuming within the same session that emitted the boundary provides no token savings and may drop still-live in-session context.
- **Stage**: Any. Resumes at whatever stage the routing rules above determine.
- **Reference**: [`references/passport_as_reset_boundary.md`](references/passport_as_reset_boundary.md) — see §"`resume_from_passport` mode contract".

**Execution flow:**
1. Detect the user's current stage and available materials
2. **Create run directory `ars_run/<slug>/` + `state.json`; run Formatting Intake (ask-first); detect paper language (ru → Stage 4.75 in route)**
3. Recommend the optimal mode for each stage
4. Dispatch the corresponding skill for each stage (clean-context subagents where required)
5. **After each stage: collect artifacts into `ars_run/<slug>/stageN/` → run `validate_stage_gate.py` → include its output in the checkpoint → wait for user confirmation**
6. Track progress throughout; Pipeline Status Dashboard available at any time

---

## Trigger Conditions

### Trigger Keywords

**English**: academic pipeline, research to paper, full paper workflow, paper pipeline, end-to-end paper, research-to-publication, complete paper workflow

**한국어**: 학술 파이프라인, 연구부터 논문까지, 논문 전체 워크플로, 연구 주제 설정부터 논문 완성까지, 연구-논문 전 과정

### Non-Trigger Scenarios

| Scenario | Skill to Use |
|----------|-------------|
| Only need to search materials or do a literature review | `deep-research` |
| Only need to write a paper (no research phase needed) | `academic-paper` |
| Only need to review a paper | `academic-paper-reviewer` |
| Only need to check citation format | `academic-paper` (citation-check mode) |
| Only need to convert paper format | `academic-paper` (format-convert mode) |
| Only need to remove AI-style markers from Russian text | `ru-academic-destyle` (standalone) |

### Trigger Exclusions

- If the user only needs a single function (just search materials, just check citations), no pipeline is needed — directly trigger the corresponding skill
- If the user is already using a specific mode of a skill, respect that entry point; the pipeline is opt-in
- The pipeline is optional, not mandatory

---

## Pipeline Stages (11 Stages)

| Stage | Name | Skill / Agent Called | Available Modes | Deliverables |
|-------|------|---------------------|----------------|-------------|
| 1 | RESEARCH | `deep-research` | socratic, full, quick | RQ Brief, Methodology, Bibliography, Synthesis |
| 2 | WRITE | `academic-paper` | plan, full | Paper Draft |
| **2.5** | **INTEGRITY** | **`integrity_verification_agent`** | **pre-review** | **Integrity verification report + corrected paper** |
| 3 | REVIEW | `academic-paper-reviewer` | full (incl. Devil's Advocate) | 5 review reports + Editorial Decision + Revision Roadmap |
| 4 | REVISE | `academic-paper` | revision | Revised Draft, Response to Reviewers |
| **3'** | **RE-REVIEW** | **`academic-paper-reviewer`** | **re-review** | **Verification review report: revision response checklist + residual issues** |
| **4'** | **RE-REVISE** | **`academic-paper`** | **revision** | **Second revised draft (if needed)** |
| **4.5** | **FINAL INTEGRITY** | **`integrity_verification_agent`** | **final-check** | **Final verification report (declared checks must PASS; registered denominators and unknown/out-of-scope states remain visible)** |
| **4.6** | **VENUE (гейт журнала)** | **`venue-review`** | **pipeline Stage 4.6** | **`stage4_6/venue_review.md`: пред-подачное рецензирование под целевой журнал (venue-профиль в `~/.claude/ars-review/<venue>/`); строка `ВЕРДИКТ ГЕЙТА: PASS` обязательна; FAIL → возврат на Stage 4; журнал без профиля → пропуск с пометкой в state** |
| **4.75** | **DESTYLE (ru only)** | **`ru-academic-destyle`** | **pipeline** | **`stage4_75/`: destyled paper + before/after.json + invariants.json + destyle report; both script gates must PASS; skipped with state note for non-ru papers** |
| 5 | FINALIZE | `academic-paper` | format-convert | Final Paper (default MD; DOCX via Pandoc when available, otherwise conversion instructions; ask about LaTeX; confirm correctness; PDF) |
| **6** | **PROCESS SUMMARY** | **orchestrator** | **auto** | **Paper creation process record MD + LaTeX to PDF (bilingual)** |

**Parallelization opportunity (v3.3)**: Within Stage 2, the `academic-paper` skill's Phase 1 (literature_strategist_agent) and the `visualization_agent` can operate in parallel after Phase 2 (structure_architect_agent) completes the outline. Specifically:
- Once the outline includes a visualization plan, `visualization_agent` can begin figure generation
- Simultaneously, `argument_builder_agent` can build CER chains
- `draft_writer_agent` waits for both to complete before beginning Phase 4

This mirrors PaperOrchestra's parallel execution of Plot Generation (Step 2) and Literature Review (Step 3) after Outline (Step 1), which reduces overall pipeline latency. The parallelization is optional — sequential execution remains the default for simplicity.

---

## Pipeline State Machine

1. **Stage 1 RESEARCH** -> user confirmation -> Stage 2
2. **Stage 2 WRITE** -> user confirmation -> Stage 2.5
3. **Stage 2.5 INTEGRITY** -> PASS -> Stage 3 (FAIL -> fix and re-verify, max 3 rounds; then Integrity Check FAIL Loop -> recorded user decision)
4. **Stage 3 REVIEW** -> Accept -> Stage 4.5 / Minor|Major -> Stage 4 / Reject -> Stage 2 or end
5. **Stage 4 REVISE** -> user confirmation -> Stage 3'
6. **Stage 3' RE-REVIEW** -> Accept|Minor -> Stage 4.5 / Major -> Stage 4'
7. **Stage 4' RE-REVISE** -> user confirmation -> Stage 4.5 (no return to review)
8. **Stage 4.5 FINAL INTEGRITY** -> PASS (zero issues) -> Stage 4.6 if the target journal has a venue profile / else Stage 4.75 (ru) / else Stage 5 (FAIL -> fix and re-verify; after 3 unresolved rounds -> Integrity Check FAIL Loop -> recorded user decision)
8a. **Stage 4.6 VENUE (гейт журнала)** -> `ВЕРДИКТ ГЕЙТА: PASS` -> Stage 4.75 (ru) / Stage 5 otherwise. FAIL -> Stage 4 (доработка по venue_review, затем 4.5 -> 4.6 повторно). Пропускается для журналов без venue-профиля с пометкой в state
9. **Stage 4.75 DESTYLE (ru)** -> both script gates PASS -> user confirmation -> Stage 5. Substantive text is FROZEN after this stage; any later content change reopens the pipeline at Stage 4.5
10. **Stage 5 FINALIZE** -> `formatting_spec.md` confirmed -> MD -> DOCX via Pandoc when available (otherwise instructions) -> ask about LaTeX -> confirm -> PDF -> completion checkpoint (FULL) -> Stage 6 (user may decline Stage 6: marked `skipped`, pipeline goes directly to `completed`)
11. **Stage 6 PROCESS SUMMARY** -> ask language version -> generate process record MD -> LaTeX -> PDF -> terminal acknowledgement (`finish` / `end` / `done` / `confirm`, or an unambiguous natural-language equivalent) -> pipeline global state `completed`

See `references/pipeline_state_machine.md` for complete state transition definitions. **v4.1**: every transition additionally requires `validate_stage_gate.py` PASS for the completed stage (`references/file_gate_protocol.md`).

---

## Adaptive Checkpoint System

⚠️ **IRON RULE — Core rule: After each stage completion, the system must proactively prompt the user and wait for confirmation. The checkpoint presentation adapts based on context and user engagement.**

### Checkpoint Types

| Type | When Used | Content |
|------|-----------|---------|
| FULL | First checkpoint; after integrity boundaries; Stage 5 completion (final-deliverable acceptance) | Full deliverables list + decision dashboard + all options |
| SLIM | After 2+ consecutive "continue" responses on non-critical stages | One-line status + explicit continue/pause prompt |
| MANDATORY | Integrity FAIL; Review decision; Stage 4.75 gate FAIL; Stage 5 entry gate (before finalization) | Cannot be skipped; requires explicit user input |

### Decision Dashboard (shown at FULL checkpoints)

```
━━━ Stage [X] [Name] Complete ━━━

Gate: validate_stage_gate.py --stage [X] → [PASS/FAIL]
[actual validator output lines]

Metrics:
- Word count: [N] (target: [T] +/-10%)    [OK/OVER/UNDER]
- References: [N] (min: [M])              [OK/LOW]
- Coverage: [N]/[T] sections drafted       [COMPLETE/PARTIAL]
- Criterion status: [named criterion + evidence-anchored categorical judgement, or `NOT_COMPARABLE`]

Deliverables:
- [Material 1]
- [Material 2]

Flagged: [any issues detected, or "None"]

Ready to proceed to Stage [Y]? You can also:
1. View progress (say "status")
2. Adjust settings
3. Pause pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Adaptive Rules

1. **First checkpoint**: always FULL
2. **After 2+ consecutive "continue" without review**: prompt user awareness ("You've continued [N] times in a row. Want to review progress?")
3. **Integrity boundaries (Stage 2.5, 4.5) and destyle gates (Stage 4.75)**: always MANDATORY
4. **Review decisions (Stage 3, 3')**: always MANDATORY
5. **Before finalization (Stage 5 entry gate)**: always MANDATORY — this is the checkpoint between Stage 4.5 PASS and the Stage 5 dispatch, where the user explicitly confirms proceeding and makes the finalization-format decision (citation style); the in-stage LaTeX question and content confirmation stay inside Stage 5 execution. The Stage 5 completion checkpoint (Final Paper delivered, before Stage 6) is FULL — never SLIM. See `references/pipeline_state_machine.md` § Stage 5 boundary semantics
6. **All other stages**: start FULL, downgrade to SLIM if user says "just continue"

### Checkpoint Rules

1. ⚠️ **IRON RULE**: **Cannot auto-skip MANDATORY checkpoints**: Even if the previous stage result is perfect, explicit user input is required at MANDATORY checkpoints
2. **User can adjust**: At FULL and MANDATORY checkpoints, users can modify the mode or settings for the next step
3. **Pause-friendly**: Users can pause at any checkpoint and resume later
4. **SLIM mode**: If the user says "just continue" or "fully automatic," subsequent non-critical checkpoints switch to SLIM format (one-line status + explicit continue/pause prompt)
5. **Awareness guard**: After 4+ consecutive continue responses, the system inserts a FULL checkpoint regardless of stage type to ensure user remains engaged

### Self-Check Questions (at every FULL checkpoint)

Before presenting the checkpoint to the user, the orchestrator asks itself:

1. **Citation integrity**: Are there any unverified citations in the latest output?
2. **Sycophantic concession**: Did the latest stage uncritically accept all feedback without pushback?
3. **Criterion trajectory**: For each applicable named criterion, did the evidence-anchored status improve, remain unchanged, regress, or become non-comparable? Never reduce this to a hidden scalar or `latest >= previous`. Pause and flag any unresolved decision-bearing regression; use `NOT_COMPARABLE` when the criterion or evidence base changed.
4. **Scope discipline**: Did the latest stage add content not requested by the user or the revision roadmap?
5. **Completeness**: Are all required deliverables for this stage present ON DISK in `ars_run/<slug>/` (not merely mentioned in chat)?

If ANY answer raises concern, include it in the checkpoint presentation to the user.

---

## Agent Team (5 Agents)

| # | Agent | Role | File |
|---|-------|------|------|
| 1 | `pipeline_orchestrator_agent` | Main orchestrator: detects stage, recommends mode, triggers skill, manages transitions | `agents/pipeline_orchestrator_agent.md` |
| 2 | `state_tracker_agent` | State tracker: records completed stages, produced materials, revision loop count | `agents/state_tracker_agent.md` |
| 3 | `integrity_verification_agent` | Integrity checker: coverage-bounded reference, citation, registered-claim, and reported-data checks (blocking verdicts are explicit) | `agents/integrity_verification_agent.md` |
| 4 | `collaboration_depth_agent` | **Observer (advisory only — never blocks).** Reads dialogue log and scores user-AI collaboration pattern against `shared/collaboration_depth_rubric.md`. Invoked at FULL/SLIM checkpoints and during Stage 6 record compilation (whole-pipeline pass, before the Process Record is delivered). Based on Wang & Zhang (2026). | `agents/collaboration_depth_agent.md` |
| 5 | `claim_ref_alignment_audit_agent` | **Opt-in claim faithfulness auditor (v3.8 #103).** Audits sampled citations for claim ↔ reference alignment + negative-constraint compliance; emits per-claim `claim_audit_results[]`, `claim_drift[]`, `uncited_assertions[]`, `constraint_violations[]`. Dispatched via orchestrator §3.6 when claim_audit mode is requested. | `agents/claim_ref_alignment_audit_agent.md` |

---

## Orchestrator Workflow

### Step 1: INTAKE & DETECTION

```
pipeline_orchestrator_agent analyzes the user's input:

1. What materials does the user have?
   - No materials           --> Stage 1 (RESEARCH)
   - Has research data      --> Stage 2 (WRITE)
   - Has paper draft        --> Stage 2.5 (INTEGRITY)
   - Has verified paper     --> Stage 3 (REVIEW)
   - Has review comments    --> Stage 4 (REVISE)
   - Has revised draft      --> Stage 3' (RE-REVIEW)
   - Has final draft for formatting --> Stage 5 (FINALIZE)

2. What is the user's goal?
   - Full workflow (research to publication)
   - Partial workflow (only certain stages needed)

3. Paper language? (ru --> Stage 4.75 DESTYLE is in the route)

4. Formatting Intake (ask-first): методичка / GOST / journal guidelines / generic style?

5. БЮДЖЕТ ПРОГОНА (обязателен до старта, IRON RULE): целевой объём текста в знаках,
   потолок и минимум источников. Значения подтверждает пользователь; дефолты —
   12-20 источников, объём из требований журнала/методички.

6. Create ars_run/<slug>/ + state.json; determine entry point, confirm with user

   state.json ОБЯЗАН содержать (иначе гейты работают вслепую):
     {"slug": "...", "language": "ru|en|...",
      "limits": {"sources_min": 12, "sources_max": 20,
                 "target_chars": <из требований>, "tolerance": 0.10},
      "stages": []}
   Эти числа проверяются блокирующе: Stage 1 — количество источников,
   Stage 2/4/4'/5 — объём текста, Stage 2 (ru) — стилевой гейт scan_axes.py.
```

### Возобновление в новом чате (Resume Protocol) ⚠️ IRON RULE

Прогон переживает смену чата: всё состояние на диске. Входя в новую сессию по
существующему прогону, НЕ переделывать сделанное и НЕ пересобирать контекст пересказом:

```
python3 "${CLAUDE_PLUGIN_ROOT}/academic-pipeline/scripts/validate_stage_gate.py" <run_dir> --ledger
```

Ледджер печатает, какие стадии закрыты, какая точка входа и каков бюджет прогона.
Затем перепроверить последний закрытый стейдж (`--stage <N>`) и продолжить со следующего.
Повторный прогон уже закрытых стадий «чтобы убедиться» — запрещён: для этого и существуют
артефакты и гейты. Если результат стадии не устраивает по существу — это возврат на неё
с явным решением пользователя, а не молчаливый переписывающий дубль.

### Step 2: MODE RECOMMENDATION

```
Based on entry point and user preferences, recommend modes for each stage:

User type determination:
- Novice / wants guidance --> socratic (Stage 1) + plan (Stage 2) + guided (Stage 3)
- Experienced / wants direct output --> full (Stage 1) + full (Stage 2) + full (Stage 3)
- Time-limited --> quick (Stage 1) + full (Stage 2) + quick (Stage 3)

Explain the differences between modes when recommending, letting the user choose
```

### Step 3: STAGE EXECUTION

```
Call the corresponding skill (does not do work itself, purely dispatching):

1. Inform the user which Stage is about to begin
2. Load the corresponding skill's SKILL.md
3. Launch the skill with the recommended mode
4. Monitor stage completion status

After completion:
1. Collect deliverables as FILES into ars_run/<slug>/stageN/ (orchestrator copies
   Bucket A outputs from their phase directories — see file_gate_protocol.md)
2. Run: python3 "${CLAUDE_PLUGIN_ROOT}/academic-pipeline/scripts/validate_stage_gate.py" <run_dir> --stage <N>  (orchestrator only;
   Bucket A agents have no Bash). FAIL --> stage is NOT complete; fix or re-dispatch
3. Update pipeline state (call state_tracker_agent; record gate verdict in state.json)
4. [MANDATORY] Proactively prompt checkpoint (include validator stdout), wait for user confirmation
```

### Step 4: TRANSITION

```
After user confirmation:

1. Pass the previous stage's deliverables as input to the next stage
2. Trigger handoff protocol (defined in each skill's SKILL.md):
   - Stage 1  --> 2: deep-research handoff (RQ Brief + Methodology Blueprint + Bibliography + Synthesis)
   - #672 cargo on every transition: exact builder-produced `preregistration-artifact/1.0` receipt and its named companion when provided; validate and carry byte-for-byte
   - **INJECTION IRON RULE: when dispatching ANY writing/revising subagent (Stage 2 draft, Stage 4/4' revision, Stage 5 formatting), the orchestrator pastes VERBATIM into the subagent prompt: (a) `C:\Users\Admin\.claude\ars-style\INJECT_STYLE_BLOCK.md` for Russian papers, and (b) `C:\Users\Admin\.claude\ars-review\<venue>\INJECT_VENUE_BLOCK.md` when venue_profile is set. Never paraphrase these blocks — copy the file contents. Subagents have a self-fetch fallback, but the orchestrator not pasting them is a protocol violation.**
   - Stage 2  --> 2.5: Pass complete paper to integrity_verification_agent
   - Stage 2.5 --> 3: Pass the Stage 2.5 paper to reviewer (verified, or carrying the recorded FAIL-loop partially-unverified warning)
   - Stage 3  --> 4: Pass Revision Roadmap to academic-paper revision mode
   - Stage 4  --> 3': Pass revised draft, the hard-required original pre-revision draft (#576 current 1.1 §3.1 Phase 2A comparison base), exact author-adjudication sidecar, fully replayed Revision-Evidence Bundle, Response to Reviewers, Editorial Decision Letter, Round-1 findings, the immutable Roadmap, the exact ordered patch/report pairs projected by the bundle, and Round-1 Reviewer Configuration Cards. Missing original/roadmap/author/bundle is `manifest_incomplete`; this is the default contract re-review transfer. A user-requested fresh full review at 3' remains a separate full-mode branch.
   - Stage 3' --> 4': Pass new Revision Roadmap + R&R Traceability Matrix (Schema 11) to academic-paper revision mode; the traceability sidecar (frozen `previously_missed`/`indeterminate` records, #576 §8) rides through 4' toward Stage 4.5
   - Stage 3' --> 4.5 (Accept/Minor direct path): Pass verified revised draft + the traceability sidecar's frozen records to integrity_verification_agent as gate input
   - Stage 4/4' --> 4.5: Pass revision-completed paper to integrity_verification_agent (final verification); on the Major-via-4' path the Stage 3' traceability sidecar travels along as gate input
   - Stage 4.5 --> 5: Pass the accepted final draft (verified, or carrying the recorded FAIL-loop partially-unverified warning) to the one mandatory Stage-5 entry checkpoint; run #660 then #672 against that same accepted artifact ID/SHA-256 before format-convert dispatch
   - Stage 5  --> 6: Pass final deliverables list + the Process-Summary projection of pipeline state history, omitting the #673 activity projection of terminal root `run_id`, pending/sealed activity fields, selected-store data, renderer output, and diagnostics (user may decline Stage 6 at the Stage 5 completion checkpoint)
   - Stage 4.5 --> 4.6 (target journal has venue profile): Pass verified paper + venue-id (default nota-bene) to venue-review (pipeline Stage 4.6 mode); it reads `C:\Users\Admin\.claude\ars-review\<venue>\` and gates on `ВЕРДИКТ ГЕЙТА`. FAIL routes back to Stage 4 with the venue fix-list
   - Stage 4.6 --> 4.75 (ru) / 5 (non-ru): on PASS, pass paper forward
   - Stage 4.5/4.6 --> 4.75 (ru papers): Pass verified paper + terms.txt + genre (ВАК-статья/ВКР/кандидатская/курсовая, from Paper Configuration Record) to ru-academic-destyle (pipeline mode); destyle reads the matching genre profile in `C:\Users\Admin\.claude\ars-style\` as its positive target
   - Stage 4.75 --> 5: Pass stage4_75/paper_destyled.md to format-convert mode (per stage5/formatting_spec.md)
   - Stage 4.5/4.6 --> 5 (non-ru): Pass verified final draft to format-convert mode
3. Begin next stage
```

### Mid-Conversation Reinforcement Protocol

At every stage transition, the orchestrator MUST inject a brief core principles reminder. This prevents context rot in long conversations.

**Template** (adapt to the upcoming stage):

````
--- STAGE TRANSITION: [Current] → [Next] ---

🔄 Core Principles Reinforcement:
1. [Most relevant IRON RULE for the next stage]
2. [Most relevant Anti-Pattern to avoid in the next stage]
3. Gate check: validate_stage_gate.py PASS recorded for [Current Stage]? If not, DO NOT TRANSITION.
4. Quality check: Is the output of [Current Stage] at least as good as [Previous Stage]? If not, PAUSE.

Checkpoint: [MANDATORY/ADVISORY] — [What user needs to confirm]
---
````

**Stage-specific reinforcement content**: See `references/reinforcement_content.md` for the full transition → reinforcement focus table.

---

## Phase-by-phase Invocation Contract (v3.9.2)

academic-pipeline is the orchestrator skill that coordinates the full ARS pipeline across 11 stages (delegating to deep-research, academic-paper, academic-paper-reviewer). Two invocation modes:

**Mode A — orchestrator-driven (default):** `pipeline_orchestrator_agent` runs all stages end-to-end with state tracking via Material Passport. `state_tracker_agent`, `integrity_verification_agent`, `collaboration_depth_agent`, and `claim_ref_alignment_audit_agent` are dispatched by the orchestrator at the appropriate checkpoints.

**Mode B — phase-by-phase (cross-session resume):** User invokes one phase agent at a time across sessions, typically via `ARS_PASSPORT_RESET=1` + `resume_from_passport=<hash>` (see `references/passport_as_reset_boundary.md`).

In Mode B, **single-phase agents (Bucket A per `docs/design/2026-05-18-ars-v3.9.2-agent-phase-classification.md`) in the downstream skills (deep-research, academic-paper, academic-paper-reviewer) stay strictly within their assigned phase for writes**. The 5 agents in academic-pipeline itself are all cross-phase / meta by design (Bucket C/D) — they have no fence by design:

- `pipeline_orchestrator_agent` (D — orchestrator, full pipeline visibility)
- `state_tracker_agent` (D — meta state, all phases)
- `integrity_verification_agent` (C — Stage 2.5 / 4.5 cross-skill gate)
- `collaboration_depth_agent` (C — FULL/SLIM checkpoints + Stage 6 record compilation, advisory-only)
- `claim_ref_alignment_audit_agent` (C — opt-in claim audit, phase-orthogonal)

Routing into Mode B requires explicit user signal — `/ars-<mode>` slash command or `[direct-mode]` prefix. Ambiguous cross-phase input defaults to clarification per `.claude/CLAUDE.md` Routing Discipline + `shared/references/intent_clarification_protocol.md`. **Critically:** if `pipeline_orchestrator_agent` is dispatched on ambiguous cross-phase materials, the orchestrator itself currently cannot reconcile (this is the v3.10 conductor #134 work) — v3.9.2 routes such cases to clarification BEFORE the orchestrator runs.

**Enforcement (v3.9.2):** Phase Boundary blocks on downstream Bucket A agents + advisory verifier (`scripts/check_pipeline_integrity.py`) + a deterministic PreToolUse write-scope guard in hook-enabled runtimes (#134 rescope, PR #294). Multi-phase envelope + orchestrator structured intake remain forward-scope (#134 Slices 3-5).

---

## File-Gate Enforcement (v4.1) ⚠️ IRON RULE

The recurring failure mode of prompt-only orchestration is *simulated* execution: one pass "role-plays" reviewers or integrity checks and advances. v4.1 closes this with verifiable artifacts:

1. **Run directory.** At pipeline start create `ars_run/<slug>/` + `state.json`. All stage deliverables are files inside it (artifact map: `references/file_gate_protocol.md`).
2. **Blocking validator.** A stage is complete ONLY when `python3 "${CLAUDE_PLUGIN_ROOT}/academic-pipeline/scripts/validate_stage_gate.py" <run_dir> --stage <N>` prints PASS (exit 0). The actual stdout is included in the checkpoint. Re-telling the validator's result without running it is prohibited.
3. **Guard-compliant collection (#134).** Bucket A subagents write only inside their `allowed_write_globs` (`scripts/ars_phase_scope_manifest.json`) and have no Bash. The orchestrator (Bucket D, unfenced) copies their outputs into `ars_run/<slug>/stageN/` and runs the validator. Do not ask a Bucket A agent to write into `ars_run/` or to run any script — the write-scope guard will deny it.
4. **Subagent dispatch.** Stage 3 reviewers (5) and Stage 2.5/4.5 integrity verification run as separate clean-context subagents; each writes its own report file in its phase directory. The synthesizer starts only after the validator confirms 5 existing, mutually distinct reports.
5. **No retro-fitting.** Generating an artifact after the fact to satisfy the gate is prohibited — a missing file means the stage was not executed.
6. **Degraded mode.** If Python is unavailable, announce prompt-only degraded mode explicitly and obtain user confirmation.

---

## Execution Discipline (LOCAL OVERRIDE, Иван, 27.07.2026) ⚠️ IRON RULE

Правила поверх всего скилла; при конфликте с текстом ниже по файлу — приоритетны. Введены по итогам боевых прогонов, где оркестратор подменял стадии импровизацией.

1. **Стадии не заменяются импровизацией.** Каждая стадия выполняется РОВНО так, как описана в этом скилле, суб-агентами, которых она предписывает. Особо Stage 3 (панель из 5 рецензентов) и Stage 2.5/4.5 (integrity): их ЗАПРЕЩЕНО выполнять «своими силами» в основном контексте — только отдельные clean-context суб-агенты, каждый со своим файлом-отчётом, затем validate_stage_gate. «Я сам быстро отрецензирую/проверю» = провал стадии, даже если результат выглядит разумно. Стадию невозможно выполнить как предписано → СТОП и доложить пользователю; тихое упрощение запрещено.
2. **Модельная политика — через штатный `ARS_MODEL_TIERING` (upstream #517), НЕ вручную.** Ручное понижение агентов ЗАПРЕЩЕНО. Канон — `shared/model_tiering.md` + `scripts/model_tiering_manifest.json`: 26 агентов judgment-type идут ТОЛЬКО на модели сессии, 13 execution-type понижаются ровно на одну ступень с полом Opus-class. **Sonnet-класс не допускается ни для одного агента ARS ни при каких настройках.** Агенты Stage 1 (`research_question`, `research_architect`, `synthesis`, `source_verification`, `risk_of_bias`, `editor_in_chief`, `literature_strategist`) — judgment-type: понижать их запрещено, именно они формируют доказательную базу, и никакой гейт 2.5/4.5 потом не починит плохие источники. Переключатель выставляется в окружении: `ARS_MODEL_TIERING=economy` для сессии на фронтир-модели, `quality-boost` для сессии ниже фронтира (judgment-агенты поднимаются до фронтира на гейтах), не задан — всё на модели сессии (дефолт, безопасен). **Соразмерность research:** для статьи достаточно 12–20 добротных источников и ОДНОЙ волны разведчиков; вторая волна — только если Stage 2.5 нашла дыры в базе. Не раскапывать тему «до дна» и не плодить итерации ресерча без явного запроса пользователя. **Соразмерность режима:** полный 11-стадийный прогон — не дефолт. Для короткой статьи под знакомый журнал выбирать `academic-paper` + venue-гейт, а не весь пайплайн; полный прогон — когда нужны обе волны рецензирования.
3. **Пользователю — только финальный .docx.** Все промежуточные файлы (черновики, рецензии, планы правок, integrity-отчёты, все *.md в ars_run/) — служебные артефакты: обязательны для гейтов, но пользователю их НЕ отправлять, НЕ прикладывать и НЕ перечислять списком. Финальное сообщение = путь к одному .docx + короткий текстовый итог с фактическими вердиктами гейтов. В Cowork промежуточные файлы держать в рабочей папке ars_run/, в outputs выкладывать только финальный .docx.
4. **Данные автора — всегда плейсхолдеры, вопросов не задавать.** ФИО/организация/e-mail/ORCID/соавторы/научрук НИКОГДА не запрашиваются (ни на intake, ни на Stage 5/6): сразу ставить `[Фамилия И. О.]`, `[организация]`, `[e-mail]`; заполняет пользователь. Intake-вопрос про соавторов (Step 9 academic-paper) отключён тем же оверрайдом.

5. **Бюджет прогона фиксируется до старта и проверяется машиной.** Объём в знаках, потолок и минимум источников
   записываются в `state.json` на Step 1 и блокирующе проверяются валидатором (Stage 1 — источники,
   Stage 2/4/4'/5 — объём, Stage 2 для ru — стилевой гейт). Раздувание разведки и черновиков «с запасом» —
   не мелочь стиля, а причина многочасовых прогонов: каждая лишняя тысяча знаков и каждый лишний источник
   проходят потом через integrity, две волны рецензирования, venue-гейт и дестилляцию.

6. **Закрытая стадия не переигрывается.** Гейт PASS = стадия принята; повторный прогон «чтобы убедиться»
   запрещён — для уверенности существуют артефакты и вердикты, а не второй проход. Продолжение в новом чате —
   через `--ledger` (Resume Protocol выше), а не пересказом контекста. Не устраивает результат по существу —
   это явный возврат на стадию по решению пользователя, с записью причины в `state.json`.

---

## Formatting Intake Protocol (ask-first, v4.1) ⚠️ IRON RULE

Never assume a formatting or citation standard. At intake AND again before Stage 5 ask:

1. What governs the formatting: **университетская методичка** (request the file), **GOST R 7.0.100-2018 / GOST 7.32-2017**, a specific journal's guidelines, or a generic style (APA/Chicago/MLA/IEEE/Vancouver)?
2. If a методичка is provided, it takes precedence. LOCAL OVERRIDE — это делает АГЕНТ, целиком:
   прочитать присланный файл (.docx/.pdf/фото) -> вынуть поля, шрифт, кегли основного текста/сносок/подписей,
   интервал, абзацный отступ, выравнивание, нумерацию страниц -> записать в `stage5/formatting_spec.md`
   И спекой в `~/.claude/ars-docx/specs.json` (id `вкр-<вуз>`, поле `source`) -> самому запустить
   `build_reference.py <id>` -> собирать Stage 5 с этим шаблоном. Пользователю НЕ выдавать команд
   для терминала и не переспрашивать параметры, которые есть в файле: он прислал документ,
   получает .docx. Показать ему только короткую сводку вычитанных чисел — чтобы он поймал
   ошибку распознавания. Чего в методичке нет — брать из `reference_gost.docx` и помечать в сводке как дефолт.
3. No document — present options, record the confirmed choice in `formatting_spec.md` («подтверждено пользователем»).

Stage 5 MUST NOT start without `formatting_spec.md`. The abstract/annotation language set is likewise an intake question (no hard-coded language pair).

---

## Stage 4.75: DESTYLE Protocol (Russian papers, v4.1)

For papers whose main text is Russian, after Stage 4.5 PASS the orchestrator dispatches the standalone `ru-academic-destyle` skill in **pipeline mode** (its `references/modes.md` §5):

1. Orchestrator prepares `terms.txt` (key terminology from the Paper Configuration Record + glossary).
2. The skill runs its verifiable cycle: `scan_axes.py --json before.json` → edit → `scan_axes.py --gate --compare` (blocking, ≤3 iterations) → `check_invariants.py` (blocking: numbers, citation markers, footnotes, quotes, headings, terms must survive).
3. Deliverables in `ars_run/<slug>/stage4_75/`: `paper_destyled.md`, `before.json`, `after.json`, `invariants.json`, `destyle_report.md`.
4. `validate_stage_gate.py --stage 4.75` must PASS.
5. ⚠️ **IRON RULE**: after Stage 4.75 the substantive text is FROZEN. Stage 5 performs format conversion only; any later content change reopens the pipeline at Stage 4.5.

Non-Russian papers: stage is skipped; `state.json` records `{"stage": "4.75", "status": "skipped", "reason": "non-ru"}`. The destyle scripts run from the orchestrator/main session (unfenced) — never from a Bucket A agent.

---

## Integrity Review Protocol

Stage 2.5 (pre-review) and Stage 4.5 (post-revision) verification. 5-phase protocol: references → citation context → statistical data → originality → claims.

⚠️ **IRON RULE**: Stage 4.5 must reach a recorded terminal resolution before Stage 5: PASS, or — after the 3-round integrity FAIL loop is exhausted — an explicit, recorded user decision on the listed unresolved items (rationale requirements escalate on repeated overrides; see `shared/compliance_checkpoint_protocol.md`). Unresolved items are never silently dropped. Stage 4.5 performs a fresh from-scratch pass without relying on Stage 2.5 conclusions; this is not a claim of independent error processes.

⚠️ **IRON RULE (v3.2)**: Both Stage 2.5 and Stage 4.5 must also run the **AI Research Failure Mode Checklist** — a 7-mode taxonomy extending the citation hallucination checks into implementation bugs, hallucinated results, shortcut reliance, bug-as-insight, methodology fabrication, and pipeline-level frame-lock. If any of the 7 modes is `SUSPECTED`, or if Modes 1/3/5/6 are `INSUFFICIENT EVIDENCE`, the pipeline **blocks** and the user must acknowledge (confirm / override with reasoning / revise) before the pipeline proceeds. No configuration flag silences this block; the only path past it is the recorded user acknowledgment above — a trust-based control with an audit trail. Stage 6 PROCESS SUMMARY then reports the full failure-mode audit log as part of the AI Self-Reflection Report.

> See `references/integrity_review_protocol.md` for the 5-phase citation/claim verification procedures.
> See `references/ai_research_failure_modes.md` for the 7-mode AI research failure checklist and block/override logic.

- [v3.4.0] `compliance_agent` runs mode-aware PRISMA-trAIce + RAISE compliance check; tier-based block semantics. See `shared/compliance_checkpoint_protocol.md`.

### Tortured-phrase advisory (#660)

After the exact Stage 4.5 pass and immediately before Stage 5 formatting, the orchestrator runs the deterministic #660 checker over the exact accepted working draft using an explicit user-supplied or synthetic-fixture snapshot and detached manifest bound to the raw snapshot SHA-256; omitted supply produces an explicit `not_checked` artifact. The path ships no native PPS content/importer/fetcher or redistributed phrase list and uses no live model, external API, human or model judge, or ambient clock; timestamps are explicit inputs. Its own-draft result is `HEURISTIC-ADVISORY` / `UNMEASURED`, never changes the Stage 4.5 PASS or Stage 5 gate, never rewrites prose, and must be re-run only after a revision has re-entered the existing integrity/screen sequence.

For the literature corpus, a non-in-place producer emits one current v1.2 advisory row per `cited_title` and `cited_abstract`; a missing abstract remains explicitly `not_checked` / `unresolved` with `ABSTRACT_MISSING`. Downstream consumers are read-only and compose every row into the one existing `Bibliographic Integrity Advisories` section. The advisory mints no marker, triggers no terminal policy, gate, finalizer promotion, ranking, citation rewrite, or replacement text, and supports no clean-draft, origin, papermill, contextual-validity, publisher-acceptance, or matcher-accuracy claim.

### Cross-document consistency advisory (#672)

The Stage-1 shell-capable dispatcher is the only consumer that may invoke
`scripts/build_cross_document_consistency_advisory.py
build-preregistration-artifact`. The non-shell research architect supplies only
the caller declaration and named companion handle. The resulting exact sidecar
and provided companion are replay-validated and carried byte-for-byte through
every handoff. Omission, silent substitution, template replacement, or digest
repair is invalid.

After the same exact Stage 4.5 PASS, the single mandatory Stage-5 entry
checkpoint runs #660 first and #672 second. Both bind the identical accepted
draft; #660 `input_binding.artifact.artifact_id/artifact_sha256` must equal #672
`input_binding.accepted_draft_artifact_id/accepted_draft_sha256`. They remain
separate carriers with separate failure semantics: preserve a schema-valid #660
degraded artifact on exit 1; a #672 contract/runtime failure writes no artifact
and records only bounded `ADVISORY_UNAVAILABLE:<CODE>`.

#672 is always `LLM-ADVISORY` / `UNMEASURED`. It has no score, pass/fail, gate,
readiness, authorization, ClaimIntent, rewrite, consent/protocol duplicate, or
clean/agreement meaning. It cannot change Stage 4.5, block or delay the existing
checkpoint, or alter Stage-5 routing after user confirmation. A manuscript
revision stales both advisories and must re-enter integrity before #660 and #672
rerun, in that order, against the new accepted bytes.

---

## Two-Stage Review Protocol

Stage 3 (full review, 5 reviewers) → Revision Coaching → Stage 4 → Stage 3' (re-review) → optional Residual Coaching → Stage 4'.

Stage 3' runs under the #576 three-gate evidence-before-persuasion contract by default: the orchestrator emits a hash-bound input manifest, dispatches Phase 1 (criteria commitment, revision-blind) → Phase 2A (evidence verdict, persuasion-blind) → Phase 2B (claim matching, letter revealed), and invokes `scripts/check_re_review_synthesis.py` as a MANDATORY step before any decision surfaces — outcomes are Accept / Minor / Major, a `user_review_required` deferral, or a fail-closed abort (never Reject). The sidecar's frozen `previously_missed`/`indeterminate` new-issue records forward to Stage 4.5 on both routes. Legacy single-pass re-review requires the explicit `ARS_RE_REVIEW_LEGACY=1` flag and is marked `[LEGACY-NO-CONTRACT]`. Authority: `pipeline_orchestrator_agent.md` § Stage 3' Re-Review Contract Dispatch + `academic-paper-reviewer/references/re_review_mode_protocol.md`.

> See `references/two_stage_review_protocol.md` for detailed stage flows and coaching dialogue limits.

---

## Mid-Entry Protocol

Users can enter from any stage. The orchestrator will:

1. **Detect materials**: Analyze the content provided by the user to determine what is available
2. **Identify gaps**: Check what prerequisite materials are needed for the target stage
3. **Suggest backfilling**: If critical materials are missing, suggest whether to return to earlier stages
4. **Direct entry**: If materials are sufficient, directly start the specified stage

**Important: mid-entry cannot skip Stage 2.5**
- If the user brings a paper and enters directly, go through Stage 2.5 (INTEGRITY) first before Stage 3 (REVIEW)
- Only exception: User can provide a previous integrity verification report and content has not been modified

---

## External Review Protocol

Handles external (human) reviewer feedback integration. 4-step workflow: Intake & Structuring → Strategic Revision Coaching → Revision & Response → Self-Verification.

> See `references/external_review_protocol.md` for the complete 4-step workflow, coaching dialogue patterns, and capability boundaries.

---

## Progress Dashboard

ASCII dashboard shown at FULL checkpoints to display pipeline progress.

> See `references/progress_dashboard_template.md` for the dashboard template.

---

## Revision Loop Management

- Stage 3 (first review) -> Stage 4 (revision) -> Stage 3' (verification review) -> Stage 4' (re-revision, if needed) -> Stage 4.5 (final verification)
- **Maximum 1 round of RE-REVISE** (Stage 4'): If Stage 3' gives Major, enter Stage 4' for revision then proceed directly to Stage 4.5 (no return to review)
- **Pipeline overrides academic-paper's max 2 revision rule**: In the pipeline, revisions are limited to Stage 4 + Stage 4' (one round each), replacing academic-paper's max 2 rounds rule
- Mark unresolved issues as Acknowledged Limitations
- Provide cumulative revision history (each round's decision, items addressed, unresolved items)

### Early-Stopping Criterion

At the end of each revision round, suggest stopping only when **no P0 issue remains**, **no unresolved decision-bearing regression remains**, **no applicable criterion has a substantive status change requiring another revision**, and **the author has no outstanding required action**. Explain the criterion-bound basis; do not compute a score delta or treat small label-count changes as convergence. The user can override. Hard cap: 2 full revision loops (Stage 4 + Stage 4').

### Budget Transparency (v3.2; interaction-count extension #89/#388)

At pipeline start, estimate token cost based on paper length, mode, and cross-model toggle. Present estimate and ask for user confirmation before Stage 1 begins.

Alongside the token estimate, present the **interaction-count budget**: long-horizon document corruption compounds with the number of document round-trips, not with token volume (DELEGATE-52, arXiv:2604.15597). Enumerate the round-trip caps the pipeline already enforces — 2 full revision loops (Early-Stopping above), 8 + 5 Socratic coaching rounds (Stage 3→4 / 3'→4'), and the integrity-gate fix→re-verify loop at Stages 2.5/4.5 — and state the worst-case round-trip total those caps imply for the chosen mode. At each stage checkpoint, report the accumulated round-trip count next to the stage status. **Advisory only**: the count never blocks; the per-loop caps remain the enforcement layer. A run that exceeds its stated worst case signals a loop the caps do not cover — surface that explicitly rather than silently continuing.

---

## Cross-run Adjudication Activity (#673; opt-in advisory side channel)

The state tracker section "Adjudication-activity metadata" is the single
producer/state authority. Each run receives one stable explicit `run_id`.
Structured handlers first durably apply their existing author-choice,
compliance-override, explicit-request, or MANDATORY-checkpoint routing/state
effect and only then best-effort append a data-minimized binding to the
five-row `pending_adjudication_activity_bindings[]` inventory. A refused
MANDATORY skip leaves state unchanged before the optional receipt stores
`skip_refused`. Author groups use `artifact_group_stage` and may preserve both
Stage 3 and Stage 3-prime; receipt stages use the complete Stage 1-through-6
closed enum, with no Stage 0. Compliance permits a plain report-only
captured-zero group and requires the paired action receipt only for a fully
qualifying override.

Terminal behavior is unchanged and runs first. After the completed/aborted
state is durable, and only for a user-selected local store, the orchestrator
passes explicit state/artifact-root paths and the explicit pending five rows to
`seal_terminal_inventory(state_path, artifact_root, pending_bindings)`, then
best-effort runs sealed-inventory `build-input`, idempotent `append-run`, and
optional `render`. The helper computes hashes; it does not read pending state,
accept caller hashes, infer sources, or scan. Root `run_id` plus sealed root
`adjudication_activity_sources` are exact authority. Any activity failure is an
advisory diagnostic and cannot affect the already-durable terminal outcome.

Activity data never enters a Material Passport, handoff, Process Record,
reviewer/model/observer/compliance input, gate, verdict, checkpoint input, or
stage transition. No live model, judge, eval, network/API, ambient clock,
directory scan, or glob participates. Full details and frozen receipt schemas
remain in `docs/design/2026-08-10-673-cross-run-adjudication-activity-spec.md`
and `shared/contracts/activity/`.

---

## Auditability and replay boundaries

Pipeline artifacts are versioned, hashed, and auditable. Deterministic validators can be replayed against the same bytes and configuration. LLM-generated prose and semantic judgements are stochastic and are not byte-reproducibility guarantees; record model/configuration and evidence so differences can be inspected.

> See `references/reproducibility_audit.md` for the standardized workflow contract, deterministic replay boundary, audit trail format, and artifact tracking.

---

## Stage 6: Process Summary Protocol

Produces the final process record: paper creation journey, collaboration quality evaluation (6 dimensions, 1-100), and AI self-reflection report.

**Terminal semantics (#528)**: Stage 6 is non-mandatory — the user may decline it at the Stage 5 completion checkpoint (Stage 6 marked `skipped`; the pipeline still terminates `completed`). When it runs, after the process record is delivered the orchestrator prompts for a terminal acknowledgement — `finish` / `end` / `done` / `confirm`, or an unambiguous natural-language equivalent that accepts the deliverables. On acknowledgement, Stage 6 is marked `completed` and the pipeline global state is set to `completed`; change requests (the other language version, content corrections) keep Stage 6 `in_progress` and are not acknowledgements. See `references/pipeline_state_machine.md` § Stage 6 terminal semantics.

> See `references/process_summary_protocol.md` for full workflow, required content structure, scoring dimensions, and output specifications.

---

## Collaboration Depth Observer (v3.5.0, advisory only — never blocks)

The `collaboration_depth_agent` observes the user's collaboration pattern with the pipeline. It is **advisory only** and **never blocks** progression at any checkpoint. It is `non-blocking` by design and carries `blocking: false` in its frontmatter as a structural guarantee.

**When invoked**: every FULL checkpoint, every SLIM checkpoint, and during Stage 6 record compilation (the whole-pipeline pass runs before the Process Record is generated and delivered, so its output can be a chapter of the record the user acknowledges). MANDATORY checkpoints (Stages 2.5 / 4.5 integrity gates) **do not** invoke the observer — those are integrity concerns and must not be diluted.

**What it does**: reads the dialogue range for the just-completed stage (at checkpoints) or the whole pipeline (during Stage 6 record compilation), scores the pattern against the canonical rubric at `shared/collaboration_depth_rubric.md`, and emits an advisory block/chapter. Dimensions: Delegation Intensity, Cognitive Vigilance, Cognitive Reallocation, Zone Classification (Zone 1 / Zone 2 / Zone 3). Rubric is based on Wang & Zhang (2026) IJETHE 23:11 (DOI 10.1186/s41239-026-00585-x).

**Distinction from existing mechanisms**:

| Mechanism | What it evaluates | Blocking? |
|---|---|---|
| `integrity_verification_agent` (Stages 2.5 / 4.5) | Paper content — references, citations, data | Yes (blocking gate) |
| Stage 6 Collaboration Quality Evaluation (6 dims, 1–100) | AI's self-reflection on its own behaviour | No, but produced once only |
| `collaboration_depth_agent` (this observer) | The **user's** collaboration pattern (delegation intensity, vigilance, reallocation) | **No — never blocks. Advisory only.** |

**Non-blocking guarantees**:
- Observer output never appears on the "Flagged" line of any checkpoint.
- The `Ready to proceed?` prompt is unchanged by observer output.
- `blocked_by: collaboration_depth_agent` is never a legal state in `state_tracker`.
- If observer frontmatter ever asserts `blocking: true`, the orchestrator must refuse to dispatch it.

**Cross-model**: when `ARS_CROSS_MODEL` is set, the observer runs on both models and flags any dimension divergence > 2 points. Scores are never silently averaged across models.

> See `agents/collaboration_depth_agent.md` for full scoring procedure and anti-sycophancy discipline; `shared/collaboration_depth_rubric.md` for the canonical 4-dimension rubric.

---

## Anti-Patterns

Explicit prohibitions to prevent common failure modes:

| # | Anti-Pattern | Why It Fails | Correct Behavior |
|---|-------------|-------------|-----------------|
| 1 | **Skipping integrity checks** | "The paper looks fine, skip Stage 2.5/4.5" | Integrity checks are MANDATORY; they cannot be auto-skipped regardless of perceived quality |
| 2 | **Orchestrator doing substantive work** | Pipeline orchestrator writes content or reviews the paper | Orchestrator only dispatches and coordinates; substantive work belongs to the sub-skills |
| 3 | **Auto-advancing past MANDATORY checkpoints** | Moving to next stage without user confirmation at FULL checkpoints | MANDATORY checkpoints require explicit user input before proceeding |
| 4 | **Quality degradation across stages** | Stage 4 revision is worse than Stage 2 draft because context window is exhausted | If Stage N output quality < Stage N-1, PAUSE and reload core principles before continuing |
| 5 | **Silently dropping reviewer concerns** | Revision addresses 8 of 10 concerns and hopes nobody notices | The R&R tracking table must account for every concern with explicit status |
| 6 | **Re-verifying only known issues at Stage 4.5** | Final integrity check only re-checks Stage 2.5 findings | Stage 4.5 must run a fresh from-scratch pass; revision may introduce new issues |
| 7 | **Inflating Collaboration Quality scores** | Giving 90/100 to avoid awkward self-criticism | Honesty first: no inflation, no pleasantries; cite specific evidence for every score |
| 8 | **Bypassing the Failure Mode Checklist block** (v3.2) | "The 7-mode checklist is new, let's skip it this run" | Stage 2.5/4.5 Failure Mode Checklist is MANDATORY and BLOCKING; there is no unrecorded bypass — every override requires user reasoning recorded for Stage 6 |
| 9 | **Simulating subagents inline (v4.1)** | One pass "role-plays" 5 reviewers or the integrity agent; reports correlate; nothing was verified | Dispatch real clean-context subagents; each writes its own file; the validator similarity check catches fakes |
| 10 | **Chat-only deliverables (v4.1)** | Stage output exists only as conversation text; lost on session end; gate unverifiable | Every deliverable is a file under `ars_run/<slug>/`; the gate checks the disk, not the chat |
| 11 | **Assuming a formatting standard (v4.1)** | Silently applying APA to a Russian ВКР governed by a методичка | Formatting Intake is ask-first; Stage 5 requires `stage5/formatting_spec.md` |
| 12 | **Editing content after DESTYLE (v4.1)** | Post-4.75 "improvements" reintroduce AI markers and dodge integrity | Text is frozen after 4.75; content changes reopen the pipeline at Stage 4.5 |
| 13 | **Fencing violations (v4.1, #134)** | Asking a Bucket A agent to write into ars_run/ or run Bash scripts | Bucket A writes stay in their phase globs; the orchestrator collects files and runs the validator |

---

## Quality Standards

| Dimension | Requirement |
|-----------|------------|
| Stage detection | Correctly identify user's current stage and available materials |
| Mode recommendation | Recommend appropriate mode based on user preferences and material status |
| Material handoff | Stage-to-stage handoff materials are complete and correctly formatted |
| State tracking | Pipeline state updated in real time; Progress Dashboard accurate |
| **Mandatory checkpoint** | **User confirmation required after each stage completion** |
| **Mandatory integrity check** | **Stage 2.5 and 4.5 always run; continuation past a non-PASS result requires an explicit, recorded user decision** |
| **Mandatory file gate (v4.1)** | **`validate_stage_gate.py` PASS required for every stage transition; validator stdout shown to the user verbatim** |
| **Mandatory destyle gates (v4.1, ru)** | **Stage 4.75 `scan_axes.py --gate` + `check_invariants.py` must PASS for Russian papers** |
| **Ask-first formatting (v4.1)** | **No standard assumed; методичка/GOST/journal confirmed and recorded in `stage5/formatting_spec.md`** |
| **Mandatory failure mode checklist** (v3.2) | **Stage 2.5 and 4.5 must run the 7-mode AI research failure checklist; suspected failures block; overrides require user reasoning** |
| No overstepping | ⚠️ IRON RULE: Orchestrator does not perform substantive research/writing/reviewing, only dispatching |
| No forcing | ⚠️ IRON RULE: User can pause or exit pipeline at any time (but cannot skip integrity checks) |
| Auditable workflow | Same declared contract and deterministic validators can be replayed; model/configuration and stochastic outputs remain visible rather than promised identical |
| **Convergence-aware stopping** | **Suggest stopping only when no P0, unresolved decision-bearing regression, substantive criterion-status change, or outstanding required action remains; user can override** |
| **Budget transparency** (v3.2; #388) | **Token cost estimate + interaction-count budget (round-trip caps + accumulated count at checkpoints, advisory) + user confirmation at pipeline start** |

---

## Error Recovery

| Stage | Error | Handling |
|-------|-------|---------|
| Intake | Cannot determine entry point | Ask user what materials they have and their goal |
| Stage 1 | deep-research not converging | Suggest mode switch (socratic -> full) or narrow scope |
| Stage 2 | Missing research foundation | Suggest returning to Stage 1 to supplement research |
| Stage 2.5 | Still FAIL after 3 correction rounds | List unverifiable items; user decides whether to continue |
| Stage 3 | Review result is Reject | Provide options: major restructuring (Stage 2) or abandon |
| Stage 4 | Revision incomplete on all items | List unaddressed items; ask whether to continue |
| Stage 3' | Verification still has major issues | Enter Stage 4' for final revision |
| Stage 4' | Issues remain after revision | Mark as Acknowledged Limitations; proceed to Stage 4.5 |
| Stage 4.5 | Final verification FAIL | Fix and re-verify (max 3 rounds) |
| Stage 3 | Reviewer reports too similar (validator FAIL) | Re-dispatch the offending reviewers as fresh subagents; never hand-edit reports to pass the gate |
| Stage 4.75 | Threshold gate FAIL after 3 iterations | Report residual markers; user decides: accept with note / manual pass |
| Stage 4.75 | Invariants gate FAIL | Roll back damaging edits and re-run; NEVER accept a version that changed numbers/citations |
| Stage 5 | No formatting_spec.md | Run Formatting Intake; do not guess |
| Any | User leaves midway | Save pipeline state; can resume from breakpoint next time |
| Any | Skill execution failure | Report error; suggest retry, pause, or mode switch. Do not skip mandatory integrity or failure-mode gates |

---

## Agent File References

| Agent | Definition File |
|-------|----------------|
| pipeline_orchestrator_agent | `agents/pipeline_orchestrator_agent.md` |
| state_tracker_agent | `agents/state_tracker_agent.md` |
| integrity_verification_agent | `agents/integrity_verification_agent.md` |
| collaboration_depth_agent | `agents/collaboration_depth_agent.md` |
| claim_ref_alignment_audit_agent | `agents/claim_ref_alignment_audit_agent.md` |

---

## Reference Files

| Reference | Purpose |
|-----------|---------|
| **`references/file_gate_protocol.md`** | **v4.1 file-gate enforcement: run directory, artifact map, guard-compliant collection, validator rules, formatting intake** |
| `references/pipeline_state_machine.md` | Complete state machine definition: all legal transitions, preconditions, actions |
| `references/plagiarism_detection_protocol.md` | Phase D originality verification protocol + self-plagiarism + AI text characteristics |
| `references/mode_advisor.md` | Unified cross-skill decision tree: maps user intent to optimal skill + mode |
| `references/claim_verification_protocol.md` | Phase E claim verification protocol: claim extraction, source tracing, cross-referencing, verdict taxonomy |
| `references/claim_audit_calibration_protocol.md` | v3.8 #103 claim_ref_alignment audit calibration: gold-set shape (T-C3), threshold gates FNR<0.15 / FPR<0.10 (T-C1), per-class FNR/FPR reporting (T-C2). Re-run via `PYTHONPATH=. python3 -m unittest scripts.test_claim_audit_calibration -v`. |
| `references/ai_research_failure_modes.md` | 7-mode AI research failure checklist (Lu 2026), run at Stage 2.5 + 4.5 with blocking behaviour, reported at Stage 6 |
| `references/team_collaboration_protocol.md` | Multi-person team coordination: role definitions, handoff protocol, version control, conflict resolution |
| `references/integrity_review_protocol.md` | Stage 2.5 + 4.5 integrity verification: 5-phase protocol details |
| `references/two_stage_review_protocol.md` | Two-stage review: Stage 3 full review + Stage 3' verification review |
| `references/external_review_protocol.md` | External (human) reviewer feedback: 4-step intake/coaching/revision/verification |
| `references/process_summary_protocol.md` | Stage 6: collaboration quality evaluation + AI self-reflection report |
| `references/reproducibility_audit.md` | Standardized workflow contract, deterministic replay boundary, and audit trail format |
| `references/progress_dashboard_template.md` | ASCII progress dashboard template |
| `references/reinforcement_content.md` | Stage-specific reinforcement focus table for transitions |
| `references/changelog.md` | Full version history |
| `shared/handoff_schemas.md` | Cross-skill data contracts: 9 schemas for all inter-stage handoff artifacts |
| `shared/collaboration_depth_rubric.md` | Collaboration Depth Observer rubric (v1.0): 4 dimensions based on Wang & Zhang (2026) IJETHE 23:11 |

---

## Templates

| Template | Purpose |
|----------|---------|
| `templates/pipeline_status_template.md` | Progress Dashboard output template |

---

## Examples

| Example | Demonstrates |
|---------|-------------|
| `examples/full_pipeline_example.md` | Complete pipeline conversation log (Stage 1-5, with integrity + 2-stage review) |
| `examples/mid_entry_example.md` | Mid-entry example starting from Stage 2.5 (existing paper -> integrity check -> review -> revision -> finalization) |

---

## Output Language

Follows user language. Academic terminology retained in English.

---

## Integration with Other Skills

```
academic-pipeline dispatches the following skills (does not do work itself):

Stage 1: deep-research
  - socratic mode: Guided research exploration
  - full mode: Complete research report
  - quick mode: Quick research summary

Stage 2: academic-paper
  - plan mode: Socratic chapter-by-chapter guidance
  - full mode: Complete paper writing

Stage 2.5: integrity_verification_agent (Mode 1: pre-review)
Stage 4.5: integrity_verification_agent (Mode 2: final-check)

Stage 3: academic-paper-reviewer
  - full mode: Complete 5-person review (Journal-Fit Reviewer + R1/R2/R3 + Devil's Advocate)

Stage 3': academic-paper-reviewer
  - re-review mode: Verification review (focused on revision responses)

Stage 4/4': academic-paper (revision mode)

Stage 4.75 (ru papers): ru-academic-destyle (pipeline mode)
  - scan_axes.py --gate + check_invariants.py, both blocking
  - text frozen after this stage

Stage 5: academic-paper (format-convert mode)
  - Step 0: stage5/formatting_spec.md must exist (Formatting Intake: методичка /
    GOST R 7.0.100-2018 / GOST 7.32 / journal style / APA 7.0 / Chicago / IEEE, etc.)
  - Step 1: Consume the citation-style decision recorded at the Stage 5 entry gate; ask which academic formatting style (APA 7.0 / Chicago / IEEE, etc.) only when no gate decision exists (direct format-convert / mid-entry invocation)
  - Step 2: Produce MD, then DOCX via Pandoc С ШАБЛОНОМ ОФОРМЛЕНИЯ (LOCAL OVERRIDE):
      pandoc <paper>.md --reference-doc="C:\Users\Admin\.claude\ars-docx\reference_<id>.docx" -o <final>.docx
      <id>: sci-lib | soc-upr | intl-journal | nota-bene | gost (ВКР/курсовая/кандидатская без методички).
      Шаблоны и их спеки: ~/.claude/ars-docx/ (README.md, specs.json). Методичка вуза перекрывает
      шаблон gost: добавить спеку в specs.json и пересобрать build_reference.py, а не править .docx руками.
      Подстрочные ссылки писать markdown-сносками [^1]: — иначе они не станут сносками Word.
      Pandoc отсутствует -> сообщить пользователю, не подменять самодельной сборкой .docx
  - Step 3: Produce LaTeX (using corresponding document class, e.g., apa7 class for APA 7.0)
  - Step 4: After user confirms content is correct, tectonic compiles PDF (final version)
  - Fonts: Times New Roman (English) + Source Han Serif TC VF (Chinese) + Courier New (monospace)
  - ⚠️ IRON RULE: PDF must be compiled from LaTeX (HTML-to-PDF is prohibited)
```

---

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `deep-research` | Dispatched (Stage 1 research phase) |
| `academic-paper` | Dispatched (Stage 2 writing, Stage 4/4' revision, Stage 5 formatting) |
| `academic-paper-reviewer` | Dispatched (Stage 3 first review, Stage 3' verification review) |
| `ru-academic-destyle` | Dispatched (Stage 4.75 destyle for Russian papers; standalone companion skill) |

---

## Model Tiering (#517, optional)

When `ARS_MODEL_TIERING` is set, the dispatching session routes this skill's agents per `shared/model_tiering.md` (canonical: the full 39-agent judgment/execution table + rules). Compact rule:

- **Unset (default):** every agent inherits the session model — byte-equivalent pre-#517 behavior.
- **`economy`** (frontier-tier session): execution-type agents dispatch ONE tier below the session model — floor Opus-class, never lower; judgment-type agents stay on the session model. No-op at or below the floor (announce once).
- **`quality-boost`** (below-frontier session): judgment-type agents at the checkpoint surfaces (Stage 2.5/4.5 gates; the opt-in Stage 4→5 claim–ref audit; final review) jump UP to the frontier tier (however many tiers away — not a single increment); nothing is ever downgraded. No-op at the frontier (announce once).
- Unknown values → warn once, behave as unset. Tiers are relative positions, never hard-pinned model ids. When a direction is active, route repeated same-stage calls to the SAME worker so its prompt cache accumulates; unset means dispatch shapes stay byte-equivalent too.

---

## Version Info

| Item | Content |
|------|---------|
| Skill Version | 3.21.0 |
| ProScience overlay | Stage 4.6 VENUE gate, Stage 4.75 DESTYLE (ru), file gates, Execution Discipline, GOST R 7.0.100-2018 |
| Last Updated | 2026-08-18 |
| Maintainer | Cheng-I Wu |
| Dependent Skills | deep-research v2.0+, academic-paper v2.0+, academic-paper-reviewer v1.1+, ru-academic-destyle v2.1+ (ru) |
| Role | Full academic research workflow orchestrator |

---

## Changelog

> See `references/changelog.md` for full version history.
