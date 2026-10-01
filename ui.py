import streamlit as st
import httpx
import time
import json

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Travel Planner", page_icon="✈️", layout="wide")

# --- session state defaults ---
for key, default in [
    ("plan_id", None),
    ("stage", "input"),
    ("draft_plan", None),
    ("final_plan", None),
    ("request_data", None),
    ("research_data", None),
    ("error", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def reset():
    for key in ["plan_id", "draft_plan", "final_plan", "request_data", "research_data", "error"]:
        st.session_state[key] = None
    st.session_state["stage"] = "input"


def render_activity(label, emoji, activity_data):
    st.markdown(f"#### {emoji} {label}")
    if isinstance(activity_data, dict):
        st.markdown(f"**{activity_data.get('activity', '')}**")
        time_str = activity_data.get("time", "")
        duration = activity_data.get("duration", "")
        cost = activity_data.get("cost", "Free")
        travel = activity_data.get("travel_from_previous", "")

        details = []
        if time_str:
            details.append(f"🕐 {time_str}")
        if duration:
            details.append(f"⏱ {duration}")
        st.caption(" | ".join(details) if details else "")

        if cost and str(cost) != "0":
            st.caption(f"💰 {cost}")
        else:
            st.caption("💰 Free")

        if travel:
            st.caption(f"🚶 {travel}")
    elif activity_data:
        st.write(activity_data)


def render_meals(meals):
    if not meals or not isinstance(meals, dict):
        return
    st.markdown("**🍽️ Meals**")
    for meal_name in ["breakfast", "lunch", "dinner"]:
        val = meals.get(meal_name, "")
        if isinstance(val, dict):
            suggestion = val.get("suggestion", "")
            cost = val.get("cost", "")
            if cost and str(cost) != "0":
                st.write(f"• **{meal_name.title()}:** {suggestion} ({cost})")
            else:
                st.write(f"• **{meal_name.title()}:** {suggestion}")
        elif val:
            st.write(f"• **{meal_name.title()}:** {val}")


def render_plan(plan, expanded=True):
    if not plan:
        st.warning("Plan data is not available.")
        return

    # trip title
    st.markdown(f"## {plan.get('trip_title', 'Your Trip')}")

    # trip overview cards
    currency = plan.get("currency", "USD")
    dates = plan.get("dates", {})
    start_date = dates.get("start", "")
    end_date = dates.get("end", "")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**📍 Destination:** {plan.get('destination', '')}")
        st.markdown(f"**📅 Dates:** {start_date} to {end_date}")
    with col2:
        st.markdown(f"**💰 Total Budget:** {plan.get('total_budget', 'N/A')}")
        st.markdown(f"**💱 Currency:** {currency}")

    st.divider()

    # daily itinerary
    st.markdown("### Day-by-Day Itinerary")
    for day in plan.get("daily_itinerary", []):
        area = day.get("area", "")
        area_label = f" — 📍 {area}" if area else ""
        header = f"📅 Day {day.get('day', '?')} — {day.get('theme', '')} ({day.get('date', '')}){area_label}"

        with st.expander(header, expanded=expanded):
            c1, c2, c3 = st.columns(3)
            with c1:
                render_activity("Morning", "🌅", day.get("morning", {}))
            with c2:
                render_activity("Afternoon", "☀️", day.get("afternoon", {}))
            with c3:
                render_activity("Evening", "🌙", day.get("evening", {}))

            render_meals(day.get("meals", {}))

            if day.get("transport_notes"):
                st.caption(f"🚇 {day['transport_notes']}")

            daily_total = day.get("daily_total", "N/A")
            st.markdown(f"**💰 Daily Total: {daily_total}**")

    # accommodation & tips
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        acc = plan.get("accommodation", {})
        if acc and isinstance(acc, dict):
            st.markdown("### 🏨 Accommodation")
            st.markdown(f"**Type:** {acc.get('type', 'N/A')}")
            st.markdown(f"**Area:** {acc.get('area', 'N/A')}")
            st.markdown(f"**Nightly Rate:** {acc.get('nightly_rate', 'N/A')}")

    with col2:
        tips = plan.get("packing_tips", [])
        if tips:
            st.markdown("### 🎒 Packing Tips")
            for tip in tips:
                st.caption(f"• {tip}")

    notes = plan.get("important_notes", [])
    if notes:
        st.markdown("### 📌 Important Notes")
        for note in notes:
            st.caption(f"• {note}")


# HEADER

st.title("✈️ AI Travel Planner")
st.caption("Multi-agent travel planning with human-in-the-loop approval")

# STAGE 1 — Trip Input Form

if st.session_state["stage"] == "input":
    st.header("Plan Your Trip")

    with st.form("travel_form"):
        col1, col2 = st.columns(2)

        with col1:
            destination = st.text_input("Destination", placeholder="e.g. Tokyo, Paris, Bali")
            start_date = st.date_input("Start Date")
            budget_min = st.number_input("Minimum Budget (USD)", min_value=100, value=1000, step=100)
            num_travelers = st.number_input("Number of Travelers", min_value=1, value=2, step=1)

        with col2:
            interests_input = st.text_input("Interests (comma-separated)", placeholder="e.g. food, culture, temples, hiking")
            end_date = st.date_input("End Date")
            budget_max = st.number_input("Maximum Budget (USD)", min_value=100, value=2000, step=100)

        submitted = st.form_submit_button("🚀 Generate Travel Plan", use_container_width=True)

    if submitted:
        if not destination:
            st.error("Please enter a destination.")
        elif end_date <= start_date:
            st.error("End date must be after start date.")
        elif budget_max < budget_min:
            st.error("Maximum budget must be greater than minimum budget.")
        else:
            interests = [i.strip() for i in interests_input.split(",") if i.strip()] if interests_input else []
            payload = {
                "destination": destination,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "budget_min": budget_min,
                "budget_max": budget_max,
                "interests": interests,
                "num_travelers": num_travelers,
            }
            try:
                resp = httpx.post(f"{API_URL}/plan", json=payload, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                st.session_state["plan_id"] = data["plan_id"]
                st.session_state["request_data"] = payload
                st.session_state["stage"] = "loading"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to create plan: {e}")


# STAGE 2 — Loading / Polling

elif st.session_state["stage"] == "loading":
    st.header("Generating Your Travel Plan...")

    plan_id = st.session_state["plan_id"]
    req = st.session_state["request_data"]

    col1, col2 = st.columns([2, 1])
    with col1:
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
    with col2:
        st.subheader("Trip Details")
        st.write(f"**Destination:** {req['destination']}")
        st.write(f"**Dates:** {req['start_date']} to {req['end_date']}")
        st.write(f"**Budget:** ${req['budget_min']} - ${req['budget_max']} USD")
        st.write(f"**Travelers:** {req['num_travelers']}")
        if req.get("interests"):
            st.write(f"**Interests:** {', '.join(req['interests'])}")

    status_messages = {
        "researching": ("🔍 Researching your destination...", 30),
        "planning": ("📝 Building your itinerary...", 65),
        "awaiting_review": ("✅ Draft plan ready!", 100),
        "revising": ("🔄 Revising based on your feedback...", 50),
        "failed": ("❌ Something went wrong.", 0),
    }

    max_polls = 60
    for i in range(max_polls):
        try:
            resp = httpx.get(f"{API_URL}/plan/{plan_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]
            msg, progress = status_messages.get(status, (f"Status: {status}", 50))
            status_placeholder.info(msg)
            progress_bar.progress(min(progress, 100))

            if status == "awaiting_review":
                st.session_state["draft_plan"] = data.get("draft_plan")
                st.session_state["research_data"] = data.get("research_data")
                st.session_state["stage"] = "review"
                st.rerun()

            if status == "failed":
                st.session_state["error"] = data.get("message", "Unknown error")
                st.session_state["stage"] = "input"
                st.rerun()

            if status == "approved":
                st.session_state["stage"] = "final"
                st.rerun()

        except Exception as e:
            status_placeholder.warning(f"Polling... ({e})")

        time.sleep(3)

    st.error("Timed out waiting for the plan. Please try again.")
    if st.button("Start Over"):
        reset()
        st.rerun()


# STAGE 3 — Review (HITL)

elif st.session_state["stage"] == "review":
    st.header("📋 Review Your Travel Plan")
    st.info("Review the draft itinerary below. You can approve it, request changes, or reject it entirely.")

    plan = st.session_state["draft_plan"]
    plan_id = st.session_state["plan_id"]

    render_plan(plan, expanded=True)

    # --- HITL action buttons ---
    st.divider()
    st.subheader("Your Decision")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve Plan", use_container_width=True, type="primary"):
            try:
                resp = httpx.post(
                    f"{API_URL}/plan/{plan_id}/review",
                    json={"action": "approve"},
                    timeout=15,
                )
                resp.raise_for_status()
                st.session_state["stage"] = "loading_final"
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with col2:
        if st.button("✏️ Request Modifications", use_container_width=True):
            st.session_state["show_modify"] = True

    with col3:
        if st.button("❌ Reject & Re-research", use_container_width=True):
            st.session_state["show_reject"] = True

    if st.session_state.get("show_modify"):
        with st.form("modify_form"):
            st.write("Describe what you'd like changed:")
            feedback = st.text_area("Your modifications", placeholder="e.g. Swap day 2 afternoon with a cooking class, add more budget-friendly restaurants")
            modify_submitted = st.form_submit_button("Submit Modifications")
        if modify_submitted and feedback:
            try:
                resp = httpx.post(
                    f"{API_URL}/plan/{plan_id}/review",
                    json={"action": "modify", "feedback": feedback},
                    timeout=15,
                )
                resp.raise_for_status()
                st.session_state["show_modify"] = False
                st.session_state["stage"] = "loading"
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.get("show_reject"):
        with st.form("reject_form"):
            st.write("Tell us what was wrong:")
            feedback = st.text_area("Your feedback", placeholder="e.g. I want more focus on street food, less museums")
            reject_submitted = st.form_submit_button("Submit & Re-research")
        if reject_submitted and feedback:
            try:
                resp = httpx.post(
                    f"{API_URL}/plan/{plan_id}/review",
                    json={"action": "reject", "feedback": feedback},
                    timeout=15,
                )
                resp.raise_for_status()
                st.session_state["show_reject"] = False
                st.session_state["stage"] = "loading"
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


# STAGE 4 — Loading after approval

elif st.session_state["stage"] == "loading_final":
    st.header("Finalizing your plan...")
    plan_id = st.session_state["plan_id"]

    with st.spinner("Almost there..."):
        for _ in range(20):
            try:
                resp = httpx.get(f"{API_URL}/plan/{plan_id}", timeout=10)
                data = resp.json()
                if data["status"] == "approved":
                    final_resp = httpx.get(f"{API_URL}/plan/{plan_id}/final", timeout=10)
                    if final_resp.status_code == 200:
                        st.session_state["final_plan"] = final_resp.json()["final_plan"]
                        st.session_state["stage"] = "final"
                        st.rerun()
                elif data["status"] == "failed":
                    st.error(data.get("message", "Failed"))
                    break
            except Exception:
                pass
            time.sleep(2)

    st.error("Timed out. Please try again.")
    if st.button("Start Over"):
        reset()
        st.rerun()


# STAGE 5 — Final Plan

elif st.session_state["stage"] == "final":
    st.header("🎉 Your Finalized Travel Plan")
    st.success("Plan approved and ready to go!")

    plan = st.session_state.get("final_plan") or st.session_state.get("draft_plan", {})

    render_plan(plan, expanded=False)

    # download
    st.divider()
    if plan:
        st.download_button(
            "📥 Download Plan as JSON",
            data=json.dumps(plan, indent=2),
            file_name="travel_plan.json",
            mime="application/json",
        )

    if st.button("🔄 Plan Another Trip"):
        reset()
        st.rerun()

# --- sidebar ---
with st.sidebar:
    st.markdown("### How It Works")
    st.markdown(
        "1. **Submit** your trip details\n"
        "2. **AI researches** your destination\n"
        "3. **AI builds** a day-by-day plan\n"
        "4. **You review** and approve/modify\n"
        "5. **Get your final plan!**"
    )
    st.divider()
    if st.session_state["plan_id"]:
        st.caption(f"Plan ID: `{st.session_state['plan_id']}`")
    if st.session_state["stage"] != "input":
        if st.button("🏠 Start Over", use_container_width=True):
            reset()
            st.rerun()

    if st.session_state.get("error"):
        st.error(st.session_state["error"])
        st.session_state["error"] = None
