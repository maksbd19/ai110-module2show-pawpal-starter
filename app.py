import streamlit as st
from datetime import date, time
from pawpal_system import (
    Task, Pet, Owner, Priority, TaskCategory, Frequency,
    TimeWindow, Scheduler
)

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

st.subheader("Add a Pet")
col1, col2, col3 = st.columns(3)
fk = st.session_state.pet_form_key
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
    st.write("Pets:")
    st.table([{"name": p.name, "species": p.species, "age": p.age}
              for p in st.session_state.owner.pets])

st.markdown("### Tasks")

if "task_form_key" not in st.session_state:
    st.session_state.task_form_key = 0

if st.session_state.owner.pets:
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

    all_tasks = st.session_state.owner.get_all_tasks()
    if all_tasks:
        pet_lookup = {p.id: p.name for p in st.session_state.owner.pets}
        st.write("Tasks:")
        st.table([{"pet": pet_lookup[t.pet_id], "name": t.name, "category": t.category.value,
                   "priority": t.priority.value, "duration": t.duration_minutes}
                  for t in all_tasks])
    else:
        st.info("No tasks yet. Add one above.")
else:
    st.info("Add a pet first before adding tasks.")

st.divider()

st.subheader("Build Schedule")

schedule_date = st.date_input("Schedule date", value=date.today())

if st.button("Generate schedule"):
    if not st.session_state.owner.pets:
        st.error("Add at least one pet before generating a schedule.")
    elif not st.session_state.owner.get_all_tasks():
        st.error("Add at least one task before generating a schedule.")
    else:
        if not st.session_state.owner.available_windows:
            st.session_state.owner.available_windows = [
                TimeWindow(label="All day", start_time=time(0, 0), end_time=time(23, 59))
            ]
        schedule = Scheduler().generate(st.session_state.owner, schedule_date)
        st.session_state.last_schedule = schedule

if "last_schedule" in st.session_state:
    schedule = st.session_state.last_schedule
    pet_lookup = {p.id: p.name for p in st.session_state.owner.pets}

    st.markdown(f"### Schedule for {schedule.date}")
    st.caption(f"Required: {schedule.total_required_minutes} min | Available: {schedule.total_available_minutes} min")

    if schedule.scheduled_tasks:
        st.markdown("**Scheduled tasks**")
        st.table([{
            "time": f"{s.start_time.strftime('%H:%M')} – {s.end_time.strftime('%H:%M')}",
            "pet": pet_lookup.get(s.task.pet_id, "?"),
            "task": s.task.name,
            "priority": s.task.priority.value,
            "duration (min)": s.task.duration_minutes,
        } for s in schedule.scheduled_tasks])

    if schedule.unscheduled_tasks:
        st.markdown("**Could not be scheduled**")
        st.table([{
            "pet": pet_lookup.get(t.pet_id, "?"),
            "task": t.name,
            "priority": t.priority.value,
            "duration (min)": t.duration_minutes,
        } for t in schedule.unscheduled_tasks])

    for w in schedule.warnings:
        st.warning(w)
    for s in schedule.suggestions:
        st.info(s)
