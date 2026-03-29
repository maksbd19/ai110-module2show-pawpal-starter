from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, time
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
    scheduled_tasks: list[ScheduledTask] = field(default_factory=list)
    unscheduled_tasks: list[Task] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    total_required_minutes: int = 0
    total_available_minutes: int = 0
    generated_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

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
        """Build a daily Schedule by fitting prioritized tasks into the owner's available windows."""
        tasks = [t for t in owner.get_all_tasks() if t.pet_id is not None]
        total_required = sum(t.duration_minutes for t in tasks)
        total_available = sum(
            _time_to_minutes(w.end_time) - _time_to_minutes(w.start_time)
            for w in owner.available_windows
        )

        prioritized = self._prioritize(tasks)
        scheduled = self._fit_into_windows(prioritized, owner.available_windows)
        scheduled_ids = {st.task.id for st in scheduled}
        unscheduled = [t for t in prioritized if t.id not in scheduled_ids]

        warnings = []
        if total_required > total_available:
            warnings.append(
                f"Total required time ({total_required} min) exceeds "
                f"available time ({total_available} min). "
                f"Some tasks could not be scheduled."
            )

        suggestions = self._suggest_actions(unscheduled)

        return Schedule(
            date=target_date,
            owner=owner,
            scheduled_tasks=scheduled,
            unscheduled_tasks=unscheduled,
            warnings=warnings,
            suggestions=suggestions,
            total_required_minutes=total_required,
            total_available_minutes=total_available,
        )

    def _prioritize(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted from highest to lowest priority."""
        return sorted(tasks, key=lambda t: _PRIORITY_RANK[t.priority], reverse=True)

    def _fit_into_windows(
        self,
        tasks: list[Task],
        windows: list[TimeWindow],
    ) -> list[ScheduledTask]:
        """Greedily assign tasks to time windows, respecting preferred windows and durations."""
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
        """Mark a task complete by ID, searching across all pets. Returns True if found."""
        for pet in owner.pets:
            task = next((t for t in pet.tasks if t.id == task_id), None)
            if task is not None:
                task.completed = True
                return True
        return False

    def _suggest_actions(self, unscheduled: list[Task]) -> list[str]:
        """Generate delegation or postponement suggestions for tasks that couldn't be scheduled."""
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
    }


def _deserialize_task(d: dict) -> Task:
    """Reconstruct a Task from a dict."""
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
        "scheduled_tasks": [_serialize_scheduled_task(st) for st in s.scheduled_tasks],
        "unscheduled_tasks": [_serialize_task(t) for t in s.unscheduled_tasks],
        "warnings": s.warnings,
        "suggestions": s.suggestions,
        "total_required_minutes": s.total_required_minutes,
        "total_available_minutes": s.total_available_minutes,
        "generated_at": s.generated_at.isoformat(),
    }


def _deserialize_schedule(d: dict) -> Schedule:
    """Reconstruct a full Schedule from a dict."""
    return Schedule(
        id=d["id"],
        date=date.fromisoformat(d["date"]),
        owner=_deserialize_owner(d["owner"]),
        scheduled_tasks=[_deserialize_scheduled_task(st) for st in d.get("scheduled_tasks", [])],
        unscheduled_tasks=[_deserialize_task(t) for t in d.get("unscheduled_tasks", [])],
        warnings=d.get("warnings", []),
        suggestions=d.get("suggestions", []),
        total_required_minutes=d.get("total_required_minutes", 0),
        total_available_minutes=d.get("total_available_minutes", 0),
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
