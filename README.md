# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## Smarter Scheduling

PawPal+ goes beyond a simple task list by applying several scheduling algorithms automatically when a daily plan is generated.

**Priority-based ordering** — Tasks are ranked CRITICAL > HIGH > MEDIUM > LOW. When multiple tasks compete for the same time window, higher-priority tasks claim slots first, so critical care (medications, meals) is never crowded out by lower-stakes activities.

**Conflict detection** — `Scheduler.detect_conflicts` groups tasks by their preferred time window, greedily assigns start times in priority order, and flags any task that overflows the window's end time. Flagged tasks appear with a warning indicator (⚠️) in the UI so the owner knows a conflict exists before the day starts.

**Window-aware placement** — `Scheduler._fit_into_windows` uses a greedy cursor algorithm: each window tracks how far it has been filled, and each task is placed in its preferred window if room remains, or falls back to another available window. This prevents gaps and keeps the schedule tight.

**Actionable suggestions** — Tasks that cannot fit anywhere trigger `Scheduler._suggest_actions`, which recommends *delegation* (pet sitter) for CRITICAL/HIGH tasks and *postponement* for MEDIUM/LOW tasks, giving the owner a clear next step rather than a silent omission.

**Recurring tasks** — Completing a DAILY, WEEKLY, or MONTHLY task automatically appends a new pending instance with the correct next due date, so recurring care never needs to be re-entered manually.

**Flexible sorting and filtering** — The generated schedule can be re-sorted by time window (earliest first) and filtered by pet or completion status, making it easy to focus on what still needs to be done for a specific animal.
