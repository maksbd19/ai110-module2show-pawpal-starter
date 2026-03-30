from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Optional
import json
import os
import uuid


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskCategory(Enum):
    FOOD = "food"
    HEALTHCARE = "healthcare"
    DAILY_ACTIVITY = "daily_activity"
    GROOMING = "grooming"
    ENRICHMENT = "enrichment"
    OTHER = "other"


class TaskStatus(Enum):
    SCHEDULED = "scheduled"
    POSTPONED = "postponed"
    DELEGATED = "delegated"


class Frequency(Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

@dataclass
class TimeWindow:
    label: str
    start_time: time
    end_time: time


# ---------------------------------------------------------------------------
# Domain Entities
# ---------------------------------------------------------------------------

@dataclass
class Task:
    name: str
    description: str
    category: TaskCategory
    priority: Priority
    duration_minutes: int
    pet_id: str
    preferred_window: Optional[TimeWindow] = None
    frequency: Frequency = Frequency.DAILY
    completed: bool = False
    due_date: Optional[date] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Pet:
    name: str
    species: str
    age: int
    breed: str = ""
    health_notes: str = ""
    tasks: list[Task] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_task(
        self,
        name: str,
        description: str,
        category: TaskCategory,
        priority: Priority,
        duration_minutes: int,
        preferred_window: Optional[TimeWindow] = None,
        frequency: Frequency = Frequency.DAILY,
    ) -> Task:
        """Create a new Task for this pet and append it to the pet's task list."""
        if any(t.name.lower() == name.lower() for t in self.tasks):
            raise ValueError(f"A task named '{name}' already exists for this pet.")
        task = Task(
            name=name,
            description=description,
            category=category,
            priority=priority,
            duration_minutes=duration_minutes,
            preferred_window=preferred_window,
            frequency=frequency,
            pet_id=self.id,
        )
        self.tasks.append(task)
        return task

    def edit_task(self, task_id: str, **updates) -> None:
        """Update one or more fields on an existing task by its ID."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        for key, value in updates.items():
            setattr(task, key, value)

    def delete_task(self, task_id: str) -> None:
        """Remove a task from this pet by its ID, raising ValueError if not found."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        self.tasks.remove(task)


@dataclass
class Owner:
    name: str
    pets: list[Pet] = field(default_factory=list)
    available_windows: list[TimeWindow] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_pet(self, pet: Pet) -> None:
        """Add a Pet to this owner's pet list."""
        if any(p.name.lower() == pet.name.lower() for p in self.pets):
            raise ValueError(f"A pet named '{pet.name}' already exists.")
        self.pets.append(pet)

    def edit_pet(self, pet_id: str, **updates) -> None:
        """Update one or more fields on an existing pet by its ID."""
        pet = next((p for p in self.pets if p.id == pet_id), None)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found")
        for key, value in updates.items():
            setattr(pet, key, value)

    def delete_pet(self, pet_id: str) -> None:
        """Remove a pet from this owner by its ID, raising ValueError if not found."""
        pet = next((p for p in self.pets if p.id == pet_id), None)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found")
        self.pets.remove(pet)

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all pets."""
        return [task for pet in self.pets for task in pet.tasks]

    def save_to_json(self, file_path: str = "data.json") -> None:
        """Persist this owner (pets, tasks, windows) to a JSON file via DataStore."""
        DataStore(file_path).save_owner(self)

    @classmethod
    def load_from_json(cls, file_path: str = "data.json") -> "Optional[Owner]":
        """Load the first owner found in a JSON file. Returns None if not found."""
        store = DataStore(file_path)
        data = store._load_file()
        for owner_id in data.get("owners", {}):
            return store.load_owner(owner_id)
        return None


# ---------------------------------------------------------------------------
# Schedule Output
# ---------------------------------------------------------------------------

@dataclass
class ScheduledTask:
    task: Task
    start_time: time
    end_time: time
    status: TaskStatus = TaskStatus.SCHEDULED


@dataclass
class Schedule:
    date: date
    owner: Owner
    tasks: list[Task] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    conflicted_task_ids: set[str] = field(default_factory=set)
    generated_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def refresh(self, scheduler: Scheduler) -> None:
        """Update the task list after a completion:
        - drops completed tasks
        - picks up any new recurring tasks appended to the owner's pets
        - re-runs conflict detection
        """
        scheduled_ids = {t.id for t in self.tasks}

        new_tasks = [
            t for t in self.owner.get_all_tasks()
            if t.pet_id is not None and not t.completed and t.id not in scheduled_ids
        ]
        for t in new_tasks:
            if t.due_date is None:
                t.due_date = self.date

        today = date.today()
        self.tasks = sorted(
            [t for t in self.tasks if not t.completed or (t.due_date or today) >= today] + new_tasks,
            key=lambda t: (t.due_date or date.max, -_PRIORITY_RANK[t.priority]),
        )
        self.warnings, self.conflicted_task_ids = scheduler.detect_conflicts(self.tasks)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

_RECURRENCE_DELTA = {
    Frequency.DAILY: timedelta(days=1),
    Frequency.WEEKLY: timedelta(weeks=1),
    Frequency.MONTHLY: timedelta(days=30),
    # Frequency.ONCE is intentionally absent — no recurrence
}

_PRIORITY_RANK = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 3,
    Priority.MEDIUM: 2,
    Priority.LOW: 1,
}


def _time_to_minutes(t: time) -> int:
    """Convert a time object to total minutes since midnight."""
    return t.hour * 60 + t.minute


def _minutes_to_time(minutes: int) -> time:
    """Convert total minutes since midnight to a time object."""
    return time(minutes // 60, minutes % 60)


class Scheduler:

    def generate(self, owner: Owner, target_date: date) -> Schedule:
        """Return all pending tasks, assigning due_date=target_date to any task that has none,
        sorted by (due_date, descending priority)."""
        all_tasks = [t for t in owner.get_all_tasks() if t.pet_id is not None]
        for t in all_tasks:
            if t.due_date is None:
                t.due_date = target_date

        today = date.today()
        pending = [t for t in all_tasks if not t.completed or (t.due_date or today) >= today]
        sorted_tasks = sorted(
            pending,
            key=lambda t: (t.due_date, -_PRIORITY_RANK[t.priority]),
        )

        warnings, conflicted_ids = self.detect_conflicts(sorted_tasks)

        return Schedule(
            date=target_date,
            owner=owner,
            tasks=sorted_tasks,
            warnings=warnings,
            conflicted_task_ids=conflicted_ids,
        )

    def detect_conflicts(self, tasks: list[Task]) -> tuple[list[str], set[str]]:
        """Detect scheduling conflicts among tasks that share the same time window.

        Groups tasks by preferred_window label, then greedily assigns start times
        in priority order. Any task that overflows its window is flagged as a conflict.
        Returns a tuple of (warning_messages, conflicted_task_ids).
        """
        warnings: list[str] = []
        conflicted_ids: set[str] = set()

        # Group tasks by preferred window label; tasks without a window are skipped.
        window_groups: dict[str, tuple[TimeWindow, list[Task]]] = {}
        for task in tasks:
            if task.preferred_window is not None:
                label = task.preferred_window.label
                if label not in window_groups:
                    window_groups[label] = (task.preferred_window, [])
                window_groups[label][1].append(task)

        for label, (window, group) in window_groups.items():
            window_start = _time_to_minutes(window.start_time)
            window_end = _time_to_minutes(window.end_time)
            cursor = window_start

            # Higher-priority tasks claim time first.
            for task in self._prioritize(group):
                end = cursor + task.duration_minutes
                if end > window_end:
                    conflicted_ids.add(task.id)
                    remaining = window_end - cursor
                    warnings.append(
                        f"Conflict in '{label}' window: '{task.name}' needs "
                        f"{task.duration_minutes} min but only {remaining} min remain."
                    )
                else:
                    cursor = end

        return warnings, conflicted_ids

    def _prioritize(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted from highest to lowest priority."""
        return sorted(tasks, key=lambda t: _PRIORITY_RANK[t.priority], reverse=True)

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted by preferred window start time (earliest first).

        Tasks with no preferred_window are placed at the end, sorted among
        themselves by descending priority as a tiebreaker.
        """
        _NO_WINDOW = 24 * 60  # sentinel: sorts after any real time
        return sorted(
            tasks,
            key=lambda t: (
                _time_to_minutes(t.preferred_window.start_time)
                if t.preferred_window is not None
                else _NO_WINDOW,
                -_PRIORITY_RANK[t.priority],
            ),
        )

    def filter_tasks(
        self,
        tasks: list[Task],
        pet_id: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> list[Task]:
        """Return tasks filtered by pet_id and/or completion status.

        Args:
            tasks: The task list to filter.
            pet_id: If provided, only tasks whose pet_id equals this value are returned.
            completed: If True, return only completed tasks; if False, return
                       only incomplete tasks; if None, return all.
        """
        result = tasks
        if pet_id is not None:
            result = [t for t in result if t.pet_id == pet_id]
        if completed is not None:
            result = [t for t in result if t.completed == completed]
        return result

    def _fit_into_windows(
        self,
        tasks: list[Task],
        windows: list[TimeWindow],
    ) -> list[ScheduledTask]:
        """Greedily assign tasks to time windows, respecting preferred windows and durations.

        Algorithm:
            1. Maintain a cursor (current fill position in minutes) for every window.
            2. For each task, build a probe order: the task's preferred window first
               (matched by label), then the remaining windows in index order.
            3. Try each candidate window in probe order; place the task in the first
               window where ``cursor + duration <= window_end``.
            4. Advance that window's cursor and record a ScheduledTask.
            Tasks that don't fit in any window are silently dropped (callers should
            run detect_conflicts beforehand to surface these to the user).

        Args:
            tasks: Ordered list of tasks to schedule (highest-priority first recommended).
            windows: Available time windows owned by the owner.

        Returns:
            List of ScheduledTask objects with concrete start/end times assigned.
        """
        # Track the current fill position (in minutes from midnight) for each window
        cursors = [_time_to_minutes(w.start_time) for w in windows]
        ends = [_time_to_minutes(w.end_time) for w in windows]
        scheduled: list[ScheduledTask] = []

        for task in tasks:
            # Build a probe order: preferred window first (by label match), then others
            indices = list(range(len(windows)))
            if task.preferred_window:
                preferred = [
                    i for i, w in enumerate(windows)
                    if w.label == task.preferred_window.label
                ]
                rest = [i for i in indices if i not in preferred]
                indices = preferred + rest

            for i in indices:
                start = cursors[i]
                end = start + task.duration_minutes
                if end <= ends[i]:
                    scheduled.append(ScheduledTask(
                        task=task,
                        start_time=_minutes_to_time(start),
                        end_time=_minutes_to_time(end),
                        status=TaskStatus.SCHEDULED,
                    ))
                    cursors[i] = end
                    break

        return scheduled

    # ------------------------------------------------------------------
    # Cross-pet "brain" methods
    # ------------------------------------------------------------------

    def get_all_tasks(self, owner: Owner) -> list[Task]:
        """Retrieve every task across all of the owner's pets, sorted by priority."""
        return self._prioritize(owner.get_all_tasks())

    def get_pending_tasks(self, owner: Owner) -> list[Task]:
        """Retrieve all incomplete tasks across all pets, sorted by priority."""
        return self._prioritize([t for t in owner.get_all_tasks() if not t.completed])

    def mark_task_complete(self, owner: Owner, task_id: str) -> bool:
        """Mark a task complete by ID, searching across all pets.

        For DAILY and WEEKLY tasks, a new pending instance is automatically
        appended to the pet so the task recurs on the next schedule. Returns
        True if the task was found.
        """
        for pet in owner.pets:
            task = next((t for t in pet.tasks if t.id == task_id), None)
            if task is not None:
                task.completed = True
                delta = _RECURRENCE_DELTA.get(task.frequency)
                if delta is not None:
                    base = task.due_date if task.due_date is not None else date.today()
                    pet.tasks.append(Task(
                        name=task.name,
                        description=task.description,
                        category=task.category,
                        priority=task.priority,
                        duration_minutes=task.duration_minutes,
                        pet_id=task.pet_id,
                        preferred_window=task.preferred_window,
                        frequency=task.frequency,
                        completed=False,
                        due_date=base + delta,
                    ))
                return True
        return False

    def _suggest_actions(self, unscheduled: list[Task]) -> list[str]:
        """Generate delegation or postponement suggestions for tasks that couldn't be scheduled.

        Decision rule:
            - CRITICAL or HIGH priority → recommend delegating to a pet sitter,
              because skipping these tasks has meaningful welfare consequences.
            - MEDIUM or LOW priority → recommend postponing to tomorrow,
              since the impact of a one-day delay is acceptable.

        Args:
            unscheduled: Tasks that overflowed all available time windows.

        Returns:
            Human-readable suggestion strings, one per unscheduled task.
        """
        suggestions = []
        for task in unscheduled:
            if task.priority in (Priority.CRITICAL, Priority.HIGH):
                suggestions.append(
                    f"Delegate '{task.name}' to a pet sitter — it's {task.priority.value} priority "
                    f"and requires {task.duration_minutes} min that couldn't be fit today."
                )
            else:
                suggestions.append(
                    f"Postpone '{task.name}' to tomorrow — {task.priority.value} priority, "
                    f"{task.duration_minutes} min needed."
                )
        return suggestions


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _serialize_time(t: time) -> str:
    """Format a time object as an 'HH:MM' string."""
    return t.strftime("%H:%M")


