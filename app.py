import streamlit as st
from datetime import date
from datetime import time
from pawpal_system import (
    Pet, Owner, Priority, TaskCategory, Frequency,
    Scheduler, TimeWindow
)
from main import load_demo

def _save():
    if st.session_state.get("owner"):
        st.session_state.owner.save_to_json()

# Predefined catalogue of time windows owners can choose from
_ALL_WINDOWS: dict[str, TimeWindow] = {
    "Early Morning": TimeWindow("Early Morning", time(5, 0),  time(7, 0)),
    "Morning":       TimeWindow("Morning",       time(7, 0),  time(9, 0)),
    "Mid-Morning":   TimeWindow("Mid-Morning",   time(9, 0),  time(11, 0)),
    "Afternoon":     TimeWindow("Afternoon",     time(12, 0), time(14, 0)),
    "Late Afternoon":TimeWindow("Late Afternoon",time(15, 0), time(17, 0)),
    "Evening":       TimeWindow("Evening",       time(18, 0), time(20, 30)),
    "Night":         TimeWindow("Night",         time(21, 0), time(23, 0)),
}

_PRIORITY_BADGE = {
    Priority.CRITICAL: '<span style="color:#dc2626;font-weight:600">⬤ critical</span>',
    Priority.HIGH:     '<span style="color:#ea580c;font-weight:600">⬤ high</span>',
    Priority.MEDIUM:   '<span style="color:#ca8a04;font-weight:600">⬤ medium</span>',
    Priority.LOW:      '<span style="color:#16a34a;font-weight:600">⬤ low</span>',
}

_CATEGORY_ICON = {
    TaskCategory.FOOD:           "🍖",
    TaskCategory.HEALTHCARE:     "💊",
    TaskCategory.DAILY_ACTIVITY: "🏃",
    TaskCategory.GROOMING:       "✂️",
    TaskCategory.ENRICHMENT:     "🧸",
    TaskCategory.OTHER:          "📋",
}

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("Pet care planning assistant — sort, filter, and schedule tasks for all your pets.")

st.divider()

if "owner" not in st.session_state:
    st.session_state.owner = Owner.load_from_json()
if "show_owner_edit" not in st.session_state:
    st.session_state.show_owner_edit = False

_all_window_labels = list(_ALL_WINDOWS.keys())

# --- No owner yet: show setup form ---
if st.session_state.owner is None:
    st.subheader("Who are you?")
    with st.container(border=True):
        new_owner_name = st.text_input("Your name", placeholder="e.g. Jordan")
        new_window_labels = st.multiselect(
            "Preferred time windows",
            options=_all_window_labels,
            default=_all_window_labels,
            help="All windows selected by default.",
        )
        if st.button("Get started", type="primary"):
            if not new_owner_name.strip():
                st.error("Please enter your name.")
            else:
                owner = Owner(name=new_owner_name.strip())
                owner.available_windows = [_ALL_WINDOWS[l] for l in new_window_labels]
                st.session_state.owner = owner
                _save()
                st.rerun()
    st.stop()

# --- Owner exists: show summary header ---
owner = st.session_state.owner
_current_labels = [w.label for w in owner.available_windows if w.label in _ALL_WINDOWS]
_custom_windows = set(_current_labels) != set(_all_window_labels)

name_col, edit_col = st.columns([8, 1])
with name_col:
    window_info = " · ".join(_current_labels) if _custom_windows else "All windows"
    st.markdown(f"### {owner.name} &nbsp; <span style='font-size:0.9rem;font-weight:normal;color:gray'>{window_info}</span>", unsafe_allow_html=True)
with edit_col:
    if st.button("✎ Edit", key="edit_owner_btn"):
        st.session_state.show_owner_edit = not st.session_state.show_owner_edit
        st.rerun()

