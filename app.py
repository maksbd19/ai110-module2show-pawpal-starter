import streamlit as st
from datetime import date, time
from pawpal_system import (
    Task, Pet, Owner, Priority, TaskCategory, Frequency,
    Scheduler
)
from main import load_demo

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Quick Demo Inputs (UI only)")
owner_name = st.text_input("Owner name", value="Jordan")

if "owner" not in st.session_state:
    st.session_state.owner = Owner(name=owner_name)

if "pet_form_key" not in st.session_state:
    st.session_state.pet_form_key = 0

st.markdown("### Pets")
with st.expander("Add a Pet", expanded=not st.session_state.owner.pets):
    fk = st.session_state.pet_form_key
    col1, col2, col3 = st.columns(3)
    with col1:
        pet_name = st.text_input("Pet name", key=f"pet_name_{fk}")
    with col2:
        species = st.selectbox("Species", ["dog", "cat", "other"], key=f"pet_species_{fk}")
    with col3:
        pet_age = st.number_input("Age", min_value=0, max_value=30, key=f"pet_age_{fk}")

    if st.button("Add pet"):
        if not pet_name.strip():
            st.error("Pet name cannot be empty.")
        else:
            try:
                new_pet = Pet(name=pet_name.strip(), species=species, age=pet_age)
                st.session_state.owner.add_pet(new_pet)
                st.session_state.pet_form_key += 1
                st.rerun()
            except ValueError as e:
                st.error(str(e))

if st.session_state.owner.pets:
    st.table([{"name": p.name, "species": p.species, "age": p.age}
              for p in st.session_state.owner.pets])

st.markdown("### Tasks")

if "task_form_key" not in st.session_state:
    st.session_state.task_form_key = 0

has_pets = bool(st.session_state.owner.pets)
all_tasks = st.session_state.owner.get_all_tasks() if has_pets else []

with st.expander("Add a Task", expanded=has_pets and not all_tasks):
    if not has_pets:
        st.info("Add a pet first before adding tasks.")
    else:
        tfk = st.session_state.task_form_key
        pet_names = [p.name for p in st.session_state.owner.pets]

        col1, col2 = st.columns(2)
        with col1:
            task_title = st.text_input("Task name", key=f"task_name_{tfk}")
        with col2:
            task_pet = st.selectbox("Pet", pet_names, key=f"task_pet_{tfk}")

        col3, col4, col5 = st.columns(3)
        with col3:
            task_category = st.selectbox("Category", [c.value for c in TaskCategory], key=f"task_cat_{tfk}")
        with col4:
            task_priority = st.selectbox("Priority", [p.value for p in Priority], key=f"task_pri_{tfk}")
        with col5:
            task_duration = st.number_input("Duration (min)", min_value=1, max_value=240, key=f"task_dur_{tfk}")

        task_description = st.text_input("Description", key=f"task_desc_{tfk}")
        task_frequency = st.selectbox("Frequency", [f.value for f in Frequency], key=f"task_freq_{tfk}")

        if st.button("Add task"):
            if not task_title.strip():
                st.error("Task name cannot be empty.")
            else:
                pet = next(p for p in st.session_state.owner.pets if p.name == task_pet)
                try:
                    pet.add_task(
                        name=task_title.strip(),
                        description=task_description.strip(),
                        category=TaskCategory(task_category),
                        priority=Priority(task_priority),
                        duration_minutes=int(task_duration),
                        frequency=Frequency(task_frequency),
                    )
                    st.session_state.task_form_key += 1
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

if all_tasks:
    pet_lookup = {p.id: p.name for p in st.session_state.owner.pets}
    st.write("Tasks:")
    st.table([{"pet": pet_lookup[t.pet_id], "name": t.name, "category": t.category.value,
               "priority": t.priority.value, "duration": t.duration_minutes}
              for t in all_tasks])

st.divider()

st.subheader("Build Schedule")