def _deserialize_time(s: str) -> time:
    """Parse an 'HH:MM' string into a time object."""
    h, m = s.split(":")
    return time(int(h), int(m))


def _serialize_window(w: TimeWindow) -> dict:
    """Serialize a TimeWindow to a JSON-compatible dict."""
    return {
        "label": w.label,
        "start_time": _serialize_time(w.start_time),
        "end_time": _serialize_time(w.end_time),
    }


def _deserialize_window(d: dict) -> TimeWindow:
    """Reconstruct a TimeWindow from a dict."""
    return TimeWindow(
        label=d["label"],
        start_time=_deserialize_time(d["start_time"]),
        end_time=_deserialize_time(d["end_time"]),
    )


def _serialize_task(t: Task) -> dict:
    """Serialize a Task to a JSON-compatible dict."""
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category.value,
        "priority": t.priority.value,
        "duration_minutes": t.duration_minutes,
        "preferred_window": _serialize_window(t.preferred_window) if t.preferred_window else None,
        "frequency": t.frequency.value,
        "completed": t.completed,
        "pet_id": t.pet_id,
        "due_date": t.due_date.isoformat() if t.due_date is not None else None,
    }


def _deserialize_task(d: dict) -> Task:
    """Reconstruct a Task from a dict."""
    raw_due = d.get("due_date")
    return Task(
        id=d["id"],
        name=d["name"],
        description=d["description"],
        category=TaskCategory(d["category"]),
        priority=Priority(d["priority"]),
        duration_minutes=d["duration_minutes"],
        preferred_window=_deserialize_window(d["preferred_window"]) if d.get("preferred_window") else None,
        frequency=Frequency(d.get("frequency", Frequency.DAILY.value)),
        completed=d.get("completed", False),
        pet_id=d["pet_id"],
        due_date=date.fromisoformat(raw_due) if raw_due else None,
    )