if st.session_state.show_owner_edit:
    with st.container(border=True):
        edited_name = st.text_input("Your name", value=owner.name, key="owner_edit_name")
        edited_windows = st.multiselect(
            "Preferred time windows",
            options=_all_window_labels,
            default=_current_labels if _current_labels else _all_window_labels,
            key="owner_edit_windows",
            help="All windows selected by default.",
        )
        save_col, _, cancel_col = st.columns([2, 6, 2])
        if save_col.button("Save", type="primary", key="owner_save", use_container_width=True):
            if not (edited_name or "").strip():
                st.error("Name cannot be empty.")
            else:
                owner.name = (edited_name or "").strip()
                owner.available_windows = [_ALL_WINDOWS[l] for l in edited_windows]
                st.session_state.show_owner_edit = False
                _save()
                st.rerun()
        if cancel_col.button("Cancel", key="owner_cancel", use_container_width=True):
            st.session_state.show_owner_edit = False
            st.rerun()

if "pet_form_key" not in st.session_state:
    st.session_state.pet_form_key = 0
if "show_add_pet_form" not in st.session_state:
    st.session_state.show_add_pet_form = False
if "editing_pet_id" not in st.session_state:
    st.session_state.editing_pet_id = None
if "deleting_pet_id" not in st.session_state:
    st.session_state.deleting_pet_id = None

st.markdown("### Pets")

_SPECIES_ICON = {"dog": "🐶", "cat": "🐱", "other": "🐾"}

if st.session_state.owner.pets:
    _PET_COLS = [1, 3, 2, 1, 1, 1]
    _PET_LABELS = ["#", "name", "species", "age", "", ""]
    hcols = st.columns(_PET_COLS)
    for col, label in zip(hcols, _PET_LABELS):
        col.markdown(f"**{label}**")

    for i, p in enumerate(st.session_state.owner.pets, start=1):
        row = st.columns(_PET_COLS)
        row[0].write(i)
        row[1].write(p.name)
        row[2].write(f"{_SPECIES_ICON.get(p.species, '🐾')} {p.species}")
        row[3].write(p.age)

        is_editing_pet = st.session_state.editing_pet_id == p.id
        is_confirming_pet_delete = st.session_state.deleting_pet_id == p.id

        if row[4].button("✎", key=f"edit_pet_btn_{p.id}", help="Edit pet"):
            st.session_state.editing_pet_id = None if is_editing_pet else p.id
            st.session_state.deleting_pet_id = None
            st.rerun()
        if row[5].button("✖", key=f"del_pet_{p.id}", help="Delete pet"):
            st.session_state.deleting_pet_id = None if is_confirming_pet_delete else p.id
            st.session_state.editing_pet_id = None
            st.rerun()

        if is_confirming_pet_delete:
            st.warning(
                f"Delete **{p.name}**? This will also remove all their tasks and cannot be undone.",
                icon="⚠️",
            )
            confirm_col, cancel_col = st.columns([1, 5])
            if confirm_col.button("Yes, delete", key=f"confirm_del_pet_{p.id}", type="primary"):
                try:
                    st.session_state.owner.delete_pet(p.id)
                    st.session_state.deleting_pet_id = None
                    if "last_schedule" in st.session_state:
                        del st.session_state.last_schedule
                    _save()
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if cancel_col.button("Cancel", key=f"cancel_del_pet_{p.id}"):
                st.session_state.deleting_pet_id = None
                st.rerun()

        if is_editing_pet:
            with st.container(border=True):
                ecol1, ecol2, ecol3 = st.columns(3)
                new_pet_name = ecol1.text_input("Name", value=p.name, key=f"ep_name_{p.id}")
                new_species = ecol2.selectbox(
                    "Species", ["dog", "cat", "other"],
                    index=["dog", "cat", "other"].index(p.species) if p.species in ["dog", "cat", "other"] else 2,
                    key=f"ep_species_{p.id}",
                )
                new_age = ecol3.number_input("Age", min_value=0, max_value=30, value=p.age, key=f"ep_age_{p.id}")

                save_col, _, cancel_col = st.columns([2, 6, 2])
                if save_col.button("Save", key=f"save_pet_{p.id}", type="primary", use_container_width=True):
                    if not (new_pet_name or "").strip():
                        st.error("Name cannot be empty.")
                    else:
                        try:
                            st.session_state.owner.edit_pet(
                                p.id,
                                name=(new_pet_name or "").strip(),
                                species=new_species,
                                age=int(new_age),
                            )
                            st.session_state.editing_pet_id = None
                            _save()
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                if cancel_col.button("Cancel", key=f"cancel_pet_{p.id}", use_container_width=True):
                    st.session_state.editing_pet_id = None
                    st.rerun()

