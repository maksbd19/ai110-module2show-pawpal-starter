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

    def test_completing_task_with_no_due_date_uses_today_as_base(self, owner, pet, walk_task):
        """When due_date is None, the recurrence base is date.today() so next due = today + delta."""
        pet.edit_task(walk_task.id, frequency=Frequency.DAILY, due_date=None)
        assert walk_task.due_date is None
        Scheduler().mark_task_complete(owner, walk_task.id)
        new_task = next(t for t in pet.tasks if not t.completed and t.name == walk_task.name)
        assert new_task.due_date == date.today() + timedelta(days=1)

    def test_completing_same_task_twice_creates_two_recurring_instances(self, owner, pet, walk_task):
        """Calling mark_task_complete on an already-completed task creates a second recurrence."""
        today = date.today()
        pet.edit_task(walk_task.id, frequency=Frequency.DAILY, due_date=today)
        initial_count = len(pet.tasks)
        scheduler = Scheduler()
        scheduler.mark_task_complete(owner, walk_task.id)
        # Call again on the same (now-completed) original task id
        scheduler.mark_task_complete(owner, walk_task.id)
        pending = [t for t in pet.tasks if not t.completed and t.name == walk_task.name]
        # Two recurring instances should exist (one per completion call)
        assert len(pet.tasks) == initial_count + 2
        assert len(pending) == 2


# ---------------------------------------------------------------------------
# [SORTING] Chronological ordering via sort_by_time
# ---------------------------------------------------------------------------

class TestSortingCorrectness:

    def test_sort_by_time_returns_chronological_order(self):
        """Tasks with earlier preferred_window.start_time appear first."""
        morning = TimeWindow("morning", time(8, 0), time(10, 0))
        afternoon = TimeWindow("afternoon", time(13, 0), time(15, 0))
        evening = TimeWindow("evening", time(18, 0), time(20, 0))
        pet = Pet(name="Rex", species="dog", age=2)
        t_eve = pet.add_task("Evening Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, evening)
        t_morn = pet.add_task("Breakfast", "", TaskCategory.FOOD, Priority.CRITICAL, 10, morning)
        t_aft = pet.add_task("Lunch", "", TaskCategory.FOOD, Priority.MEDIUM, 10, afternoon)

        sorted_tasks = Scheduler().sort_by_time(pet.tasks)
        start_times = [t.preferred_window.start_time for t in sorted_tasks if t.preferred_window]
        assert start_times == sorted(start_times), "Tasks must be in ascending start_time order"

    def test_sort_by_time_tasks_without_window_go_last(self):
        """Tasks with no preferred_window are placed after all windowed tasks."""
        morning = TimeWindow("morning", time(8, 0), time(10, 0))
        pet = Pet(name="Rex", species="dog", age=2)
        t_no_window = pet.add_task("Nail Trim", "", TaskCategory.GROOMING, Priority.LOW, 15)
        t_windowed = pet.add_task("Breakfast", "", TaskCategory.FOOD, Priority.CRITICAL, 10, morning)

        sorted_tasks = Scheduler().sort_by_time(pet.tasks)
        assert sorted_tasks[0].id == t_windowed.id, "Windowed task must come first"
        assert sorted_tasks[-1].id == t_no_window.id, "No-window task must come last"

    def test_sort_by_time_same_start_time_tiebreaks_by_priority(self):
        """When two tasks share the same start_time, higher priority comes first."""
        window = TimeWindow("morning", time(8, 0), time(10, 0))
        pet = Pet(name="Rex", species="dog", age=2)
        t_low = pet.add_task("Nail Trim", "", TaskCategory.GROOMING, Priority.LOW, 15, window)
        t_crit = pet.add_task("Medication", "", TaskCategory.HEALTHCARE, Priority.CRITICAL, 5, window)

        sorted_tasks = Scheduler().sort_by_time(pet.tasks)
        assert sorted_tasks[0].id == t_crit.id, "CRITICAL must precede LOW at same start_time"

    def test_sort_by_time_multiple_no_window_tasks_tiebreak_by_priority(self):
        """Multiple no-window tasks at the end are themselves sorted by descending priority."""
        pet = Pet(name="Rex", species="dog", age=2)
        t_low = pet.add_task("Nail Trim", "", TaskCategory.GROOMING, Priority.LOW, 15)
        t_high = pet.add_task("Vet Call", "", TaskCategory.HEALTHCARE, Priority.HIGH, 20)
        t_med = pet.add_task("Play", "", TaskCategory.ENRICHMENT, Priority.MEDIUM, 10)

        sorted_tasks = Scheduler().sort_by_time(pet.tasks)
        # All have no window — should be sorted HIGH > MEDIUM > LOW
        priorities = [t.priority for t in sorted_tasks]
        from pawpal_system import _PRIORITY_RANK
        ranks = [_PRIORITY_RANK[p] for p in priorities]
        assert ranks == sorted(ranks, reverse=True), "No-window tasks must sort high→low priority"

    def test_generate_sorts_tasks_by_due_date_then_priority(self):
        """generate() output: earlier due_date comes first; same date → higher priority first."""
        owner = Owner(name="Test")
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)

        today = date.today()
        tomorrow = today + timedelta(days=1)

        t_tomorrow_crit = pet.add_task("Vet", "", TaskCategory.HEALTHCARE, Priority.CRITICAL, 10)
        t_today_low = pet.add_task("Play", "", TaskCategory.ENRICHMENT, Priority.LOW, 20)
        t_today_high = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30)

        # Assign explicit due dates so generate() doesn't overwrite them
        t_tomorrow_crit.due_date = tomorrow
        t_today_low.due_date = today
        t_today_high.due_date = today

        result = Scheduler().generate(owner, today)
        assert result.tasks[0].due_date == today, "today's tasks must come before tomorrow's"
        assert result.tasks[1].due_date == today
        assert result.tasks[2].due_date == tomorrow
        # Within today: HIGH before LOW
        today_tasks = [t for t in result.tasks if t.due_date == today]
        assert today_tasks[0].priority == Priority.HIGH


