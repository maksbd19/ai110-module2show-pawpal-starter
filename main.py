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
# Setup
# ---------------------------------------------------------------------------

owner = Owner(name="Alex Rivera")

# Available time windows for the owner today
morning = TimeWindow("Morning", time(7, 0), time(9, 0))
afternoon = TimeWindow("Afternoon", time(12, 0), time(13, 30))
evening = TimeWindow("Evening", time(18, 0), time(20, 0))

owner.available_windows = [morning, afternoon, evening]

# ---------------------------------------------------------------------------
# Pets
# ---------------------------------------------------------------------------

buddy = Pet(name="Buddy", species="Dog", age=3, breed="Golden Retriever")
luna = Pet(name="Luna", species="Cat", age=5, breed="Siamese")

owner.add_pet(buddy)
owner.add_pet(luna)

# ---------------------------------------------------------------------------
# Tasks — at least three with different preferred times
# ---------------------------------------------------------------------------

buddy.add_task(
    name="Morning Walk",
    description="30-minute walk around the block",
    category=TaskCategory.DAILY_ACTIVITY,
    priority=Priority.HIGH,
    duration_minutes=30,
    preferred_window=morning,
    frequency=Frequency.DAILY,
)

buddy.add_task(
    name="Breakfast",
    description="Serve one cup of dry kibble",
    category=TaskCategory.FOOD,
    priority=Priority.CRITICAL,
    duration_minutes=10,
    preferred_window=morning,
    frequency=Frequency.DAILY,
)

luna.add_task(
    name="Lunch Feeding",
    description="Half a can of wet food",
    category=TaskCategory.FOOD,
    priority=Priority.HIGH,
    duration_minutes=10,
    preferred_window=afternoon,
    frequency=Frequency.DAILY,
)

luna.add_task(
    name="Playtime",
    description="Interactive wand toy session",
    category=TaskCategory.ENRICHMENT,
    priority=Priority.MEDIUM,
    duration_minutes=20,
    preferred_window=afternoon,
    frequency=Frequency.DAILY,
)

buddy.add_task(
    name="Evening Walk",
    description="45-minute neighbourhood walk",
    category=TaskCategory.DAILY_ACTIVITY,
    priority=Priority.HIGH,
    duration_minutes=45,
    preferred_window=evening,
    frequency=Frequency.DAILY,
)

luna.add_task(
    name="Grooming",
    description="Brush coat and check ears",
    category=TaskCategory.GROOMING,
    priority=Priority.LOW,
    duration_minutes=15,
    preferred_window=evening,
    frequency=Frequency.WEEKLY,
)

# ---------------------------------------------------------------------------
# Generate and print Today's Schedule
# ---------------------------------------------------------------------------

scheduler = Scheduler()
schedule = scheduler.generate(owner, date.today())

print("=" * 52)
print(f"  PawPal+ — Today's Schedule ({schedule.date})")
print(f"  Owner: {owner.name}")
print("=" * 52)

# Build a pet-name lookup
pet_lookup = {p.id: p.name for p in owner.pets}

if schedule.scheduled_tasks:
    for st in schedule.scheduled_tasks:
        pet_name = pet_lookup.get(st.task.pet_id, "Unknown")
        start = st.start_time.strftime("%I:%M %p")
        end = st.end_time.strftime("%I:%M %p")
        print(f"  {start} – {end}  [{pet_name}]  {st.task.name}")
        print(f"               {st.task.description}")
else:
    print("  No tasks could be scheduled today.")

print("-" * 52)
print(f"  Total required : {schedule.total_required_minutes} min")
print(f"  Total available: {schedule.total_available_minutes} min")

if schedule.unscheduled_tasks:
    print("\n  Unscheduled tasks:")
    for task in schedule.unscheduled_tasks:
        pet_name = pet_lookup.get(task.pet_id, "Unknown")
        print(f"    - [{pet_name}] {task.name} ({task.duration_minutes} min)")

if schedule.warnings:
    print("\n  Warnings:")
    for w in schedule.warnings:
        print(f"    ! {w}")

if schedule.suggestions:
    print("\n  Suggestions:")
    for s in schedule.suggestions:
        print(f"    > {s}")

print("=" * 52)
