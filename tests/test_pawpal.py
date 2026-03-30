"""
Tests for pawpal_system.py

Run with:  pytest test_pawpal.py -v

Legend:
  [MODEL]     — pure dataclass construction; should pass immediately
  [CRUD]      — Pet/Owner mutation methods; will pass after implementation
  [SCHEDULER] — Scheduler logic; will pass after implementation
  [DATASTORE] — JSON persistence; will pass after implementation
"""

import pytest
from datetime import date, time, timedelta

from pawpal_system import (
    DataStore,
    Frequency,
    Owner,
    Pet,
    Priority,
    Schedule,
    ScheduledTask,
    Scheduler,
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
def pet():
    return Pet(name="Buddy", species="dog", age=3, breed="Labrador")


@pytest.fixture
def walk_task(pet, morning_window):
    return pet.add_task(
        name="Morning Walk",
        description="30-minute walk around the block",
        category=TaskCategory.DAILY_ACTIVITY,
        priority=Priority.HIGH,
        duration_minutes=30,
        preferred_window=morning_window,
    )


@pytest.fixture
def feed_task(pet):
    return pet.add_task(
        name="Breakfast",
        description="Feed kibble with supplements",
        category=TaskCategory.FOOD,
        priority=Priority.CRITICAL,
        duration_minutes=10,
    )


@pytest.fixture
def low_priority_task(pet):
    return pet.add_task(
        name="Nail Trim",
        description="Trim nails with pet clipper",
        category=TaskCategory.GROOMING,
        priority=Priority.LOW,
        duration_minutes=15,
    )


@pytest.fixture
def owner(pet, morning_window, evening_window, walk_task, feed_task):
    o = Owner(name="Alex")
    o.add_pet(pet)
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

    def test_task_ids_are_unique(self, pet):
        t1 = pet.add_task("A", "", TaskCategory.OTHER, Priority.LOW, 5)
        t2 = pet.add_task("B", "", TaskCategory.OTHER, Priority.LOW, 5)
        assert t1.id != t2.id

    def test_pet_creation(self, pet):
        assert pet.name == "Buddy"
        assert pet.species == "dog"
        assert pet.age == 3
        assert len(pet.tasks) == 0

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
        new_task = pet.add_task(
            name="Bath",
            description="Monthly bath",
            category=TaskCategory.GROOMING,
            priority=Priority.LOW,
            duration_minutes=20,
        )
        assert len(pet.tasks) == initial_count + 1
        assert new_task in pet.tasks

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

    def test_generate_returns_schedule(self, owner):
        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        assert isinstance(result, Schedule)

    def test_schedule_is_for_correct_owner(self, owner):
        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        assert result.owner.id == owner.id

    def test_critical_tasks_are_scheduled_first(self, owner):
        """CRITICAL priority tasks must appear before lower-priority ones."""
        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        assert result.tasks[0].priority == Priority.CRITICAL

    def test_scheduled_tasks_fit_within_available_windows(self, owner, morning_window, evening_window):
        """All pending tasks appear in result.tasks regardless of time windows."""
        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        pending_ids = {t.id for t in owner.get_all_tasks() if not t.completed}
        result_ids = {t.id for t in result.tasks}
        assert pending_ids == result_ids

    def test_tasks_that_dont_fit_are_unscheduled(self):
        """All pending tasks appear in result.tasks regardless of duration — no overflow concept."""
        tight_window = TimeWindow("tiny", time(8, 0), time(8, 20))  # only 20 min
        owner = Owner(name="Busy", available_windows=[tight_window])
        pet = Pet(name="Max", species="dog", age=1)
        owner.add_pet(pet)
        pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30)
        pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 10)

        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        assert len(result.tasks) == 2

    def test_warnings_generated_when_time_is_insufficient(self):
        """Schedule succeeds and task appears in result.tasks regardless of window size."""
        tight_window = TimeWindow("tiny", time(8, 0), time(8, 5))  # only 5 min
        owner = Owner(name="Busy", available_windows=[tight_window])
        pet = Pet(name="Max", species="dog", age=1)
        owner.add_pet(pet)
        pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 60)

        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        assert len(result.tasks) == 1

    def test_suggestions_provided_for_unscheduled_tasks(self):
        """All tasks appear in result.tasks — no overflow, no auto-suggestions generated."""
        tight_window = TimeWindow("tiny", time(8, 0), time(8, 10))
        owner = Owner(name="Busy", available_windows=[tight_window])
        pet = Pet(name="Max", species="dog", age=1)
        owner.add_pet(pet)
        pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.LOW, 60)

        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        assert len(result.tasks) == 1

    def test_schedule_totals_are_accurate(self, owner):
        scheduler = Scheduler()
        result = scheduler.generate(owner, date.today())
        non_completed = [t for t in owner.get_all_tasks() if not t.completed]
        assert len(result.tasks) == len(non_completed)


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

    def test_save_and_reload_schedule(self, tmp_datastore, owner):
        scheduler = Scheduler()
        schedule = scheduler.generate(owner, date.today())
        tmp_datastore.save_schedule(schedule)
        loaded = tmp_datastore.load_schedule(owner.id, date.today())
        assert loaded is not None
        assert loaded.id == schedule.id

    def test_load_schedule_returns_none_when_missing(self, tmp_datastore, owner):
        result = tmp_datastore.load_schedule(owner.id, date.today())
        assert result is None

    def test_save_owner_overwrites_existing(self, tmp_datastore, owner):
        tmp_datastore.save_owner(owner)
        owner.name = "Alex Updated"
        tmp_datastore.save_owner(owner)
        loaded = tmp_datastore.load_owner(owner.id)
        assert loaded.name == "Alex Updated"