def _serialize_pet(p: Pet) -> dict:
    """Serialize a Pet and its tasks to a JSON-compatible dict."""
    return {
        "id": p.id,
        "name": p.name,
        "species": p.species,
        "age": p.age,
        "breed": p.breed,
        "health_notes": p.health_notes,
        "tasks": [_serialize_task(t) for t in p.tasks],
    }


def _deserialize_pet(d: dict) -> Pet:
    """Reconstruct a Pet and its tasks from a dict."""
    pet = Pet(
        id=d["id"],
        name=d["name"],
        species=d["species"],
        age=d["age"],
        breed=d.get("breed", ""),
        health_notes=d.get("health_notes", ""),
    )
    pet.tasks = [_deserialize_task(t) for t in d.get("tasks", [])]
    return pet


def _serialize_owner(o: Owner) -> dict:
    """Serialize an Owner, their pets, and available windows to a JSON-compatible dict."""
    return {
        "id": o.id,
        "name": o.name,
        "pets": [_serialize_pet(p) for p in o.pets],
        "available_windows": [_serialize_window(w) for w in o.available_windows],
    }


def _deserialize_owner(d: dict) -> Owner:
    """Reconstruct an Owner with their pets and available windows from a dict."""
    owner = Owner(
        id=d["id"],
        name=d["name"],
    )
    owner.pets = [_deserialize_pet(p) for p in d.get("pets", [])]
    owner.available_windows = [_deserialize_window(w) for w in d.get("available_windows", [])]
    return owner


