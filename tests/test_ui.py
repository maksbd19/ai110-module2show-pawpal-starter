"""
UI integration tests for app.py using Streamlit's AppTest framework.

Covers:
  - Add pet form: success and validation errors
  - Add task form: success and validation errors
  - Schedule generation: session state, sort, and filter controls
"""

import pytest
from streamlit.testing.v1 import AppTest
from pawpal_system import Owner

APP_PATH = "app.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_widget_states(at: AppTest) -> None:
    """Pre-populate missing widget states to handle stale element trees.

    When st.rerun() is called inside a button handler, Streamlit clears widget
    states for widgets that aren't rendered in the interrupted run, but AppTest's
    element tree still references those widgets.  The next at.run() call invokes
    get_widget_states() on the stale tree and raises a KeyError for any missing
    key.  This helper reads the current element tree and seeds any absent keys
    with sensible defaults so the subsequent run succeeds.
    """
    def _present(key: str) -> bool:
        try:
            at.session_state[key]
            return True
        except (KeyError, AttributeError):
            return False

    for sb in at.selectbox:
        if sb.key and not _present(sb.key):
            at.session_state[sb.key] = sb.options[0] if sb.options else None
    for ti in at.text_input:
        if ti.key and not _present(ti.key):
            at.session_state[ti.key] = ""
    for ni in at.number_input:
        if ni.key and not _present(ni.key):
            at.session_state[ni.key] = 0


def click(at: AppTest, label: str) -> AppTest:
    """Click the first button whose label matches, then run."""
    _ensure_widget_states(at)
    btn = next(b for b in at.button if b.label == label)
    return btn.click().run()


def add_pet(at: AppTest, name: str, species: str = "dog", age: int = 2) -> AppTest:
    at.session_state["show_add_pet_form"] = True
    _ensure_widget_states(at)
    at.run()
    fk = at.session_state["pet_form_key"]
    at.text_input(key=f"pet_name_{fk}").set_value(name)
    at.selectbox(key=f"pet_species_{fk}").set_value(species)
    at.number_input(key=f"pet_age_{fk}").set_value(age)
    return click(at, "Add pet")


def add_task(at: AppTest, name: str, pet: str, category: str = "food",
             priority: str = "high", duration: int = 10) -> AppTest:
    at.session_state["show_add_task_form"] = True
    _ensure_widget_states(at)
    at.run()
    tfk = at.session_state["task_form_key"]
    at.text_input(key=f"task_name_{tfk}").set_value(name)
    at.selectbox(key=f"task_pet_{tfk}").set_value(pet)
    at.selectbox(key=f"task_cat_{tfk}").set_value(category)
    at.selectbox(key=f"task_pri_{tfk}").set_value(priority)
    at.number_input(key=f"task_dur_{tfk}").set_value(duration)
    return click(at, "Add task")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    at = AppTest.from_file(APP_PATH)
    # Pre-seed a fresh owner so the app never calls load_from_json,
    # preventing data.json contamination between test runs.
    at.session_state["owner"] = Owner(name="Test User")
    at.run()
    return at


@pytest.fixture
def app_with_pet(app):
    return add_pet(app, "Buddy", "dog", 3)


@pytest.fixture
def app_with_pet_and_task(app_with_pet):
    return add_task(app_with_pet, "Morning Walk", "Buddy", "daily_activity", "high", 30)


@pytest.fixture
def app_with_schedule(app_with_pet_and_task):
    return click(app_with_pet_and_task, "Generate schedule")


# ---------------------------------------------------------------------------
# Add Pet
# ---------------------------------------------------------------------------

class TestAddPet:

    def test_add_pet_appears_in_session(self, app_with_pet):
        assert not app_with_pet.exception
        names = [p.name for p in app_with_pet.session_state["owner"].pets]
        assert "Buddy" in names

    def test_add_second_pet(self, app_with_pet):
        at = add_pet(app_with_pet, "Luna", "cat", 5)
        assert not at.exception
        assert len(at.session_state["owner"].pets) == 2

    def test_add_pet_empty_name_shows_error(self, app):
        app.session_state["show_add_pet_form"] = True
        app.run()
        fk = app.session_state["pet_form_key"]
        app.text_input(key=f"pet_name_{fk}").set_value("   ")
        click(app, "Add pet")
        assert not app.exception
        assert any("cannot be empty" in e.value.lower() for e in app.error)

    def test_add_duplicate_pet_name_shows_error(self, app_with_pet):
        add_pet(app_with_pet, "Buddy")
        assert not app_with_pet.exception
        assert any("buddy" in e.value.lower() for e in app_with_pet.error)
        assert len(app_with_pet.session_state["owner"].pets) == 1