# ---------------------------------------------------------------------------
# [CORNER] Scheduler — Window Boundary & Overflow
# ---------------------------------------------------------------------------

class TestSchedulerWindowEdgeCases:

    def test_task_fits_exactly_in_window(self):
        """A task whose duration exactly equals remaining window space appears in result.tasks."""
        window = TimeWindow("exact", time(8, 0), time(8, 30))  # 30 min
        owner = Owner(name="Test", available_windows=[window])
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 1
        assert result.tasks[0].due_date == date.today()

    def test_preferred_window_full_falls_back_to_other_window(self):
        """Both tasks appear in result.tasks, sorted by priority."""
        morning = TimeWindow("morning", time(8, 0), time(8, 20))   # 20 min
        evening = TimeWindow("evening", time(17, 0), time(18, 0))  # 60 min
        owner = Owner(name="Test", available_windows=[morning, evening])
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 20, preferred_window=morning)
        pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, preferred_window=morning)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 2
        assert result.tasks[0].priority == Priority.CRITICAL

    def test_task_longer_than_any_window_is_unscheduled(self):
        """A task longer than any window still appears in result.tasks — duration doesn't exclude it."""
        window = TimeWindow("short", time(8, 0), time(8, 30))  # 30 min
        owner = Owner(name="Test", available_windows=[window])
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        pet.add_task("Marathon", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 120)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 1
        assert result.tasks[0].name == "Marathon"

    def test_preferred_window_label_not_in_available_windows_falls_back(self):
        """Task with a preferred window whose label matches nothing still appears in result.tasks."""
        morning = TimeWindow("morning", time(8, 0), time(10, 0))
        ghost = TimeWindow("night", time(22, 0), time(23, 0))  # not in owner's windows
        owner = Owner(name="Test", available_windows=[morning])
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, preferred_window=ghost)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 1


# ---------------------------------------------------------------------------
# [CORNER] Scheduler — Priority & Multi-Pet
# ---------------------------------------------------------------------------

