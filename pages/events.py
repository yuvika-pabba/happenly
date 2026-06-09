import streamlit as st
from supabase import create_client, Client
from streamlit_calendar import calendar
import plotly.express as px
from datetime import date, time, datetime, timedelta



@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
    key = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)


supabase: Client = init_connection()

if "session" in st.session_state:
    supabase.auth.set_session(
        st.session_state["session"].access_token,
        st.session_state["session"].refresh_token
    )



def get_auth_user():
    """
    Get the Supabase auth user stored in session_state by main.py.
    If not present, show a warning and stop the script.
   """
    user = st.session_state.get("user")
    if not user:
        st.warning("Please log in first from the main page.")
        st.stop()
    return user


def get_app_user_id(auth_user):
    """
    Use Supabase Auth user id directly.
    This avoids inserting into the custom users table.
    """
    return str(auth_user.id)


def load_events(auth_id: str):
    res = (
        supabase.table("events")
        .select("*")
        .eq("auth_user_id", auth_id)
        .order("date")
        .execute()
    )
    return res.data or []



def event_selectbox(events, key="event_select"):
    """
    Let the user pick an event; returns the chosen eventid.
    """
    if not events:
        st.info("No events yet. Create one in the **Events** tab first.")
        return None

    options = {
        f"{e['title']} ({e['date']})": e["eventid"]
        for e in events
    }
    label = st.selectbox("Select Event", list(options.keys()), key=key)
    return options[label]


# ---------- Layout ----------

st.set_page_config(page_title="Happenly - Events", page_icon="📅", layout="wide")

auth_user = get_auth_user()
app_user_id = get_app_user_id(auth_user)

st.title("Happenly Event Manager")
st.caption(f"Logged in as: {auth_user.email}")