def _serialize_scheduled_task(st: ScheduledTask) -> dict:
    """Serialize a ScheduledTask to a JSON-compatible dict."""
    return {
        "task": _serialize_task(st.task),
        "start_time": _serialize_time(st.start_time),
        "end_time": _serialize_time(st.end_time),
        "status": st.status.value,
    }


def _deserialize_scheduled_task(d: dict) -> ScheduledTask:
    """Reconstruct a ScheduledTask from a dict."""
    return ScheduledTask(
        task=_deserialize_task(d["task"]),
        start_time=_deserialize_time(d["start_time"]),
        end_time=_deserialize_time(d["end_time"]),
        status=TaskStatus(d["status"]),
    )


def _serialize_schedule(s: Schedule) -> dict:
    """Serialize a full Schedule (including owner and all tasks) to a JSON-compatible dict."""
    return {
        "id": s.id,
        "date": s.date.isoformat(),
        "owner": _serialize_owner(s.owner),
        "tasks": [_serialize_task(t) for t in s.tasks],
        "warnings": s.warnings,
        "suggestions": s.suggestions,
        "conflicted_task_ids": list(s.conflicted_task_ids),
        "generated_at": s.generated_at.isoformat(),
    }


def _deserialize_schedule(d: dict) -> Schedule:
    """Reconstruct a full Schedule from a dict."""
    return Schedule(
        id=d["id"],
        date=date.fromisoformat(d["date"]),
        owner=_deserialize_owner(d["owner"]),
        tasks=[_deserialize_task(t) for t in d.get("tasks", [])],
        warnings=d.get("warnings", []),
        suggestions=d.get("suggestions", []),
        conflicted_task_ids=set(d.get("conflicted_task_ids", [])),
        generated_at=datetime.fromisoformat(d.get("generated_at", datetime.now().isoformat())),
    )