# ---------------------------------------------------------------------------
# Add Task
# ---------------------------------------------------------------------------

class TestAddTask:

    def test_add_task_appears_in_session(self, app_with_pet_and_task):
        at = app_with_pet_and_task
        assert not at.exception
        tasks = at.session_state["owner"].get_all_tasks()
        assert any(t.name == "Morning Walk" for t in tasks)

    def test_add_task_empty_name_shows_error(self, app_with_pet):
        app_with_pet.session_state["show_add_task_form"] = True
        _ensure_widget_states(app_with_pet)
        app_with_pet.run()
        tfk = app_with_pet.session_state["task_form_key"]
        app_with_pet.text_input(key=f"task_name_{tfk}").set_value("   ")
        click(app_with_pet, "Add task")
        assert not app_with_pet.exception
        assert any("cannot be empty" in e.value.lower() for e in app_with_pet.error)

    def test_add_duplicate_task_shows_error(self, app_with_pet_and_task):
        at = app_with_pet_and_task
        add_task(at, "Morning Walk", "Buddy", "daily_activity", "high", 30)
        assert not at.exception
        assert any("morning walk" in e.value.lower() for e in at.error)

    def test_add_task_increments_count(self, app_with_pet):
        add_task(app_with_pet, "Breakfast", "Buddy", "food", "critical", 10)
        assert not app_with_pet.exception
        assert len(app_with_pet.session_state["owner"].get_all_tasks()) == 1

    def test_add_two_tasks_for_same_pet(self, app_with_pet_and_task):
        add_task(app_with_pet_and_task, "Breakfast", "Buddy", "food", "critical", 10)
        assert not app_with_pet_and_task.exception
        assert len(app_with_pet_and_task.session_state["owner"].get_all_tasks()) == 2


# ---------------------------------------------------------------------------
# Schedule generation
# ---------------------------------------------------------------------------

class TestScheduleGeneration:

    def test_generate_creates_last_schedule(self, app_with_schedule):
        assert not app_with_schedule.exception
        assert "last_schedule" in app_with_schedule.session_state

    def test_scheduled_task_matches_added_task(self, app_with_schedule):
        schedule = app_with_schedule.session_state["last_schedule"]
        names = {t.name for t in schedule.tasks}
        assert "Morning Walk" in names

    def test_generate_without_pets_shows_error(self, app):
        click(app, "Generate schedule")
        assert not app.exception
        assert any("pet" in e.value.lower() for e in app.error)

    def test_generate_without_tasks_shows_error(self, app_with_pet):
        click(app_with_pet, "Generate schedule")
        assert not app_with_pet.exception
        assert any("task" in e.value.lower() for e in app_with_pet.error)

    def test_sort_dropdown_present_after_schedule(self, app_with_schedule):
        assert not app_with_schedule.exception
        keys = [sb.key for sb in app_with_schedule.selectbox]
        assert "due_date_sort" in keys

    def test_pet_filter_dropdown_present_after_schedule(self, app_with_schedule):
        assert not app_with_schedule.exception
        keys = [sb.key for sb in app_with_schedule.selectbox]
        assert "pet_filter" in keys

    def test_status_filter_dropdown_present_after_schedule(self, app_with_schedule):
        assert not app_with_schedule.exception
        keys = [sb.key for sb in app_with_schedule.selectbox]
        assert "status_filter" in keys

    def test_filter_by_pet_narrows_results(self, app):
        """Two pets with one task each — filtering by pet returns only that pet's task."""
        add_pet(app, "Buddy", "dog", 3)
        add_pet(app, "Luna", "cat", 5)
        add_task(app, "Walk", "Buddy", "daily_activity", "high", 30)
        add_task(app, "Feed", "Luna", "food", "high", 10)
        click(app, "Generate schedule")

        assert not app.exception
        schedule = app.session_state["last_schedule"]
        buddy = next(p for p in app.session_state["owner"].pets if p.name == "Buddy")

        from pawpal_system import Scheduler
        filtered = Scheduler().filter_tasks(schedule.tasks, pet_id=buddy.id)
        assert all(t.pet_id == buddy.id for t in filtered)
        assert len(filtered) == 1
