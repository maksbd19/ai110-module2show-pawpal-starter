"""
End-to-end tests for pawpal_system.py

Covers the full lifecycle:
  - Create owner with time windows
  - Add multiple pets with tasks
  - Generate a schedule
  - Complete tasks
  - Edit pets and tasks
  - Delete pets and tasks
  - Persist and reload the full state
"""

import pytest
from datetime import date, time, timedelta

from pawpal_system import (
    DataStore,
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    TaskCategory,
    TimeWindow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def windows():
    return {
        "morning": TimeWindow("morning", time(7, 0), time(9, 0)),    # 120 min
        "afternoon": TimeWindow("afternoon", time(12, 0), time(13, 30)),  # 90 min
        "evening": TimeWindow("evening", time(18, 0), time(20, 0)),  # 120 min
    }


@pytest.fixture
def owner(windows):
    o = Owner(name="Jordan")
    o.available_windows = list(windows.values())
    return o


@pytest.fixture
def buddy(windows):
    pet = Pet(name="Buddy", species="dog", age=3, breed="Labrador")
    pet.add_task("Morning Walk", "30-min walk", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 30, windows["morning"], Frequency.DAILY)
    pet.add_task("Breakfast", "Kibble + supplements", TaskCategory.FOOD, Priority.CRITICAL, 10, windows["morning"], Frequency.DAILY)
    pet.add_task("Evening Walk", "45-min walk", TaskCategory.DAILY_ACTIVITY, Priority.HIGH, 45, windows["evening"], Frequency.DAILY)
    return pet


@pytest.fixture
def luna(windows):
    pet = Pet(name="Luna", species="cat", age=5, breed="Siamese")
    pet.add_task("Lunch Feeding", "Wet food", TaskCategory.FOOD, Priority.HIGH, 10, windows["afternoon"], Frequency.DAILY)
    pet.add_task("Playtime", "Wand toy session", TaskCategory.ENRICHMENT, Priority.MEDIUM, 20, windows["afternoon"], Frequency.DAILY)
    pet.add_task("Coat Brushing", "Brush coat", TaskCategory.GROOMING, Priority.LOW, 15, windows["evening"], Frequency.WEEKLY)
    return pet


@pytest.fixture
def populated_owner(owner, buddy, luna):
    owner.add_pet(buddy)
    owner.add_pet(luna)
    return owner


@pytest.fixture
def datastore(tmp_path):
    return DataStore(file_path=str(tmp_path / "e2e_test.json"))


# ---------------------------------------------------------------------------
# E2E: Owner & pet setup
# ---------------------------------------------------------------------------

class TestE2ESetup:

    def test_owner_created_with_windows(self, owner, windows):
        assert owner.name == "Jordan"
        assert len(owner.available_windows) == 3

    def test_pets_added_to_owner(self, populated_owner):
        assert len(populated_owner.pets) == 2
        names = {p.name for p in populated_owner.pets}
        assert names == {"Buddy", "Luna"}

    def test_all_tasks_registered(self, populated_owner):
        all_tasks = populated_owner.get_all_tasks()
        assert len(all_tasks) == 6

    def test_task_ids_are_unique_across_pets(self, populated_owner):
        ids = [t.id for t in populated_owner.get_all_tasks()]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# E2E: Schedule generation
# ---------------------------------------------------------------------------

class TestE2ESchedule:

    def test_all_tasks_scheduled(self, populated_owner):
        result = Scheduler().generate(populated_owner, date.today())
        assert len(result.unscheduled_tasks) == 0
        assert len(result.scheduled_tasks) == 6

    def test_critical_tasks_scheduled_first(self, populated_owner):
        result = Scheduler().generate(populated_owner, date.today())
        critical = [st for st in result.scheduled_tasks if st.task.priority == Priority.CRITICAL]
        others = [st for st in result.scheduled_tasks if st.task.priority != Priority.CRITICAL]
        if critical and others:
            assert critical[-1].start_time <= others[0].start_time

    def test_schedule_totals_match(self, populated_owner):
        result = Scheduler().generate(populated_owner, date.today())
        expected_required = sum(t.duration_minutes for t in populated_owner.get_all_tasks())
        assert result.total_required_minutes == expected_required
        assert result.total_available_minutes == 330  # 120+90+120

    def test_tasks_fit_within_windows(self, populated_owner):
        result = Scheduler().generate(populated_owner, date.today())
        window_pairs = [(w.start_time, w.end_time) for w in populated_owner.available_windows]
        for st in result.scheduled_tasks:
            fits = any(ws <= st.start_time and st.end_time <= we for ws, we in window_pairs)
            assert fits, f"'{st.task.name}' falls outside all available windows"

    def test_schedule_linked_to_correct_owner(self, populated_owner):
        result = Scheduler().generate(populated_owner, date.today())
        assert result.owner.id == populated_owner.id

    def test_schedule_for_tomorrow_is_independent(self, populated_owner):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        s1 = Scheduler().generate(populated_owner, today)
        s2 = Scheduler().generate(populated_owner, tomorrow)
        assert s1.id != s2.id
        assert s1.date == today
        assert s2.date == tomorrow


# ---------------------------------------------------------------------------
# E2E: Task completion
# ---------------------------------------------------------------------------

class TestE2ETaskCompletion:

    def test_complete_a_task(self, populated_owner, buddy):
        walk = next(t for t in buddy.tasks if t.name == "Morning Walk")
        result = Scheduler().mark_task_complete(populated_owner, walk.id)
        assert result is True
        assert walk.completed is True

    def test_completed_task_excluded_from_pending(self, populated_owner, buddy):
        scheduler = Scheduler()
        walk = next(t for t in buddy.tasks if t.name == "Morning Walk")
        scheduler.mark_task_complete(populated_owner, walk.id)
        pending_ids = {t.id for t in scheduler.get_pending_tasks(populated_owner)}
        assert walk.id not in pending_ids

    def test_complete_all_tasks(self, populated_owner):
        scheduler = Scheduler()
        for task in populated_owner.get_all_tasks():
            scheduler.mark_task_complete(populated_owner, task.id)
        assert scheduler.get_pending_tasks(populated_owner) == []

    def test_complete_unknown_task_returns_false(self, populated_owner):
        result = Scheduler().mark_task_complete(populated_owner, "nonexistent-id")
        assert result is False

    def test_completing_task_does_not_remove_it_from_pet(self, populated_owner, buddy):
        walk = next(t for t in buddy.tasks if t.name == "Morning Walk")
        Scheduler().mark_task_complete(populated_owner, walk.id)
        assert walk in buddy.tasks  # still present, just flagged


# ---------------------------------------------------------------------------
# E2E: Editing pets and tasks
# ---------------------------------------------------------------------------

class TestE2EEdits:

    def test_edit_pet_name(self, populated_owner, buddy):
        populated_owner.edit_pet(buddy.id, name="Buddy Jr.")
        updated = next(p for p in populated_owner.pets if p.id == buddy.id)
        assert updated.name == "Buddy Jr."

    def test_edit_pet_age(self, populated_owner, luna):
        populated_owner.edit_pet(luna.id, age=6)
        updated = next(p for p in populated_owner.pets if p.id == luna.id)
        assert updated.age == 6

    def test_edit_task_duration(self, buddy):
        walk = next(t for t in buddy.tasks if t.name == "Morning Walk")
        buddy.edit_task(walk.id, duration_minutes=45)
        assert walk.duration_minutes == 45

    def test_edit_task_priority(self, luna):
        play = next(t for t in luna.tasks if t.name == "Playtime")
        luna.edit_task(play.id, priority=Priority.HIGH)
        assert play.priority == Priority.HIGH

    def test_add_new_task_to_existing_pet(self, buddy):
        initial = len(buddy.tasks)
        buddy.add_task("Vet Visit", "Annual checkup", TaskCategory.HEALTHCARE, Priority.CRITICAL, 60)
        assert len(buddy.tasks) == initial + 1

    def test_added_task_appears_in_owner_all_tasks(self, populated_owner, buddy):
        before = len(populated_owner.get_all_tasks())
        buddy.add_task("Vet Visit", "Annual checkup", TaskCategory.HEALTHCARE, Priority.CRITICAL, 60)
        after = len(populated_owner.get_all_tasks())
        assert after == before + 1


# ---------------------------------------------------------------------------
# E2E: Deleting tasks and pets
# ---------------------------------------------------------------------------

class TestE2EDeletion:

    def test_delete_task_from_pet(self, buddy):
        walk = next(t for t in buddy.tasks if t.name == "Morning Walk")
        initial = len(buddy.tasks)
        buddy.delete_task(walk.id)
        assert len(buddy.tasks) == initial - 1
        assert walk not in buddy.tasks

    def test_deleted_task_absent_from_schedule(self, populated_owner, luna):
        grooming = next(t for t in luna.tasks if t.name == "Coat Brushing")
        luna.delete_task(grooming.id)
        result = Scheduler().generate(populated_owner, date.today())
        scheduled_ids = {st.task.id for st in result.scheduled_tasks}
        unscheduled_ids = {t.id for t in result.unscheduled_tasks}
        assert grooming.id not in scheduled_ids
        assert grooming.id not in unscheduled_ids

    def test_delete_pet_removes_from_owner(self, populated_owner, luna):
        populated_owner.delete_pet(luna.id)
        assert luna not in populated_owner.pets
        assert len(populated_owner.pets) == 1

    def test_delete_pet_removes_its_tasks_from_all_tasks(self, populated_owner, luna):
        luna_task_ids = {t.id for t in luna.tasks}
        populated_owner.delete_pet(luna.id)
        remaining_ids = {t.id for t in populated_owner.get_all_tasks()}
        assert luna_task_ids.isdisjoint(remaining_ids)

    def test_delete_only_pet_leaves_empty_schedule(self, owner, buddy):
        owner.add_pet(buddy)
        owner.delete_pet(buddy.id)
        result = Scheduler().generate(owner, date.today())
        assert len(result.scheduled_tasks) == 0
        assert len(result.unscheduled_tasks) == 0

    def test_delete_nonexistent_pet_raises(self, populated_owner):
        with pytest.raises(ValueError):
            populated_owner.delete_pet("ghost-id")

    def test_delete_nonexistent_task_raises(self, buddy):
        with pytest.raises(ValueError):
            buddy.delete_task("ghost-id")


# ---------------------------------------------------------------------------
# E2E: Full persistence round-trip
# ---------------------------------------------------------------------------

class TestE2EPersistence:

    def test_save_and_reload_owner_with_pets_and_tasks(self, datastore, populated_owner, buddy, luna):
        datastore.save_owner(populated_owner)
        loaded = datastore.load_owner(populated_owner.id)

        assert loaded.id == populated_owner.id
        assert loaded.name == populated_owner.name
        assert len(loaded.pets) == 2

        loaded_pet_names = {p.name for p in loaded.pets}
        assert loaded_pet_names == {"Buddy", "Luna"}

        buddy_loaded = next(p for p in loaded.pets if p.name == "Buddy")
        assert len(buddy_loaded.tasks) == len(buddy.tasks)

    def test_task_fields_survive_round_trip(self, datastore, populated_owner, buddy):
        walk = next(t for t in buddy.tasks if t.name == "Morning Walk")
        datastore.save_owner(populated_owner)
        loaded = datastore.load_owner(populated_owner.id)
        buddy_loaded = next(p for p in loaded.pets if p.name == "Buddy")
        walk_loaded = next(t for t in buddy_loaded.tasks if t.id == walk.id)

        assert walk_loaded.name == walk.name
        assert walk_loaded.priority == walk.priority
        assert walk_loaded.category == walk.category
        assert walk_loaded.duration_minutes == walk.duration_minutes
        assert walk_loaded.frequency == walk.frequency
        assert walk_loaded.completed == walk.completed

    def test_completed_flag_persisted(self, datastore, populated_owner, buddy):
        walk = next(t for t in buddy.tasks if t.name == "Morning Walk")
        Scheduler().mark_task_complete(populated_owner, walk.id)
        datastore.save_owner(populated_owner)
        loaded = datastore.load_owner(populated_owner.id)
        buddy_loaded = next(p for p in loaded.pets if p.name == "Buddy")
        walk_loaded = next(t for t in buddy_loaded.tasks if t.id == walk.id)
        assert walk_loaded.completed is True

    def test_save_and_reload_schedule(self, datastore, populated_owner):
        schedule = Scheduler().generate(populated_owner, date.today())
        datastore.save_schedule(schedule)
        loaded = datastore.load_schedule(populated_owner.id, date.today())

        assert loaded.id == schedule.id
        assert loaded.date == schedule.date
        assert len(loaded.scheduled_tasks) == len(schedule.scheduled_tasks)
        assert len(loaded.unscheduled_tasks) == len(schedule.unscheduled_tasks)

    def test_owner_update_persisted(self, datastore, populated_owner, buddy):
        datastore.save_owner(populated_owner)
        populated_owner.edit_pet(buddy.id, name="Buddy Senior")
        datastore.save_owner(populated_owner)

        loaded = datastore.load_owner(populated_owner.id)
        buddy_loaded = next(p for p in loaded.pets if p.id == buddy.id)
        assert buddy_loaded.name == "Buddy Senior"

    def test_deleted_pet_not_in_reloaded_owner(self, datastore, populated_owner, luna):
        populated_owner.delete_pet(luna.id)
        datastore.save_owner(populated_owner)
        loaded = datastore.load_owner(populated_owner.id)
        loaded_names = {p.name for p in loaded.pets}
        assert "Luna" not in loaded_names

    def test_schedules_for_different_dates_independent(self, datastore, populated_owner):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        s_today = Scheduler().generate(populated_owner, today)
        s_tomorrow = Scheduler().generate(populated_owner, tomorrow)
        datastore.save_schedule(s_today)
        datastore.save_schedule(s_tomorrow)

        loaded_today = datastore.load_schedule(populated_owner.id, today)
        loaded_tomorrow = datastore.load_schedule(populated_owner.id, tomorrow)
        assert loaded_today.id == s_today.id
        assert loaded_tomorrow.id == s_tomorrow.id
        assert loaded_today.id != loaded_tomorrow.id