class TestSchedulerPriorityMultiPet:

    def test_same_priority_tasks_all_scheduled(self):
        """Multiple tasks at the same priority level should all be scheduled if time allows."""
        window = TimeWindow("morning", time(8, 0), time(10, 0))  # 120 min
        owner = Owner(name="Test", available_windows=[window])
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        pet.add_task("Task A", "", TaskCategory.OTHER, Priority.HIGH, 30)
        pet.add_task("Task B", "", TaskCategory.OTHER, Priority.HIGH, 30)
        pet.add_task("Task C", "", TaskCategory.OTHER, Priority.HIGH, 30)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 3
        assert len([t for t in result.tasks if t.completed]) == 0

    def test_main_scenario_all_tasks_scheduled(self):
        """Replicates main.py: two pets, six tasks, three windows — all tasks fit."""
        morning = TimeWindow("Morning", time(7, 0), time(9, 0))    # 120 min
        afternoon = TimeWindow("Afternoon", time(12, 0), time(13, 30))  # 90 min
        evening = TimeWindow("Evening", time(18, 0), time(20, 0))  # 120 min

        owner = Owner(name="Alex Rivera")
        owner.available_windows = [morning, afternoon, evening]

        buddy = Pet(name="Buddy", species="Dog", age=3, breed="Golden Retriever")
        luna = Pet(name="Luna", species="Cat", age=5, breed="Siamese")
        owner.add_pet(buddy)
        owner.add_pet(luna)

        from pawpal_system import Frequency
        buddy.add_task("Morning Walk", "30-min walk", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, morning, Frequency.DAILY)
        buddy.add_task("Breakfast", "Kibble", TaskCategory.FOOD, Priority.CRITICAL, 10, morning, Frequency.DAILY)
        luna.add_task("Lunch Feeding", "Wet food", TaskCategory.FOOD, Priority.HIGH, 10, afternoon, Frequency.DAILY)
        luna.add_task("Playtime", "Wand toy", TaskCategory.ENRICHMENT, Priority.MEDIUM, 20, afternoon, Frequency.DAILY)
        buddy.add_task("Evening Walk", "45-min walk", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 45, evening, Frequency.DAILY)
        luna.add_task("Grooming", "Brush coat", TaskCategory.GROOMING, Priority.LOW, 15, evening, Frequency.WEEKLY)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 6

    def test_critical_task_from_one_pet_before_high_from_another(self):
        """CRITICAL priority task from any pet is scheduled before HIGH from another pet."""
        window = TimeWindow("morning", time(8, 0), time(10, 0))
        owner = Owner(name="Test", available_windows=[window])

        pet_a = Pet(name="A", species="dog", age=1)
        pet_b = Pet(name="B", species="cat", age=1)
        owner.add_pet(pet_a)
        owner.add_pet(pet_b)

        pet_a.add_task("High Task", "", TaskCategory.OTHER, Priority.HIGH, 20)
        pet_b.add_task("Critical Task", "", TaskCategory.OTHER, Priority.CRITICAL, 20)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 2
        assert result.tasks[0].priority == Priority.CRITICAL


# ---------------------------------------------------------------------------
# [CORNER] Scheduler — Empty / Degenerate Inputs
# ---------------------------------------------------------------------------

class TestSchedulerDegenerate:

    def test_owner_with_no_available_windows(self):
        """Tasks still appear in result.tasks even when the owner has no time windows."""
        owner = Owner(name="Busy")
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30)
        pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 10)

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 2

    def test_owner_with_no_pets(self):
        """Scheduler runs cleanly when the owner has no pets."""
        window = TimeWindow("morning", time(8, 0), time(10, 0))
        owner = Owner(name="Empty", available_windows=[window])

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 0

    def test_pet_with_no_tasks(self):
        """A pet with zero tasks does not affect schedule generation."""
        window = TimeWindow("morning", time(8, 0), time(10, 0))
        owner = Owner(name="Test", available_windows=[window])
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)  # no tasks added

        result = Scheduler().generate(owner, date.today())
        assert len(result.tasks) == 0


# ---------------------------------------------------------------------------
# [CORNER] Scheduler — State Methods
# ---------------------------------------------------------------------------

