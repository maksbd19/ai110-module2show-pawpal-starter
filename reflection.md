# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
  - _Owner_ — the central entity; holds personal info, a list of pets, and available time windows that define when care can happen
  - _Pet_ — belongs to an owner; stores species, age, and health notes; owns a list of tasks specific to that pet
  - _Task_ — the core unit of work; captures what needs to be done, how long it takes, its priority, whether it recurs, and an optional preferred time window; tasks can be grouped using a parent/subtask relationship
  - _Frequency_ — a value object attached to recurring tasks; expresses recurrence as a count + unit (e.g. twice per day, once per month)
  - _TimeWindow_ — a reusable value object for both owner availability and task preferences; has a label, start time, and end time
  - _Scheduler_ — takes an owner, a pet, and a target date; ranks tasks by priority, fits them into available time windows, detects conflicts, and produces a Schedule
  - _Schedule_ — the output of the scheduler; contains an ordered list of scheduled tasks, any tasks that couldn't fit, warnings about time gaps between what's needed and what's available, and a summary of total required vs. available time
  - _ScheduledTask_ — wraps a Task with a concrete start/end time and a status (scheduled, postponed, delegated)
  - _DataStore_ — handles reading and writing the full owner graph (owner → pets → tasks) to a JSON file for persistence
- What classes did you include, and what responsibilities did you assign to each?
  - The design includes 3 enums (`Priority`, `TaskCategory`, `TaskStatus`), 1 value object (`TimeWindow`), 3 domain entities (`Owner`, `Pet`, `Task`), 2 output types (`Schedule`, `ScheduledTask`), and 2 service classes (`Scheduler`, `DataStore`).
  - `Owner` is the root of the data graph. It owns a list of `Pet` objects and a list of `TimeWindow` objects representing when the owner (or a sitter) is available during the day.
  - `Pet` belongs to one owner and holds a list of `Task` objects. It is responsible for task CRUD — adding, editing, and deleting tasks assigned to that pet.
  - `Task` is the core unit of care. It records the task name, description, category, priority, duration, and optionally a preferred time window. Each task represents one occurrence per day.
  - `TimeWindow` is a shared value object used in two places: to express when the owner is available, and to express when a task is preferred to occur.
  - `Scheduler` is a stateless service. It takes an owner, a pet, and a target date, then ranks tasks by priority, fits them into the owner's available windows, and returns a `Schedule`.
  - `Schedule` is the output of the scheduler. It contains the list of successfully placed tasks, any tasks that could not fit, warnings when total required time exceeds available time, and optional suggestions for unscheduled tasks.
  - `ScheduledTask` wraps a `Task` with a concrete start time, end time, and a status value (scheduled, postponed, or delegated).
  - `DataStore` handles all JSON file I/O. It saves and loads the full owner graph (owner → pets → tasks) and stores generated schedules so the app does not need to regenerate them on every page refresh.

**b. Design changes**

- Did your design change during implementation?
  - Yes. Several changes were made during the design review phase before implementation began.
- If yes, describe at least one change and why you made it.
  - **Removed recurring tasks (`Frequency`, `FrequencyUnit`)** — the initial design supported tasks with a recurrence frequency (e.g. twice per day). This was dropped in favor of one task per day to keep the scheduler logic simple and the data model flat. Recurring tasks would have required an expansion step before scheduling and made the `total_required_minutes` calculation more complex.
  - **Removed task grouping** — the initial design allowed tasks to have a parent/subtask relationship for grouping related care activities. This was deferred from the MVP to avoid the added complexity of recursive structures in both the scheduler and the JSON persistence layer.
  - **Removed `_detect_conflicts` from `Scheduler`** — the initial skeleton included a conflict detection method. After reviewing the scheduler design, it was determined that a sequential greedy placement strategy makes overlapping tasks structurally impossible, so the method was redundant and removed.
  - **Added `pet_id` to `Task`** — not present in the initial design. Added as a back-reference so that `DataStore` can reconstruct task ownership during deserialization without relying solely on the nested JSON structure.
  - **Added `owner_id` parameter to `DataStore.load_owner()`** — the initial signature took no arguments, implying a single-user system. Adding the parameter makes the intent explicit and leaves room for multi-user support later.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
  - **Duration and time windows** — each task has a `duration_minutes` value, and tasks can declare a `preferred_window` (a labeled start/end time block). The scheduler checks whether a task fits within its window using a greedy cursor that advances only when a task is successfully placed.
  - **Priority** — tasks carry one of four priority levels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`). Within a time window, higher-priority tasks claim time first, so critical care (e.g., medication) is never bumped by lower-priority activities.
  - **Due date** — the scheduler sorts tasks by `(due_date, descending priority)`, so overdue or time-sensitive tasks surface before future ones.
  - **Completion status** — completed tasks are excluded from scheduling; recurring tasks (daily, weekly, monthly) automatically spawn a new pending instance so they reappear on the next relevant schedule.
  - **Preferred window as a soft constraint** — the preferred window is a preference, not a hard lock. Tasks without a window are still included in the schedule; they are simply placed after all windowed tasks when sorting by time.
- How did you decide which constraints mattered most?
  - Pet care has non-negotiable hard requirements: a dog's medication or a cat's feeding cannot be quietly dropped to optimize slot usage. Priority was therefore ranked above time-window fit — a critical task that overflows its window is flagged as a conflict rather than silently dropped, so the owner is always alerted. Due date was ranked second because an overdue task represents care that has already been deferred and should not fall further behind. Preferred window was intentionally kept as a soft constraint because owners benefit more from seeing all tasks (with a conflict warning) than from a schedule that silently omits tasks that don't fit perfectly.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
  - The scheduler uses a **priority-first greedy placement** strategy rather than an optimal bin-packing approach. Within a time window, tasks are sorted from highest to lowest priority and placed one by one; when a task overflows the window, it is flagged as a conflict and the cursor does not advance, allowing a shorter lower-priority task to claim the remaining slot. This means the scheduler does not search for the arrangement that fits the most tasks — it always guarantees that the highest-priority task is placed first, even if a different ordering could squeeze in one more task overall.
- Why is that tradeoff reasonable for this scenario?
  - For pet care, the cost of missing a critical task (medication, feeding) is far higher than the cost of leaving a small gap in the schedule. An optimal bin-packing solver might determine that skipping a high-priority 40-minute task allows two lower-priority tasks totaling 35 minutes to fit — a worse outcome from a welfare standpoint. The greedy approach ensures owners are never surprised by a missing critical task; they get a conflict warning instead, which they can act on (delegate, reschedule). The tradeoff sacrifices theoretical slot efficiency in exchange for predictable, safety-first behavior.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
