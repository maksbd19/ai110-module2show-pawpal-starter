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

## Testing PawPal+

The test suite lives in the `tests/` directory and is organized into three focused files covering 131 tests in total.

| File | Tests | What it covers |
|------|-------|----------------|
| `test_pawpal.py` | 74 | Unit tests for every class and scheduler method |
| `test_e2e.py` | 40 | Full lifecycle scenarios (create → schedule → complete → persist) |
| `test_ui.py` | 17 | Streamlit UI integration tests using `AppTest` |

### Running the tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single file
python -m pytest tests/test_pawpal.py -v

# Run a specific class
python -m pytest tests/test_pawpal.py::TestConflictDetection -v
```

### What the test suite covers

#### Data models (`TestModels`)
- `Task`, `Pet`, `Owner`, `TimeWindow`, and `ScheduledTask` construct correctly with the right defaults.
- Task IDs are unique across every `add_task` call.

#### CRUD — Pet task management (`TestPetTaskCRUD`, `TestCRUDErrorCases`)
- `add_task` appends to the pet and returns the new task.
- `edit_task` updates one or multiple fields by ID.
- `delete_task` removes the task; calling it with a non-existent ID raises `ValueError`.
- Editing or deleting a non-existent task/pet ID always raises `ValueError`.

#### CRUD — Owner pet management (`TestOwnerPetCRUD`)
- `add_pet`, `edit_pet`, and `delete_pet` mirror the task CRUD contract.
- Deleting a pet removes all of its tasks from `get_all_tasks()`.

#### Schedule generation (`TestScheduler`, `TestSchedulerDegenerate`, `TestSchedulerPriorityMultiPet`)
- `generate()` returns all pending tasks assigned to `due_date = target_date` when none is set.
- CRITICAL-priority tasks appear before lower-priority tasks in the output.
- Schedules work correctly with zero pets, zero tasks, and zero available time windows.
- Tasks from multiple pets are merged and priority-ranked globally.
- A CRITICAL task from one pet always precedes a HIGH task from another.

#### Sorting correctness (`TestSortingCorrectness`)
- `sort_by_time()` returns tasks in ascending `preferred_window.start_time` order.
- Tasks with no preferred window are placed after all windowed tasks.
- Same-start-time ties are broken by descending priority.
- No-window tasks among themselves are sorted HIGH → MEDIUM → LOW.
- `generate()` output sorts by `(due_date, priority)` end-to-end.

#### Conflict detection (`TestConflictDetection`)
- Tasks that fit within their window together produce no warnings and an empty `conflicted_task_ids`.
- When combined durations overflow the window, the lower-priority task is flagged — not the higher-priority one.
- A task that exactly fills the window (boundary) is **not** flagged (uses `<=` check).
- A task that overflows by exactly 1 minute **is** flagged with a warning message.
- Warning messages reference both the task name and the window label.
- Tasks in different windows are evaluated independently — no cross-window conflicts.
- `generate()` surfaces `conflicted_task_ids` and `warnings` on the returned `Schedule`.

#### Recurrence logic (`TestRecurringTasks`)
- A DAILY task: completing it appends a new pending copy with `due_date = original + 1 day`.
- A WEEKLY task: next copy has `due_date = original + 7 days`.
- A MONTHLY task: next copy has `due_date = original + 30 days`.
- A ONCE task: no recurrence is created.
- When `due_date` is `None`, `date.today()` is used as the recurrence base.
- The spawned task inherits name, category, priority, duration, and frequency but gets a new ID.
- Completing a task twice in a chain produces correctly spaced due dates (+1 day, +2 days, …).
- A double-completion on the same task ID creates two separate recurring instances.

#### Window boundary and overflow (`TestSchedulerWindowEdgeCases`)
- A task whose duration exactly equals the window fits without conflict.
- When a preferred window is full, the task still appears in `result.tasks`.
- Tasks longer than any window still appear in the schedule (duration is never a filter).
- A preferred window label that matches no available window is handled gracefully.

#### JSON persistence (`TestDataStore`, `TestDataStoreEdgeCases`)
- `save_owner` / `load_owner` round-trips preserve ID, name, pets, tasks, and time windows.
- Tasks with `preferred_window=None` serialize and deserialize without error.
- `save_schedule` / `load_schedule` round-trips preserve ID, date, and task list.
- Schedules for different dates are stored under separate keys and never overwrite each other.
- Loading a non-existent owner or schedule returns `None`.
- Saving an owner a second time overwrites the previous version.
- An owner with no pets serializes and reloads correctly.

#### End-to-end lifecycle (`TestE2ESetup`, `TestE2ESchedule`, `TestE2ETaskCompletion`, `TestE2EEdits`, `TestE2EDeletion`, `TestE2EPersistence`)
- Full create-schedule-complete-persist cycle using a realistic two-pet, six-task, three-window scenario.
- Completing tasks (daily, weekly, once) and verifying recurrence within a live owner state.
- Editing pet names, ages, task durations, and priorities mid-lifecycle.
- Deleting tasks and pets and verifying the schedule updates correctly.
- Full persistence round-trip: owner with two pets and six tasks saves and reloads intact, including the `completed` flag.

#### Streamlit UI integration (`TestAddPet`, `TestAddTask`, `TestScheduleGeneration`)
- Adding a pet via the form populates `st.session_state.owner.pets`.
- Empty pet/task names show a validation error; the count does not change.
- Duplicate pet or task names show an error and are rejected.
- Generating a schedule without pets or tasks shows the correct error message.
- After generation, the sort, pet-filter, and status-filter dropdowns are all present.
- Filtering by pet via `Scheduler.filter_tasks` returns only that pet's tasks.

---

### Confidence level

**4 / 5 stars**

The core scheduling logic — priority ordering, conflict detection, recurrence, sorting, CRUD, and JSON persistence — is comprehensively covered with unit, edge-case, and end-to-end tests, all 131 passing. One star is withheld because the `MONTHLY` recurrence uses a fixed 30-day delta (not a true calendar month), the double-completion behavior is documented but not guarded, and UI test coverage is limited to form validation and dropdown presence rather than full schedule interaction flows.
