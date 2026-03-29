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

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

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
