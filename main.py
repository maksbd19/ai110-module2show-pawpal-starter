from datetime import date, time

from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    TaskCategory,
    TimeWindow,
)


# ---------------------------------------------------------------------------
# Data dictionaries
# ---------------------------------------------------------------------------

_DEMO_DATA = {
    "owner": "Sam Chen",
    "windows": [
        {"label": "Morning",   "start": (7, 0),  "end": (9, 0)},
        {"label": "Afternoon", "start": (12, 0), "end": (14, 0)},
        {"label": "Evening",   "start": (18, 0), "end": (20, 30)},
    ],
    "pets": [
        {
            "name": "Max", "species": "Dog", "age": 4, "breed": "Labrador Retriever",
            "tasks": [
                {"name": "Breakfast",       "description": "Two cups of dry kibble with a splash of broth",    "category": "food",           "priority": "critical", "duration": 10, "window": "Morning",   "frequency": "daily"},
                {"name": "Morning Walk",    "description": "30-minute walk around the neighbourhood",          "category": "daily_activity", "priority": "high",     "duration": 30, "window": "Morning",   "frequency": "daily"},
                {"name": "Bath Time",       "description": "Full shampoo, rinse and blow-dry",                 "category": "grooming",       "priority": "high",     "duration": 60, "window": "Morning",   "frequency": "weekly"},
                {"name": "Training",        "description": "Sit, stay, and recall practice with treats",       "category": "enrichment",     "priority": "medium",   "duration": 20, "window": "Afternoon", "frequency": "daily"},
                {"name": "Evening Walk",    "description": "45-minute off-leash run at the park",              "category": "daily_activity", "priority": "high",     "duration": 45, "window": "Evening",   "frequency": "daily"},
                {"name": "Dental Chew",     "description": "One enzymatic chew for oral health",               "category": "healthcare",     "priority": "low",      "duration": 5,  "window": "Evening",   "frequency": "daily"},
            ],
        },
        {
            "name": "Whiskers", "species": "Cat", "age": 3, "breed": "Persian",
            "tasks": [
                {"name": "Wet Food",        "description": "Half a can of pâté, morning portion",              "category": "food",           "priority": "critical", "duration": 10, "window": "Morning",   "frequency": "daily"},
                {"name": "Litter Box",      "description": "Scoop and refresh litter tray",                    "category": "daily_activity", "priority": "high",     "duration": 10, "window": "Morning",   "frequency": "daily"},
                {"name": "Vet Appointment", "description": "Annual check-up and booster vaccination",          "category": "healthcare",     "priority": "critical", "duration": 70, "window": "Afternoon", "frequency": "once"},
                {"name": "Coat Brushing",   "description": "Daily brush to prevent matting on long fur",       "category": "grooming",       "priority": "medium",   "duration": 15, "window": "Afternoon", "frequency": "daily"},
                {"name": "Playtime",        "description": "Wand toy and laser pointer session",               "category": "enrichment",     "priority": "medium",   "duration": 20, "window": "Evening",   "frequency": "daily"},
            ],
        },
        {
            "name": "Mango", "species": "Bird", "age": 2, "breed": "Cockatiel",
            "tasks": [
                {"name": "Water & Seeds",   "description": "Refill water dish and top up seed mix",            "category": "food",           "priority": "critical", "duration": 5,  "window": "Morning",   "frequency": "daily"},
                {"name": "Cage Clean",      "description": "Remove droppings and replace cage liner",          "category": "daily_activity", "priority": "high",     "duration": 15, "window": "Morning",   "frequency": "daily"},
                {"name": "Fruit & Veggies", "description": "Offer a small piece of apple and leafy greens",    "category": "food",           "priority": "high",     "duration": 5,  "window": "Afternoon", "frequency": "daily"},
                {"name": "Socialisation",   "description": "Out-of-cage time, talking and gentle handling",    "category": "enrichment",     "priority": "medium",   "duration": 20, "window": "Afternoon", "frequency": "daily"},
                {"name": "Health Check",    "description": "Visual check of feathers, eyes, and feet",         "category": "healthcare",     "priority": "low",      "duration": 5,  "window": "Afternoon", "frequency": "weekly"},
                {"name": "Cover Cage",      "description": "Drape sleep cover over cage for the night",        "category": "daily_activity", "priority": "low",      "duration": 5,  "window": "Evening",   "frequency": "daily"},
            ],
        },
    ],
}