class TestSchedulerStateMethods:

    def test_mark_task_complete_sets_completed_flag(self, owner, pet, walk_task):
        """mark_task_complete actually flips the task's completed field to True."""
        assert walk_task.completed is False
        result = Scheduler().mark_task_complete(owner, walk_task.id)
        assert result is True
        assert walk_task.completed is True

    def test_mark_task_complete_returns_false_for_unknown_id(self, owner):
        assert Scheduler().mark_task_complete(owner, "does-not-exist") is False

    def test_get_pending_tasks_excludes_completed(self, owner, pet, walk_task):
        scheduler = Scheduler()
        scheduler.mark_task_complete(owner, walk_task.id)
        pending_ids = [t.id for t in scheduler.get_pending_tasks(owner)]
        assert walk_task.id not in pending_ids

    def test_get_all_tasks_aggregates_across_pets(self):
        """get_all_tasks returns tasks from every pet, sorted by priority."""
        window = TimeWindow("morning", time(8, 0), time(10, 0))
        owner = Owner(name="Test", available_windows=[window])

        pet_a = Pet(name="A", species="dog", age=1)
        pet_b = Pet(name="B", species="cat", age=1)
        owner.add_pet(pet_a)
        owner.add_pet(pet_b)

        pet_a.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30)
        pet_b.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 10)

        tasks = Scheduler().get_all_tasks(owner)
        assert len(tasks) == 2
        # CRITICAL should come first after prioritization
        assert tasks[0].priority == Priority.CRITICAL


# ---------------------------------------------------------------------------
# [CORNER] CRUD — Error Cases
# ---------------------------------------------------------------------------

class TestCRUDErrorCases:

    def test_add_task_increases_pet_task_count(self, pet):
        """Each call to add_task increments the pet's task list by exactly one."""
        initial = len(pet.tasks)
        pet.add_task("Nap", "Afternoon nap", TaskCategory.OTHER, Priority.LOW, 60)
        assert len(pet.tasks) == initial + 1
        pet.add_task("Bath", "Weekly bath", TaskCategory.GROOMING, Priority.MEDIUM, 20)
        assert len(pet.tasks) == initial + 2

    def test_edit_task_nonexistent_id_raises(self, pet):
        with pytest.raises(ValueError):
            pet.edit_task("nonexistent-id", name="Ghost")

    def test_edit_pet_nonexistent_id_raises(self, owner):
        with pytest.raises(ValueError):
            owner.edit_pet("nonexistent-id", name="Ghost")

    def test_delete_pet_removes_its_tasks_from_get_all_tasks(self, owner, pet):
        task_ids_before = {t.id for t in owner.get_all_tasks()}
        assert len(task_ids_before) > 0

        owner.delete_pet(pet.id)
        task_ids_after = {t.id for t in owner.get_all_tasks()}
        assert task_ids_after == set()


# ---------------------------------------------------------------------------
# [CORNER] DataStore — Persistence Edge Cases
# ---------------------------------------------------------------------------

class TestDataStoreEdgeCases:

    def test_task_without_preferred_window_round_trips(self, tmp_datastore):
        """A task with preferred_window=None serializes and deserializes without error."""
        owner = Owner(name="Test")
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        task = pet.add_task("Feed", "Kibble", TaskCategory.FOOD, Priority.HIGH, 10)
        assert task.preferred_window is None

        tmp_datastore.save_owner(owner)
        loaded = tmp_datastore.load_owner(owner.id)
        loaded_task = loaded.pets[0].tasks[0]
        assert loaded_task.preferred_window is None
        assert loaded_task.name == "Feed"

    def test_two_schedules_different_dates_stored_independently(self, tmp_datastore, owner):
        """Schedules for different dates do not overwrite each other."""
        from datetime import timedelta
        scheduler = Scheduler()
        today = date.today()
        tomorrow = today + timedelta(days=1)

        schedule_today = scheduler.generate(owner, today)
        schedule_tomorrow = scheduler.generate(owner, tomorrow)

        tmp_datastore.save_schedule(schedule_today)
        tmp_datastore.save_schedule(schedule_tomorrow)

        loaded_today = tmp_datastore.load_schedule(owner.id, today)
        loaded_tomorrow = tmp_datastore.load_schedule(owner.id, tomorrow)

        assert loaded_today.id == schedule_today.id
        assert loaded_tomorrow.id == schedule_tomorrow.id
        assert loaded_today.id != loaded_tomorrow.id

    def test_owner_with_no_pets_round_trips(self, tmp_datastore):
        """An owner with no pets serializes and deserializes correctly."""
        owner = Owner(name="Empty Owner")
        tmp_datastore.save_owner(owner)
        loaded = tmp_datastore.load_owner(owner.id)
        assert loaded is not None
        assert loaded.name == "Empty Owner"
        assert loaded.pets == []