if not st.session_state.show_add_pet_form:
    _, btn_col, _ = st.columns([2, 2, 2])
    if btn_col.button("+ Add A New Pet", key="toggle_add_pet", use_container_width=True):
        st.session_state.show_add_pet_form = True
        st.rerun()

if st.session_state.show_add_pet_form:
    with st.container(border=True):
        fk = st.session_state.pet_form_key
        col1, col2, col3 = st.columns(3)
        with col1:
            pet_name = st.text_input("Pet name", key=f"pet_name_{fk}")
        with col2:
            species = st.selectbox("Species", ["dog", "cat", "other"], key=f"pet_species_{fk}")
        with col3:
            pet_age = st.number_input("Age", min_value=0, max_value=30, key=f"pet_age_{fk}")

        add_col, _, close_col = st.columns([2, 6, 2])
        if add_col.button("Add pet", type="primary", use_container_width=True):
            if not pet_name.strip():
                st.error("Pet name cannot be empty.")
            else:
                try:
                    new_pet = Pet(name=pet_name.strip(), species=species, age=pet_age)
                    st.session_state.owner.add_pet(new_pet)
                    st.session_state.pet_form_key += 1
                    st.session_state.show_add_pet_form = False
                    _save()
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        if close_col.button("✕ Close", key="close_add_pet", use_container_width=True):
            st.session_state.show_add_pet_form = False
            st.rerun()

st.markdown("### Tasks")

if "task_form_key" not in st.session_state:
    st.session_state.task_form_key = 0
if "show_add_task_form" not in st.session_state:
    st.session_state.show_add_task_form = False

has_pets = bool(st.session_state.owner.pets)
all_tasks = st.session_state.owner.get_all_tasks() if has_pets else []

