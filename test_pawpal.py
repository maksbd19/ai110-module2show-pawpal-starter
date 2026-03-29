"""
Tests for pawpal_system.py

Run with:  pytest test_pawpal.py -v

Legend:
  [MODEL]     — pure dataclass construction; should pass immediately
  [CRUD]      — Pet/Owner mutation methods; will pass after implementation
  [SCHEDULER] — Scheduler logic; will pass after implementation
  [DATASTORE] — JSON persistence; will pass after implementation
"""

import os
import json
import tempfile
import pytest
from datetime import date, time

from pawpal_system import (
    DataStore,
    Owner,
    Pet,
    Priority,
    Schedule,
    ScheduledTask,
    Scheduler,
    Task,
    TaskCategory,
    TaskStatus,
    TimeWindow,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def morning_window():
    return TimeWindow(label="morning", start_time=time(8, 0), end_time=time(10, 0))


@pytest.fixture
def evening_window():
    return TimeWindow(label="evening", start_time=time(17, 0), end_time=time(19, 0))


@pytest.fixture
def walk_task(morning_window):
    return Task(
        name="Morning Walk",
        description="30-minute walk around the block",
        category=TaskCategory.DAILY_ACTIVITY,
        priority=Priority.HIGH,
        duration_minutes=30,
        preferred_window=morning_window,
    )


@pytest.fixture
def feed_task():
    return Task(
        name="Breakfast",
        description="Feed kibble with supplements",
        category=TaskCategory.FOOD,
        priority=Priority.CRITICAL,
        duration_minutes=10,
    )


@pytest.fixture
def low_priority_task():
    return Task(
        name="Nail Trim",
        description="Trim nails with pet clipper",
        category=TaskCategory.GROOMING,
        priority=Priority.LOW,
        duration_minutes=15,
    )


@pytest.fixture
def pet(walk_task, feed_task):
    p = Pet(name="Buddy", species="dog", age=3, breed="Labrador")
    p.tasks = [walk_task, feed_task]
    return p


@pytest.fixture
def owner(pet, morning_window, evening_window):
    o = Owner(name="Alex")
    o.pets = [pet]
    o.available_windows = [morning_window, evening_window]
    return o


@pytest.fixture
def tmp_datastore(tmp_path):
    return DataStore(file_path=str(tmp_path / "pawpal_data.json"))


# ---------------------------------------------------------------------------
# [MODEL] Data model construction
# ---------------------------------------------------------------------------

class TestModels:

    def test_task_creation(self, walk_task):
        assert walk_task.name == "Morning Walk"
        assert walk_task.priority == Priority.HIGH
        assert walk_task.category == TaskCategory.DAILY_ACTIVITY
        assert walk_task.duration_minutes == 30
        assert walk_task.id is not None

    def test_task_ids_are_unique(self):
        t1 = Task("A", "", TaskCategory.OTHER, Priority.LOW, 5)
        t2 = Task("B", "", TaskCategory.OTHER, Priority.LOW, 5)
        assert t1.id != t2.id

    def test_pet_creation(self, pet):
        assert pet.name == "Buddy"
        assert pet.species == "dog"
        assert pet.age == 3
        assert len(pet.tasks) == 2

    def test_owner_creation(self, owner, pet):
        assert owner.name == "Alex"
        assert len(owner.pets) == 1
        assert owner.pets[0].name == pet.name
        assert len(owner.available_windows) == 2

    def test_time_window(self, morning_window):
        assert morning_window.label == "morning"
        assert morning_window.start_time == time(8, 0)
        assert morning_window.end_time == time(10, 0)

    def test_scheduled_task_defaults_to_scheduled(self, walk_task):
        st = ScheduledTask(
            task=walk_task,
            start_time=time(8, 0),
            end_time=time(8, 30),
        )
        assert st.status == TaskStatus.SCHEDULED


# ---------------------------------------------------------------------------
# [CRUD] Pet task management
# ---------------------------------------------------------------------------

class TestPetTaskCRUD:

    def test_add_task_appends_to_pet(self, pet, low_priority_task):
        initial_count = len(pet.tasks)
        pet.add_task(low_priority_task)
        assert len(pet.tasks) == initial_count + 1
        assert low_priority_task in pet.tasks

    def test_edit_task_updates_field(self, pet, walk_task):
        pet.edit_task(walk_task.id, duration_minutes=45)
        updated = next(t for t in pet.tasks if t.id == walk_task.id)
        assert updated.duration_minutes == 45

    def test_edit_task_updates_multiple_fields(self, pet, walk_task):
        pet.edit_task(walk_task.id, name="Evening Walk", priority=Priority.MEDIUM)
        updated = next(t for t in pet.tasks if t.id == walk_task.id)
        assert updated.name == "Evening Walk"
        assert updated.priority == Priority.MEDIUM

    def test_delete_task_removes_from_pet(self, pet, walk_task):
        initial_count = len(pet.tasks)
        pet.delete_task(walk_task.id)
        assert len(pet.tasks) == initial_count - 1
        assert walk_task not in pet.tasks

    def test_delete_nonexistent_task_raises(self, pet):
        with pytest.raises((ValueError, KeyError)):
            pet.delete_task("nonexistent-id")


# ---------------------------------------------------------------------------
# [CRUD] Owner pet management
# ---------------------------------------------------------------------------

class TestOwnerPetCRUD:

    def test_add_pet_appends_to_owner(self, owner):
        new_pet = Pet(name="Luna", species="cat", age=2)
        initial_count = len(owner.pets)
        owner.add_pet(new_pet)
        assert len(owner.pets) == initial_count + 1
        assert new_pet in owner.pets

    def test_edit_pet_updates_field(self, owner, pet):
        owner.edit_pet(pet.id, name="Buddy Jr.")
        updated = next(p for p in owner.pets if p.id == pet.id)
        assert updated.name == "Buddy Jr."

    def test_delete_pet_removes_from_owner(self, owner, pet):
        initial_count = len(owner.pets)
        owner.delete_pet(pet.id)
        assert len(owner.pets) == initial_count - 1
        assert pet not in owner.pets

    def test_delete_nonexistent_pet_raises(self, owner):
        with pytest.raises((ValueError, KeyError)):
            owner.delete_pet("nonexistent-id")


# ---------------------------------------------------------------------------
# [SCHEDULER] Schedule generation
# ---------------------------------------------------------------------------

class TestScheduler:

    def test_generate_returns_schedule(self, owner, pet):
        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        assert isinstance(result, Schedule)

    def test_schedule_is_for_correct_pet(self, owner, pet):
        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        assert result.pet.id == pet.id

    def test_critical_tasks_are_scheduled_first(self, owner, pet, feed_task):
        """CRITICAL priority tasks must appear before lower-priority ones."""
        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        critical = [st for st in result.scheduled_tasks if st.task.priority == Priority.CRITICAL]
        others = [st for st in result.scheduled_tasks if st.task.priority != Priority.CRITICAL]
        if critical and others:
            assert critical[-1].start_time <= others[0].start_time

    def test_scheduled_tasks_fit_within_available_windows(self, owner, pet, morning_window, evening_window):
        """No scheduled task should start or end outside owner's time windows."""
        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        window_pairs = [(w.start_time, w.end_time) for w in owner.available_windows]
        for st in result.scheduled_tasks:
            fits = any(ws <= st.start_time and st.end_time <= we for ws, we in window_pairs)
            assert fits, f"Task '{st.task.name}' falls outside all available windows"

    def test_tasks_that_dont_fit_are_unscheduled(self):
        """When total task duration exceeds available time, overflow goes to unscheduled."""
        tight_window = TimeWindow("tiny", time(8, 0), time(8, 20))  # only 20 min
        owner = Owner(name="Busy", available_windows=[tight_window])
        pet = Pet(name="Max", species="dog", age=1)
        pet.add_task(Task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30))
        pet.add_task(Task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 10))
        owner.add_pet(pet)

        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        assert len(result.unscheduled_tasks) > 0

    def test_warnings_generated_when_time_is_insufficient(self):
        """Schedule should include warnings when required time exceeds available time."""
        tight_window = TimeWindow("tiny", time(8, 0), time(8, 5))  # only 5 min
        owner = Owner(name="Busy", available_windows=[tight_window])
        pet = Pet(name="Max", species="dog", age=1)
        pet.add_task(Task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 60))
        owner.add_pet(pet)

        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        assert len(result.warnings) > 0

    def test_suggestions_provided_for_unscheduled_tasks(self):
        """Unscheduled tasks should have suggestions (postpone/delegate)."""
        tight_window = TimeWindow("tiny", time(8, 0), time(8, 10))
        owner = Owner(name="Busy", available_windows=[tight_window])
        pet = Pet(name="Max", species="dog", age=1)
        pet.add_task(Task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.LOW, 60))
        owner.add_pet(pet)

        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        assert len(result.suggestions) > 0

    def test_schedule_totals_are_accurate(self, owner, pet):
        scheduler = Scheduler()
        result = scheduler.generate(owner, pet, date.today())
        assert result.total_required_minutes == sum(t.duration_minutes for t in pet.tasks)
        assert result.total_available_minutes > 0