if st.button("Generate schedule"):
    if not st.session_state.owner.pets:
        st.error("Add at least one pet before generating a schedule.")
    elif not st.session_state.owner.get_all_tasks():
        st.error("Add at least one task before generating a schedule.")
    else:
        schedule = Scheduler().generate(st.session_state.owner, date.today())
        st.session_state.last_schedule = schedule

if "last_schedule" in st.session_state:
    schedule = st.session_state.last_schedule
    pet_lookup = {p.id: p.name for p in st.session_state.owner.pets}

    st.markdown("### Schedule")

    if schedule.tasks:
        st.markdown("**Tasks**")

        ctrl_col, filter_col, status_col = st.columns([2, 2, 2])
        with ctrl_col:
            selected_sort = st.selectbox(
                "Sort by date & time",
                ["Default", "Ascending", "Descending"],
                key="due_date_sort",
            )
        with filter_col:
            pet_options = ["All pets"] + [p.name for p in st.session_state.owner.pets]
            selected_pet = st.selectbox(
                "Filter by pet",
                pet_options,
                key="pet_filter",
            )
        with status_col:
            selected_status = st.selectbox(
                "Filter by status",
                ["All", "Incomplete", "Completed"],
                key="status_filter",
            )

        scheduler = Scheduler()
        pet_id_filter = None
        if selected_pet != "All pets":
            matched = next(
                (p.id for p in st.session_state.owner.pets if p.name == selected_pet),
                None,
            )
            pet_id_filter = matched

        completed_filter = None
        if selected_status == "Completed":
            completed_filter = True
        elif selected_status == "Incomplete":
            completed_filter = False

        display_tasks = scheduler.filter_tasks(
            schedule.tasks,
            pet_id=pet_id_filter,
            completed=completed_filter,
        )
        def _sort_key(t):
            d = t.due_date or date.max
            w = t.preferred_window.start_time if t.preferred_window else time.max
            return (d, w)

        if selected_sort == "Ascending":
            display_tasks = sorted(display_tasks, key=_sort_key)
        elif selected_sort == "Descending":
            display_tasks = sorted(display_tasks, key=_sort_key, reverse=True)

        conflicted = schedule.conflicted_task_ids

        date_counts: dict = {}
        for t in display_tasks:
            key = t.due_date
            total, done = date_counts.get(key, (0, 0))
            date_counts[key] = (total + 1, done + (1 if t.completed else 0))

        header = st.columns([2, 1, 2, 1, 1, 1, 1])
        for col, label in zip(header, ["time", "pet", "task", "priority", "min", "", ""]):
            col.markdown(f"**{label}**")

        current_date = None
        for t in display_tasks:
            row_date = t.due_date
            if row_date != current_date:
                current_date = row_date
                total, done = date_counts.get(row_date, (0, 0))
                label = str(row_date) if row_date else "No date"
                st.markdown(f"**{label}** — {done}/{total} completed")

            row = st.columns([2, 1, 2, 1, 1, 1, 1])
            if t.preferred_window:
                start = t.preferred_window.start_time.strftime("%H:%M")
                end = t.preferred_window.end_time.strftime("%H:%M")
                row[0].write(f"{start}–{end}")
            else:
                row[0].write("—")
            row[1].write(pet_lookup.get(t.pet_id, "?"))
            row[2].write(t.name)
            row[3].write(t.priority.value)
            row[4].write(t.duration_minutes)
            if t.id in conflicted:
                row[5].write("⚠️")
            if t.completed:
                row[6].write("✓")
            else:
                if row[6].button("Done", key=f"complete_{t.id}"):
                    scheduler.mark_task_complete(st.session_state.owner, t.id)
                    st.session_state.last_schedule.refresh(scheduler)
                    st.rerun()

    if schedule.warnings:
        st.warning("\n\n".join(schedule.warnings))
    if schedule.suggestions:
        st.info("\n\n".join(schedule.suggestions))