# ---------------------------------------------------------------------------
# [RECURRING] Task recurrence on completion
# ---------------------------------------------------------------------------

class TestRecurringTasks:

    def test_completing_daily_task_adds_new_instance(self, owner, pet, walk_task):
        """Completing a DAILY task appends a new pending copy to the pet."""
        pet.edit_task(walk_task.id, frequency=Frequency.DAILY)
        initial_count = len(pet.tasks)
        Scheduler().mark_task_complete(owner, walk_task.id)
        assert len(pet.tasks) == initial_count + 1

    def test_completing_daily_task_sets_next_due_date(self, owner, pet, walk_task):
        """The new daily instance has due_date = original due_date + 1 day."""
        today = date.today()
        pet.edit_task(walk_task.id, frequency=Frequency.DAILY, due_date=today)
        Scheduler().mark_task_complete(owner, walk_task.id)
        new_task = next(t for t in pet.tasks if not t.completed and t.name == walk_task.name)
        assert new_task.due_date == today + timedelta(days=1)

    def test_completing_weekly_task_sets_next_due_date(self, owner, pet, walk_task):
        """The new weekly instance has due_date = original due_date + 7 days."""
        today = date.today()
        pet.edit_task(walk_task.id, frequency=Frequency.WEEKLY, due_date=today)
        Scheduler().mark_task_complete(owner, walk_task.id)
        new_task = next(t for t in pet.tasks if not t.completed and t.name == walk_task.name)
        assert new_task.due_date == today + timedelta(weeks=1)

    def test_completing_monthly_task_sets_next_due_date(self, owner, pet, walk_task):
        """The new monthly instance has due_date = original due_date + 30 days."""
        today = date.today()
        pet.edit_task(walk_task.id, frequency=Frequency.MONTHLY, due_date=today)
        Scheduler().mark_task_complete(owner, walk_task.id)
        new_task = next(t for t in pet.tasks if not t.completed and t.name == walk_task.name)
        assert new_task.due_date == today + timedelta(days=30)

    def test_completing_once_task_does_not_add_new_instance(self, owner, pet, walk_task):
        """Completing a ONCE task does not create a recurrence."""
        pet.edit_task(walk_task.id, frequency=Frequency.ONCE)
        initial_count = len(pet.tasks)
        Scheduler().mark_task_complete(owner, walk_task.id)
        assert len(pet.tasks) == initial_count

    def test_new_recurring_instance_inherits_task_fields(self, owner, pet, walk_task):
        """The spawned task has the same name, category, priority, duration, and frequency."""
        pet.edit_task(walk_task.id, frequency=Frequency.DAILY)
        Scheduler().mark_task_complete(owner, walk_task.id)
        new_task = next(t for t in pet.tasks if not t.completed and t.name == walk_task.name)
        assert new_task.name == walk_task.name
        assert new_task.category == walk_task.category
        assert new_task.priority == walk_task.priority
        assert new_task.duration_minutes == walk_task.duration_minutes
        assert new_task.frequency == walk_task.frequency
        assert new_task.id != walk_task.id

    def test_new_recurring_instance_appears_in_next_schedule(self, owner, pet, walk_task):
        """After completing a daily task, the next day's schedule includes the recurrence."""
        today = date.today()
        pet.edit_task(walk_task.id, frequency=Frequency.DAILY, due_date=today)
        Scheduler().mark_task_complete(owner, walk_task.id)
        next_schedule = Scheduler().generate(owner, today + timedelta(days=1))
        assert any(t.name == walk_task.name for t in next_schedule.tasks)

    def test_chain_completion_creates_successive_due_dates(self, owner, pet, walk_task):
        """Completing a recurring task twice yields correctly spaced due dates."""
        today = date.today()
        pet.edit_task(walk_task.id, frequency=Frequency.DAILY, due_date=today)
        scheduler = Scheduler()
        scheduler.mark_task_complete(owner, walk_task.id)
        second = next(t for t in pet.tasks if not t.completed and t.name == walk_task.name)
        scheduler.mark_task_complete(owner, second.id)
        third = next(t for t in pet.tasks if not t.completed and t.name == walk_task.name)
        assert third.due_date == today + timedelta(days=2)