# ---------------------------------------------------------------------------
# [DATASTORE] JSON persistence
# ---------------------------------------------------------------------------

class TestDataStore:

    def test_save_and_reload_owner(self, tmp_datastore, owner):
        tmp_datastore.save_owner(owner)
        loaded = tmp_datastore.load_owner(owner.id)
        assert loaded is not None
        assert loaded.id == owner.id
        assert loaded.name == owner.name

    def test_owner_pets_are_persisted(self, tmp_datastore, owner, pet):
        tmp_datastore.save_owner(owner)
        loaded = tmp_datastore.load_owner(owner.id)
        assert len(loaded.pets) == len(owner.pets)
        assert loaded.pets[0].id == pet.id

    def test_pet_tasks_are_persisted(self, tmp_datastore, owner, pet, walk_task):
        tmp_datastore.save_owner(owner)
        loaded = tmp_datastore.load_owner(owner.id)
        loaded_pet = loaded.pets[0]
        task_ids = [t.id for t in loaded_pet.tasks]
        assert walk_task.id in task_ids

    def test_load_returns_none_when_no_file(self, tmp_datastore):
        result = tmp_datastore.load_owner("nonexistent-id")
        assert result is None

    def test_save_and_reload_schedule(self, tmp_datastore, owner, pet):
        scheduler = Scheduler()
        schedule = scheduler.generate(owner, pet, date.today())
        tmp_datastore.save_schedule(schedule)
        loaded = tmp_datastore.load_schedule(pet.id, date.today())
        assert loaded is not None
        assert loaded.id == schedule.id

    def test_load_schedule_returns_none_when_missing(self, tmp_datastore, pet):
        result = tmp_datastore.load_schedule(pet.id, date.today())
        assert result is None

    def test_save_owner_overwrites_existing(self, tmp_datastore, owner):
        tmp_datastore.save_owner(owner)
        owner.name = "Alex Updated"
        tmp_datastore.save_owner(owner)
        loaded = tmp_datastore.load_owner(owner.id)
        assert loaded.name == "Alex Updated"