if all_tasks:
    pet_lookup = {p.id: p.name for p in st.session_state.owner.pets}
    pet_by_id = {p.id: p for p in st.session_state.owner.pets}

    if "editing_task_id" not in st.session_state:
        st.session_state.editing_task_id = None
    if "deleting_task_id" not in st.session_state:
        st.session_state.deleting_task_id = None

    st.write(f"Tasks ({len(all_tasks)}):")

    # Header row
    _TASK_COLS = [1, 2, 2, 2, 2, 1, 1, 1]
    _TASK_LABELS = ["#", "pet", "name", "category", "priority", "min", "", ""]
    hcols = st.columns(_TASK_COLS)
    for col, label in zip(hcols, _TASK_LABELS):
        col.markdown(f"**{label}**")

    for i, t in enumerate(all_tasks, start=1):
        row = st.columns(_TASK_COLS)
        row[0].write(i)
        row[1].write(pet_lookup.get(t.pet_id, "?"))
        row[2].write(t.name)
        row[3].write(t.category.value)
        row[4].markdown(_PRIORITY_BADGE.get(t.priority, t.priority.value), unsafe_allow_html=True)
        row[5].write(t.duration_minutes)

        is_editing = st.session_state.editing_task_id == t.id
        is_confirming_delete = st.session_state.deleting_task_id == t.id
        if row[6].button("✎", key=f"edit_btn_{t.id}", help="Edit task"):
            st.session_state.editing_task_id = None if is_editing else t.id
            st.session_state.deleting_task_id = None
            st.rerun()
        if row[7].button("✖", key=f"del_{t.id}", help="Delete task"):
            st.session_state.deleting_task_id = None if is_confirming_delete else t.id
            st.session_state.editing_task_id = None
            st.rerun()

        if is_confirming_delete:
            st.warning(
                f"Delete **{t.name}** for **{pet_lookup.get(t.pet_id, '?')}**? This cannot be undone.",
                icon="⚠️",
            )
            confirm_col, cancel_col = st.columns([1, 5])
            if confirm_col.button("Yes, delete", key=f"confirm_del_{t.id}", type="primary"):
                try:
                    pet_by_id[t.pet_id].delete_task(t.id)
                    st.session_state.deleting_task_id = None
                    if "last_schedule" in st.session_state:
                        del st.session_state.last_schedule
                    _save()
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if cancel_col.button("Cancel", key=f"cancel_del_{t.id}"):
                st.session_state.deleting_task_id = None
                st.rerun()

        # Inline edit form — shown only for the selected row
        if is_editing:
            with st.container(border=True):
                ecol1, ecol2 = st.columns(2)
                new_name = ecol1.text_input("Name", value=t.name, key=f"e_name_{t.id}")
                new_desc = ecol2.text_input("Description", value=t.description, key=f"e_desc_{t.id}")

                ecol3, ecol4, ecol5 = st.columns(3)
                new_category = ecol3.selectbox(
                    "Category", [c.value for c in TaskCategory],
                    index=[c.value for c in TaskCategory].index(t.category.value),
                    key=f"e_cat_{t.id}",
                )
                new_priority = ecol4.selectbox(
                    "Priority", [p.value for p in Priority],
                    index=[p.value for p in Priority].index(t.priority.value),
                    key=f"e_pri_{t.id}",
                )
                new_duration = ecol5.number_input(
                    "Duration (min)", min_value=1, max_value=240,
                    value=t.duration_minutes, key=f"e_dur_{t.id}",
                )

                ecol6, ecol7 = st.columns(2)
                new_frequency = ecol6.selectbox(
                    "Frequency", [f.value for f in Frequency],
                    index=[f.value for f in Frequency].index(t.frequency.value),
                    key=f"e_freq_{t.id}",
                )
                window_options = ["None"] + [w.label for w in st.session_state.owner.available_windows]
                current_window = t.preferred_window.label if t.preferred_window else "None"
                win_index = window_options.index(current_window) if current_window in window_options else 0
                new_window_label = ecol7.selectbox(
                    "Time window", window_options, index=win_index, key=f"e_win_{t.id}",
                )

                save_col, _, cancel_col = st.columns([2, 6, 2])
                if save_col.button("Save", key=f"save_{t.id}", type="primary", use_container_width=True):
                    new_window = next(
                        (w for w in st.session_state.owner.available_windows if w.label == new_window_label),
                        None,
                    )
                    try:
                        pet_by_id[t.pet_id].edit_task(
                            t.id,
                            name=(new_name or "").strip(),
                            description=(new_desc or "").strip(),
                            category=TaskCategory(new_category),
                            priority=Priority(new_priority),
                            duration_minutes=int(new_duration),
                            frequency=Frequency(new_frequency),
                            preferred_window=new_window,
                        )
                        st.session_state.editing_task_id = None
                        if "last_schedule" in st.session_state:
                            del st.session_state.last_schedule
                        _save()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                if cancel_col.button("Cancel", key=f"cancel_{t.id}", use_container_width=True):
                    st.session_state.editing_task_id = None
                    st.rerun()

# --- Add task button + form ---
if not has_pets:
    st.info("Add a pet first before adding tasks.")
