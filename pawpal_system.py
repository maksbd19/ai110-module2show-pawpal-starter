from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Optional
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
    preferred_window: Optional[TimeWindow] = None
    pet_id: Optional[str] = None
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

    def add_task(self, task: Task) -> None:
        ...

    def edit_task(self, task_id: str, **updates) -> None:
        ...

    def delete_task(self, task_id: str) -> None:
        ...


@dataclass
class Owner:
    name: str
    pets: list[Pet] = field(default_factory=list)
    available_windows: list[TimeWindow] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_pet(self, pet: Pet) -> None:
        ...

    def edit_pet(self, pet_id: str, **updates) -> None:
        ...

    def delete_pet(self, pet_id: str) -> None:
        ...


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
    pet: Pet
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

class Scheduler:

    def generate(self, owner: Owner, pet: Pet, target_date: date) -> Schedule:
        ...

    def _prioritize(self, tasks: list[Task]) -> list[Task]:
        ...

    def _fit_into_windows(
        self,
        tasks: list[Task],
        windows: list[TimeWindow],
    ) -> list[ScheduledTask]:
        ...

    def _suggest_actions(self, unscheduled: list[Task]) -> list[str]:
        ...


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class DataStore:
    def __init__(self, file_path: str = "pawpal_data.json") -> None:
        self.file_path = file_path

    def save_owner(self, owner: Owner) -> None:
        ...

    def load_owner(self, owner_id: str) -> Optional[Owner]:
        ...

    def save_schedule(self, schedule: Schedule) -> None:
        ...

    def load_schedule(self, pet_id: str, target_date: date) -> Optional[Schedule]:
        ...