_TERMINAL_DATA = {
    "owner": "Alex Rivera",
    "windows": [
        {"label": "Morning",   "start": (7, 0),  "end": (9, 0)},
        {"label": "Afternoon", "start": (12, 0), "end": (13, 30)},
        {"label": "Evening",   "start": (18, 0), "end": (20, 0)},
    ],
    "pets": [
        {
            "name": "Buddy", "species": "Dog", "age": 3, "breed": "Golden Retriever",
            "tasks": [
                # Added out of order intentionally to demonstrate sorting
                {"name": "Evening Walk",  "description": "45-minute neighbourhood walk",    "category": "daily_activity", "priority": "high",     "duration": 45, "window": "Evening",   "frequency": "daily"},
                {"name": "Breakfast",     "description": "Serve one cup of dry kibble",     "category": "food",           "priority": "critical", "duration": 10, "window": "Morning",   "frequency": "daily"},
                {"name": "Morning Walk",  "description": "30-minute walk around the block", "category": "daily_activity", "priority": "high",     "duration": 30, "window": "Morning",   "frequency": "daily"},
                {"name": "Bath Time",     "description": "Full shampoo, rinse and blow-dry","category": "grooming",       "priority": "high",     "duration": 90, "window": "Morning",   "frequency": "weekly"},
                {"name": "Vet Checkup",   "description": "Annual physical and vaccinations","category": "healthcare",     "priority": "critical", "duration": 75, "window": "Afternoon", "frequency": "once"},
            ],
        },
        {
            "name": "Luna", "species": "Cat", "age": 5, "breed": "Siamese",
            "tasks": [
                {"name": "Playtime",      "description": "Interactive wand toy session",    "category": "enrichment",     "priority": "medium",   "duration": 20, "window": "Afternoon", "frequency": "daily"},
                {"name": "Grooming",      "description": "Brush coat and check ears",       "category": "grooming",       "priority": "low",      "duration": 15, "window": "Evening",   "frequency": "weekly"},
                {"name": "Lunch Feeding", "description": "Half a can of wet food",          "category": "food",           "priority": "high",     "duration": 10, "window": "Afternoon", "frequency": "daily"},
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Builder — shared by load_demo() and the terminal entry point
# ---------------------------------------------------------------------------

def _build_owner(data: dict) -> Owner:
    """Construct an Owner with pets and tasks from a data dictionary."""
    windows = {
        w["label"]: TimeWindow(w["label"], time(*w["start"]), time(*w["end"]))
        for w in data["windows"]
    }

    owner = Owner(name=data["owner"])
    owner.available_windows = list(windows.values())

    for pet_data in data["pets"]:
        pet = Pet(
            name=pet_data["name"],
            species=pet_data["species"],
            age=pet_data["age"],
            breed=pet_data.get("breed", ""),
        )
        for t in pet_data["tasks"]:
            pet.add_task(
                name=t["name"],
                description=t["description"],
                category=TaskCategory(t["category"]),
                priority=Priority(t["priority"]),
                duration_minutes=t["duration"],
                preferred_window=windows.get(t["window"]),
                frequency=Frequency(t["frequency"]),
            )
        owner.add_pet(pet)

    return owner


# ---------------------------------------------------------------------------
# Public API — imported by app.py for the "Load Demo" button
# ---------------------------------------------------------------------------

def load_demo() -> Owner:
    return _build_owner(_DEMO_DATA)


# ---------------------------------------------------------------------------
# Terminal entry point — run with: python main.py
# ---------------------------------------------------------------------------

def _print_schedule(schedule, owner: Owner) -> None:
    pet_lookup = {p.id: p.name for p in owner.pets}

    print("=" * 52)
    print(f"  PawPal+ — Schedule ({schedule.date})")
    print(f"  Owner: {owner.name}")
    print("=" * 52)

    if schedule.tasks:
        for task in schedule.tasks:
            pet_name = pet_lookup.get(task.pet_id, "Unknown")
            due = str(task.due_date) if task.due_date else "no due date"
            conflict = " ⚠ CONFLICT" if task.id in schedule.conflicted_task_ids else ""
            print(f"  {due}  [{pet_name}]  {task.name}{conflict}")
            print(f"               {task.description}")
    else:
        print("  No pending tasks.")

    print("-" * 52)

    if schedule.warnings:
        print("\n  Warnings:")
        for w in schedule.warnings:
            print(f"    ! {w}")

    if schedule.suggestions:
        print("\n  Suggestions:")
        for s in schedule.suggestions:
            print(f"    > {s}")

    print("=" * 52)


if __name__ == "__main__":
    owner = _build_owner(_TERMINAL_DATA)
    scheduler = Scheduler()
    schedule = scheduler.generate(owner, date.today())

    _print_schedule(schedule, owner)

    # Sorting demo
    all_tasks = owner.get_all_tasks()

    print("\n  Tasks as added (original order):")
    for t in all_tasks:
        label = t.preferred_window.label if t.preferred_window else "No window"
        print(f"    [{label:10}]  {t.name}")

    print("\n  Tasks sorted by time (ascending):")
    for t in scheduler.sort_by_time(all_tasks):
        label = t.preferred_window.label if t.preferred_window else "No window"
        print(f"    [{label:10}]  {t.name}")

    # Filtering demo
    buddy = next(p for p in owner.pets if p.name == "Buddy")
    pet_lookup = {p.id: p.name for p in owner.pets}

    print("\n  Tasks — Buddy only:")
    for t in scheduler.filter_tasks(schedule.tasks, pet_id=buddy.id):
        print(f"    {t.due_date}  {t.name}")

    print("\n  Tasks — incomplete only:")
    for t in scheduler.filter_tasks(schedule.tasks, completed=False):
        print(f"    [{pet_lookup.get(t.pet_id, '?'):6}]  {t.name}  (completed={t.completed})")

    print("=" * 52)