else:
    if not st.session_state.show_add_task_form:
        _, btn_col, _ = st.columns([2, 2, 2])
        if btn_col.button("+ Add A New Task", use_container_width=True):
            st.session_state.show_add_task_form = True
            st.rerun()

    if st.session_state.show_add_task_form:
        with st.container(border=True):
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

            col6, col7 = st.columns(2)
            with col6:
                task_frequency = st.selectbox("Frequency", [f.value for f in Frequency], key=f"task_freq_{tfk}")
            with col7:
                window_options = ["None"] + [w.label for w in st.session_state.owner.available_windows]
                task_window = st.selectbox("Time window", window_options, key=f"task_window_{tfk}")

            add_col, _, close_col = st.columns([2, 6, 2])
            if add_col.button("Add task", type="primary", use_container_width=True):
                if not task_title.strip():
                    st.error("Task name cannot be empty.")
                else:
                    pet = next(p for p in st.session_state.owner.pets if p.name == task_pet)
                    selected_window = next(
                        (w for w in st.session_state.owner.available_windows if w.label == task_window),
                        None,
                    )
                    try:
                        pet.add_task(
                            name=task_title.strip(),
                            description=task_description.strip(),
                            category=TaskCategory(task_category),
                            priority=Priority(task_priority),
                            duration_minutes=int(task_duration),
                            preferred_window=selected_window,
                            frequency=Frequency(task_frequency),
                        )
                        st.session_state.task_form_key += 1
                        st.session_state.show_add_task_form = False
                        _save()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            if close_col.button("✕ Close", key="close_add_task", use_container_width=True):
                st.session_state.show_add_task_form = False
                st.rerun()

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

        if selected_sort == "Ascending":
            display_tasks = scheduler.sort_by_time(display_tasks)
        elif selected_sort == "Descending":
            display_tasks = list(reversed(scheduler.sort_by_time(display_tasks)))

        conflicted = schedule.conflicted_task_ids

        # Map each conflicted task id to its specific warning message
        conflict_messages: dict[str, str] = {}
        for t in display_tasks:
            if t.id in conflicted:
                msg = next((w for w in schedule.warnings if t.name in w), None)
                if msg:
                    conflict_messages[t.id] = msg

        # --- Summary metrics ---
        total_count = len(display_tasks)
        done_count = sum(1 for t in display_tasks if t.completed)
        conflict_count = sum(1 for t in display_tasks if t.id in conflicted)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total tasks", total_count)
        m2.metric("Completed", done_count)
        m3.metric("Conflicts", conflict_count, delta=f"-{conflict_count}" if conflict_count else None,
                  delta_color="inverse")

        # --- Conflict alerts (prominent, near the top) ---
        if schedule.warnings:
            with st.expander(f"⚠️ {len(schedule.warnings)} scheduling conflict(s) — click to review", expanded=True):
                for warn in schedule.warnings:
                    st.warning(warn)
                st.caption("Conflicted tasks are marked ⚠️ in the list below. Consider shortening them, moving them to a different window, or delegating.")

        # --- Suggestions ---
        if schedule.suggestions:
            with st.expander("💡 Suggestions"):
                for s in schedule.suggestions:
                    st.info(s)

        st.divider()

        # --- Task rows grouped by date ---
        date_counts: dict = {}
        for t in display_tasks:
            key = t.due_date
            total, done = date_counts.get(key, (0, 0))
            date_counts[key] = (total + 1, done + (1 if t.completed else 0))

        header = st.columns([1, 3, 1, 3, 2, 1, 1])
        for col, label in zip(header, ["#", "window", "pet", "task", "priority", "min", ""]):
            col.markdown(f"**{label}**")

        current_date = None
        for row_idx, t in enumerate(display_tasks, start=1):
            row_date = t.due_date
            if row_date != current_date:
                current_date = row_date
                total, done = date_counts.get(row_date, (0, 0))
                date_label = str(row_date) if row_date else "No date"
                pct = done / total if total else 0
                st.markdown(f"**{date_label}** — {done}/{total} tasks completed")
                st.progress(pct)

            is_conflict = t.id in conflicted
            row = st.columns([1, 3, 1, 3, 2, 1, 1])
            row[0].write(row_idx)

            if t.preferred_window:
                start = t.preferred_window.start_time.strftime("%H:%M")
                end = t.preferred_window.end_time.strftime("%H:%M")
                row[1].write(f"{t.preferred_window.label} ({start}–{end})")
            else:
                row[1].write("—")

            row[2].write(pet_lookup.get(t.pet_id, "?"))

            icon = _CATEGORY_ICON.get(t.category, "📋")
            if t.completed:
                task_label = f'<span style="color:#9ca3af;text-decoration:line-through">{icon} {t.name}</span>'
            elif is_conflict:
                task_label = f'<span style="color:#d97706;font-weight:600">{icon} {t.name}</span>'
            else:
                task_label = f"{icon} {t.name}"
            row[3].markdown(task_label, unsafe_allow_html=True)

            row[4].markdown(_PRIORITY_BADGE.get(t.priority, t.priority.value), unsafe_allow_html=True)
            row[5].write(t.duration_minutes)

            if t.completed:
                row[6].markdown("✔")
            else:
                if row[6].button("✔", key=f"complete_{t.id}"):
                    scheduler.mark_task_complete(st.session_state.owner, t.id)
                    st.session_state.last_schedule.refresh(scheduler)
                    _save()
                    st.rerun()

            # Inline conflict warning directly under the affected row
            if is_conflict and t.id in conflict_messages:
                st.warning(f"⚠️ **{pet_lookup.get(t.pet_id, 'Pet')}** — {conflict_messages[t.id]} Tip: shorten this task, move it to a less busy window, or ask a pet sitter to help.")