logout_col, _ = st.columns([1, 5])
with logout_col:
    if st.button("Log out"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.session_state.clear()
        st.switch_page("main.py")

st.write("---")

# Load events for this user once
events = load_events(app_user_id)

tab_events, tab_guests, tab_vendors, tab_tasks, tab_dashboard = st.tabs(
    ["Events", "Guests", "Vendors", "Tasks", "Dashboard"]
)

# ---------- EVENTS TAB ----------

with tab_events:
    st.subheader("Create New Event")

    with st.form("create_event_form", clear_on_submit=True):
        title = st.text_input("Title *")
        description = st.text_area("Description")
        c1, c2 = st.columns(2)
        with c1:
            ev_date = st.date_input("Date *", value=date.today())
        with c2:
            ev_time = st.time_input("Time", value=time(18, 0))  

        venue = st.text_input("Venue")
        category = st.text_input("Category (e.g., Birthday, Graduation)")
        budget = st.number_input(
            "Budget", min_value=0.0, step=100.0, format="%.2f"
        )
        status = st.selectbox(
            "Status",
            ["upcoming", "ongoing", "completed"],
            index=0,
        )

        create_submit = st.form_submit_button("Create Event")

    if create_submit:
        if not title:
            st.error("Title is required.")
        else:
            data = {
                "title": title,
                "description": description or None,
                "date": ev_date.isoformat(),
                "time": ev_time.strftime("%H:%M:%S"),
                "venue": venue or None,
                "category": category or None,
                "budget": budget,
                "status": status,
                "auth_user_id": app_user_id,
            }
            try:
                supabase.table("events").insert(data).execute()
                st.success("Event created successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Could not create event: {e}")

    st.write("---")
    st.subheader("Your Events")

    events = load_events(app_user_id)
    if not events:
        st.info("No events yet. Use the form above to create one.")
    else:
        for e in events:
            with st.expander(f"{e['title']}  ({e['date']})  – {e['status']}"):
                col1, col2, col3 = st.columns([3, 2, 1])

                with col1:
                    st.markdown(f"**Venue:** {e.get('venue') or '—'}")
                    st.markdown(f"**Category:** {e.get('category') or '—'}")
                    st.markdown(f"**Budget:** {e.get('budget') or 0}")

                with col2:
                    new_status = st.selectbox(
                        "Status",
                        ["upcoming", "ongoing", "completed"],
                        index=["upcoming", "ongoing", "completed"].index(e["status"]),
                        key=f"status_{e['eventid']}",
                    )
                    new_budget = st.number_input(
                        "Update Budget",
                        value=float(e["budget"] or 0),
                        key=f"budget_{e['eventid']}",
                    )

                with col3:
                    if st.button(
                        "Save Changes", key=f"save_{e['eventid']}"
                    ):
                        try:
                            supabase.table("events").update(
                                {"status": new_status, "budget": new_budget}
                            ).eq("eventid", e["eventid"]).execute()
                            st.success("Event updated.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Update failed: {ex}")

                    if st.button("Delete Event", key=f"delete_{e['eventid']}"):
                        try:
                            supabase.table("tasks").delete().eq("eventid", e["eventid"]).execute()
                            supabase.table("guests").delete().eq("eventid", e["eventid"]).execute()
                            supabase.table("vendors").delete().eq("eventid", e["eventid"]).execute()

                            supabase.table("events").delete().eq("eventid", e["eventid"]).execute()
                            st.warning("Event and related data deleted.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Delete failed: {ex}")


# ---------- GUESTS TAB ----------

with tab_guests:
    st.subheader("Guests")

    events = load_events(app_user_id)
    selected_event_id = event_selectbox(events, key="guest_event_select")

    if selected_event_id:
        st.markdown("### Guests for Selected Event")

        # Load guests
        guests_res = (
            supabase.table("guests")
            .select("*")
            .eq("eventid", selected_event_id)
            .execute()
        )
        guests = guests_res.data or []

        if guests:
            st.dataframe(
                [
                    {
                        "Name": g["name"],
                        "Email": g["email"],
                        "Contact": g["contactnumber"],
                        "RSVP": g["rsvpstatus"],
                    }
                    for g in guests
                ]
            )
        else:
            st.info("No guests added yet.")

        st.write("#### Add Guest")
        with st.form("add_guest_form", clear_on_submit=True):
            g_name = st.text_input("Name")
            g_email = st.text_input("Email")
            g_contact = st.text_input("Contact Number")
            g_rsvp = st.selectbox(
                "RSVP Status", ["Pending", "Accepted", "Declined"], index=0
            )
            guest_submit = st.form_submit_button("Add Guest")

        if guest_submit:
            if not g_name or not g_email:
                st.error("Name and email are required.")
            else:
                try:
                    supabase.table("guests").insert(
                        {
                            "name": g_name,
                            "email": g_email,
                            "contactnumber": g_contact or None,
                            "rsvpstatus": g_rsvp,
                            "eventid": selected_event_id,
                        }
                    ).execute()
                    st.success("Guest added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add guest: {e}")

        st.write("#### Update Guest RSVP")
        for g in guests:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(g["name"])
            with col2:
                new_rsvp = st.selectbox(
                    "RSVP",
                    ["Pending", "Accepted", "Declined"],
                    index=["Pending", "Accepted", "Declined"].index(g["rsvpstatus"]),
                    key=f"rsvp_{g['guestid']}",
                )
            with col3:
                if st.button("Save", key=f"update_guest_{g['guestid']}"):
                    try:
                        supabase.table("guests").update(
                            {"rsvpstatus": new_rsvp}
                        ).eq("guestid", g["guestid"]).execute()
                        st.success("RSVP updated.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Update failed: {ex}")

# ---------- VENDORS TAB ----------

with tab_vendors:
    st.subheader("Vendors")

    events = load_events(app_user_id)
    selected_event_id = event_selectbox(events, key="vendor_event_select")

    if selected_event_id:
        vendors_res = (
            supabase.table("vendors")
            .select("*")
            .eq("eventid", selected_event_id)
            .execute()
        )
        vendors = vendors_res.data or []

        if vendors:
            st.dataframe(
                [
                    {
                        "Name": v["name"],
                        "Type": v["type"],
                        "Contact": v["contactinfo"],
                        "Cost": v["cost"],
                    }
                    for v in vendors
                ]
            )
        else:
            st.info("No vendors added yet.")

        st.write("#### Add Vendor")
        with st.form("add_vendor_form", clear_on_submit=True):
            v_name = st.text_input("Vendor Name")
            v_type = st.text_input("Type (Caterer, DJ, etc.)")
            v_contact = st.text_input("Contact Info")
            v_cost = st.number_input(
                "Cost", min_value=0.0, step=50.0, format="%.2f"
            )
            vendor_submit = st.form_submit_button("Add Vendor")

        if vendor_submit:
            if not v_name:
                st.error("Vendor name is required.")
            else:
                try:
                    supabase.table("vendors").insert(
                        {
                            "name": v_name,
                            "type": v_type or None,
                            "contactinfo": v_contact or None,
                            "cost": v_cost,
                            "eventid": selected_event_id,
                        }
                    ).execute()
                    st.success("Vendor added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add vendor: {e}")

        for v in vendors:
            if st.button(
                f"Delete {v['name']}", key=f"delete_vendor_{v['vendorid']}"
            ):
                try:
                    supabase.table("vendors").delete().eq(
                        "vendorid", v["vendorid"]
                    ).execute()
                    st.warning("Vendor deleted.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Delete failed: {ex}")

# ---------- TASKS TAB ----------

with tab_tasks:
    st.subheader("Tasks")

    events = load_events(app_user_id)
    selected_event_id = event_selectbox(events, key="task_event_select")

    if selected_event_id:
        tasks_res = (
            supabase.table("tasks")
            .select("*")
            .eq("eventid", selected_event_id)
            .execute()
        )
        tasks = tasks_res.data or []

        if tasks:
            st.dataframe(
                [
                    {
                        "Title": t["title"],
                        "Due Date": t["duedate"],
                        "Assigned To": t["assignedto"],
                        "Status": t["status"],
                    }
                    for t in tasks
                ]
            )
        else:
            st.info("No tasks yet.")

        st.write("#### Add Task")
        with st.form("add_task_form", clear_on_submit=True):
            t_title = st.text_input("Task Title")
            t_desc = st.text_area("Description")
            t_due = st.date_input("Due Date", value=date.today())
            t_assigned = st.text_input("Assigned To")
            t_status = st.selectbox(
                "Status", ["Not Started", "In Progress", "Completed"], index=0
            )
            task_submit = st.form_submit_button("Add Task")

        if task_submit:
            if not t_title or not t_assigned:
                st.error("Title and Assigned To are required.")
            else:
                try:
                    supabase.table("tasks").insert(
                        {
                            "title": t_title,
                            "description": t_desc or None,
                            "duedate": t_due.isoformat(),
                            "assignedto": t_assigned,
                            "status": t_status,
                            "eventid": selected_event_id,
                           
                        }
                    ).execute()
                    st.success("Task added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add task: {e}")

        st.write("#### Update Task Status")
        for t in tasks:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(t["title"])
            with col2:
                new_status = st.selectbox(
                    "Status",
                    ["Not Started", "In Progress", "Completed"],
                    index=["Not Started", "In Progress", "Completed"].index(
                        t["status"]
                    ),
                    key=f"task_status_{t['taskid']}",
                )
            with col3:
                if st.button("Save", key=f"update_task_{t['taskid']}"):
                    try:
                        supabase.table("tasks").update(
                            {"status": new_status}
                        ).eq("taskid", t["taskid"]).execute()
                        st.success("Task updated.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Update failed: {ex}")

# ---------- DASHBOARD TAB ----------

with tab_dashboard:
    st.subheader("Dashboard & Analytics")

    events = load_events(app_user_id)
    selected_event_id = event_selectbox(events, key="dashboard_event_select")

    if selected_event_id:
        # Load related data
        guests = (
            supabase.table("guests")
            .select("*")
            .eq("eventid", selected_event_id)
            .execute()
            .data
            or []
        )
        vendors = (
            supabase.table("vendors")
            .select("*")
            .eq("eventid", selected_event_id)
            .execute()
            .data
            or []
        )
        tasks = (
            supabase.table("tasks")
            .select("*")
            .eq("eventid", selected_event_id)
            .execute()
            .data
            or []
        )

        # RSVP stats
        total_guests = len(guests)
        accepted = sum(1 for g in guests if g["rsvpstatus"] == "Accepted")
        pending = sum(1 for g in guests if g["rsvpstatus"] == "Pending")
        declined = sum(1 for g in guests if g["rsvpstatus"] == "Declined")

        # Budget stats
        event_row = [e for e in events if e["eventid"] == selected_event_id][0]
        total_budget = float(event_row.get("budget") or 0)
        vendor_spend = sum(float(v["cost"] or 0) for v in vendors)
        remaining = total_budget - vendor_spend

        # Task stats
        completed_tasks = sum(1 for t in tasks if t["status"] == "Completed")
        in_progress_tasks = sum(1 for t in tasks if t["status"] == "In Progress")
        not_started_tasks = sum(1 for t in tasks if t["status"] == "Not Started")

        # KPIs
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric("Total Guests", total_guests)
        with kpi2:
            st.metric("Budget", f"${total_budget:,.2f}")
        with kpi3:
            st.metric("Vendor Spend", f"${vendor_spend:,.2f}", f"{remaining:,.2f} remaining")

        st.write("### RSVP Breakdown")
        rsvp_fig = px.bar(
            x=["Accepted", "Pending", "Declined"],
            y=[accepted, pending, declined],
            labels={"x": "RSVP Status", "y": "Count"},
        )
        st.plotly_chart(rsvp_fig, width="stretch")

        st.write("### Task Status")
        task_fig = px.bar(
            x=["Completed", "In Progress", "Not Started"],
            y=[completed_tasks, in_progress_tasks, not_started_tasks],
            labels={"x": "Task Status", "y": "Count"},
        )
        st.plotly_chart(task_fig, use_container_width=True)