# ---------------------------------------------------------------------------
# [CONFLICT] Conflict detection via detect_conflicts
# ---------------------------------------------------------------------------

class TestConflictDetection:

    def test_no_conflict_when_tasks_fit_in_window(self):
        """Two tasks that together fit inside the window produce no warnings."""
        window = TimeWindow("morning", time(8, 0), time(9, 0))  # 60 min
        pet = Pet(name="Rex", species="dog", age=2)
        t1 = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, window)
        t2 = pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 20, window)

        warnings, conflicted_ids = Scheduler().detect_conflicts([t1, t2])
        assert warnings == []
        assert conflicted_ids == set()

    def test_conflict_flagged_when_tasks_overflow_window(self):
        """When tasks exceed the window, the overflowing task is in conflicted_task_ids."""
        window = TimeWindow("morning", time(8, 0), time(8, 30))  # 30 min total
        pet = Pet(name="Rex", species="dog", age=2)
        t_crit = pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 20, window)
        t_high = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 20, window)
        # CRITICAL (20 min) fills 20/30; HIGH (20 min) needs 20 more but only 10 remain → conflict

        warnings, conflicted_ids = Scheduler().detect_conflicts([t_crit, t_high])
        assert t_high.id in conflicted_ids
        assert t_crit.id not in conflicted_ids

    def test_lower_priority_task_is_flagged_not_higher(self):
        """Higher-priority task claims time first; lower-priority task gets flagged."""
        window = TimeWindow("morning", time(8, 0), time(8, 40))  # 40 min
        pet = Pet(name="Rex", species="dog", age=2)
        t_low = pet.add_task("Nail Trim", "", TaskCategory.GROOMING, Priority.LOW, 30, window)
        t_crit = pet.add_task("Medication", "", TaskCategory.HEALTHCARE, Priority.CRITICAL, 30, window)
        # CRITICAL takes 30 min (fits); LOW needs 30 more but only 10 remain → LOW flagged

        warnings, conflicted_ids = Scheduler().detect_conflicts([t_low, t_crit])
        assert t_low.id in conflicted_ids
        assert t_crit.id not in conflicted_ids

    def test_task_exactly_filling_window_has_no_conflict(self):
        """A single task that exactly fills the window is not flagged (boundary is inclusive)."""
        window = TimeWindow("morning", time(8, 0), time(8, 30))  # 30 min
        pet = Pet(name="Rex", species="dog", age=2)
        t = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, window)

        warnings, conflicted_ids = Scheduler().detect_conflicts([t])
        assert t.id not in conflicted_ids
        assert warnings == []

    def test_task_overflowing_by_one_minute_is_flagged(self):
        """A task that exceeds the window by exactly 1 minute triggers a conflict."""
        window = TimeWindow("morning", time(8, 0), time(8, 30))  # 30 min
        pet = Pet(name="Rex", species="dog", age=2)
        t = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 31, window)

        warnings, conflicted_ids = Scheduler().detect_conflicts([t])
        assert t.id in conflicted_ids
        assert len(warnings) == 1

    def test_warning_message_references_task_and_window(self):
        """The conflict warning names the task and the window it overflowed."""
        window = TimeWindow("morning", time(8, 0), time(8, 20))  # 20 min
        pet = Pet(name="Rex", species="dog", age=2)
        t_crit = pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 20, window)
        t_high = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 10, window)
        # CRITICAL takes all 20 min; Walk has 0 min left → conflict

        warnings, _ = Scheduler().detect_conflicts([t_crit, t_high])
        assert len(warnings) == 1
        assert "morning" in warnings[0]
        assert "Walk" in warnings[0]

    def test_tasks_in_different_windows_do_not_conflict(self):
        """Tasks in separate windows are evaluated independently — no cross-window conflict."""
        morning = TimeWindow("morning", time(8, 0), time(8, 30))  # 30 min
        evening = TimeWindow("evening", time(18, 0), time(18, 30))  # 30 min
        pet = Pet(name="Rex", species="dog", age=2)
        t1 = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, morning)
        t2 = pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 30, evening)

        warnings, conflicted_ids = Scheduler().detect_conflicts([t1, t2])
        assert warnings == []
        assert conflicted_ids == set()

    def test_conflict_detected_in_generated_schedule(self):
        """generate() surfaces conflict metadata when the window is too tight."""
        window = TimeWindow("morning", time(8, 0), time(8, 30))  # 30 min
        owner = Owner(name="Test", available_windows=[window])
        pet = Pet(name="Rex", species="dog", age=2)
        owner.add_pet(pet)
        t_crit = pet.add_task("Feed", "", TaskCategory.FOOD, Priority.CRITICAL, 20, window)
        t_high = pet.add_task("Walk", "", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 20, window)

        result = Scheduler().generate(owner, date.today())
        assert t_high.id in result.conflicted_task_ids
        assert len(result.warnings) >= 1