class DataStore:
    def __init__(self, file_path: str = "pawpal_data.json") -> None:
        self.file_path = file_path

    def _load_file(self) -> dict:
        """Read and return the JSON data file, returning an empty store if it doesn't exist."""
        if not os.path.exists(self.file_path):
            return {"owners": {}, "schedules": {}}
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_file(self, data: dict) -> None:
        """Write the given data dict to the JSON file, overwriting any existing content."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_owner(self, owner: Owner) -> None:
        """Persist an Owner (and all their pets/tasks) to the data file."""
        data = self._load_file()
        data["owners"][owner.id] = _serialize_owner(owner)
        self._save_file(data)

    def load_owner(self, owner_id: str) -> Optional[Owner]:
        """Load and return an Owner by ID, or None if not found."""
        data = self._load_file()
        raw = data["owners"].get(owner_id)
        if raw is None:
            return None
        return _deserialize_owner(raw)

    def save_schedule(self, schedule: Schedule) -> None:
        """Persist a Schedule to the data file, keyed by owner ID and date."""
        data = self._load_file()
        key = f"{schedule.owner.id}_{schedule.date.isoformat()}"
        data["schedules"][key] = _serialize_schedule(schedule)
        self._save_file(data)

    def load_schedule(self, owner_id: str, target_date: date) -> Optional[Schedule]:
        """Load and return a Schedule for the given owner and date, or None if not found."""
        data = self._load_file()
        key = f"{owner_id}_{target_date.isoformat()}"
        raw = data["schedules"].get(key)
        if raw is None:
            return None
        return _deserialize_schedule(raw)
