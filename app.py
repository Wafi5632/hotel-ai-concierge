"""Streamlit front end for the Al Waha Grand Hotel concierge."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from hotel_app.agent import HotelAgent
from hotel_app.data import HotelDataStore
from hotel_app.memory import MemoryStore
from hotel_app.tools import HotelToolset

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "hotel_data.json"

st.set_page_config(
    page_title="Al Waha Grand · Concierge",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
    :root { --ink:#13251f; --muted:#64736d; --gold:#c99b4b; --cream:#fbf8f2; --mint:#e8f1ec; }
    .stApp { background:linear-gradient(135deg,#fbf8f2 0%,#f4f8f5 55%,#edf4f0 100%); color:var(--ink); }
    h1,h2,h3 { font-family:'Playfair Display',serif !important; color:var(--ink) !important; }
    p, label, .stMarkdown, .stButton, input, textarea { font-family:'DM Sans',sans-serif !important; }
    .hero { padding:2.4rem 2.6rem; border-radius:24px; color:white; background:linear-gradient(115deg,#132f28,#245b4c 64%,#98743b); box-shadow:0 18px 45px #1b40321f; margin-bottom:1.4rem; }
    .hero h1 { color:white !important; font-size:3rem; margin:0; }
    .hero p { color:#e7f0e9; font-size:1.1rem; margin:.5rem 0 0; }
    .eyebrow { color:#e5bd72; letter-spacing:.15em; text-transform:uppercase; font-weight:700; font-size:.75rem; }
    .metric-card { background:#ffffffc9; border:1px solid #e2eae5; border-radius:16px; padding:1rem 1.1rem; height:100%; }
    .metric-card strong { display:block; font-size:1.25rem; color:var(--ink); }
    .metric-card span { color:var(--muted); font-size:.82rem; }
    [data-testid="stChatMessage"] { background:#ffffffb8; border:1px solid #e4ebe6; border-radius:16px; padding:.3rem .8rem; }
    .stButton > button[kind="primary"] { background:#245b4c; border:0; }
    .stTabs [data-baseweb="tab-list"] { gap:1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_store() -> HotelDataStore:
    return HotelDataStore(DATA_PATH)


@st.cache_resource
def get_agent() -> HotelAgent:
    store = get_store()
    memory = MemoryStore(ROOT / "data" / "memory.json")
    return HotelAgent(store, memory=memory)


def money(value: float, currency: str = "AED") -> str:
    return f"{currency} {value:,.0f}"


store = get_store()
tools = HotelToolset(store)
agent = get_agent()
if "session_id" not in st.session_state:
    st.session_state.session_id = MemoryStore.new_session_id()
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "Welcome to Al Waha Grand. I can help with rooms, policies, amenities, and thoughtful extras for your stay. What can I arrange?",
        }
    ]
if "booking_result" not in st.session_state:
    st.session_state.booking_result = None
if "support_result" not in st.session_state:
    st.session_state.support_result = None
if "last_agent_result" not in st.session_state:
    st.session_state.last_agent_result = None

hotel = store.hotel
st.markdown(
    f"""
    <section class="hero">
      <div class="eyebrow">Dubai · UAE &nbsp; | &nbsp; Your stay, thoughtfully arranged</div>
      <h1>{hotel['name']}</h1>
      <p>A calm, capable concierge for reservations and guest care.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Your concierge")
    st.caption("Live inventory and policies are read from `hotel_data.json`.")
    st.divider()
    st.markdown("**At a glance**")
    st.markdown(f"🕒 Check-in **{hotel['check_in_time']}** · Check-out **{hotel['check_out_time']}**")
    st.markdown(f"📞 {hotel['contact']['phone']}")
    st.markdown(f"✉️ {hotel['contact']['email']}")
    st.divider()
    st.markdown("**Signature amenities**")
    st.caption(" · ".join(hotel["amenities"]))
    st.divider()
    st.caption("Need a person? Call reservations and quote your booking or case number.")

overview = st.columns(4)
overview[0].markdown('<div class="metric-card"><strong>15:00</strong><span>Check-in</span></div>', unsafe_allow_html=True)
overview[1].markdown('<div class="metric-card"><strong>12:00</strong><span>Check-out</span></div>', unsafe_allow_html=True)
overview[2].markdown('<div class="metric-card"><strong>24/7</strong><span>Guest support</span></div>', unsafe_allow_html=True)
overview[3].markdown('<div class="metric-card"><strong>AED</strong><span>Local currency</span></div>', unsafe_allow_html=True)

chat_tab, booking_tab, help_tab = st.tabs(["✦ Concierge chat", "▣ Book your stay", "♡ Help & feedback"])

with chat_tab:
    st.markdown("### How may we make your stay exceptional?")
    st.caption("Ask about availability using dates like 2026-09-15 to 2026-09-18, or ask about any hotel policy.")
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    last_result = st.session_state.last_agent_result or {}
    availability_result = last_result.get("tool_results", {}).get("availability", {})
    if availability_result.get("success") and availability_result.get("data", {}).get("rooms"):
        st.markdown("#### Rooms found for your dates")
        room_columns = st.columns(min(3, len(availability_result["data"]["rooms"])))
        for column, room in zip(room_columns, availability_result["data"]["rooms"]):
            with column:
                st.markdown(
                    f"""<div class="metric-card">
                    <strong>{room['name']}</strong>
                    <span>{room['bed_type']} · {room['size_sqm']} m²</span>
                    <p>{money(room['rate_per_night'], room['currency'])}/night<br>
                    <b>{room['available_rooms']} left</b> · up to {room['max_occupancy']} guests</p>
                    </div>""",
                    unsafe_allow_html=True,
                )
    booking_action = last_result.get("tool_results", {}).get("booking", {})
    if booking_action.get("success"):
        booking_data = booking_action["data"]
        st.success(
            f"Reservation confirmed · {booking_data['booking_id']} · "
            f"{money(booking_data['total_amount'], booking_data['currency'])}"
        )
    prompt = st.chat_input("Ask about rooms, policies, amenities, or packages…", key="chat_input")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        agent.memory.save_turn(st.session_state.session_id, "user", prompt) if agent.memory else None
        with st.spinner("Checking hotel information and preparing your options…"):
            result = agent.invoke(prompt, st.session_state.chat_messages[-10:])
        st.session_state.last_agent_result = result
        response = result.get("response", "I’m sorry, I could not complete that request.")
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
        agent.memory.save_turn(st.session_state.session_id, "assistant", response) if agent.memory else None
        st.rerun()

with booking_tab:
    st.markdown("### Reserve a room")
    st.caption("Your booking is confirmed only after the form is submitted and live availability is checked.")
    room_labels = {room["id"]: f"{room['name']} · from {money(room['base_rate_per_night'])}/night" for room in store.room_types}
    package_labels = {package["id"]: f"{package['name']} · {money(package.get('price_per_night', package.get('price', 0)))}" for package in store.packages}
    with st.form("booking_form", clear_on_submit=False):
        left, right = st.columns(2)
        with left:
            guest_name = st.text_input("Full name", placeholder="Amina Hassan")
            email = st.text_input("Email", placeholder="you@example.com")
            phone = st.text_input("Phone", placeholder="+971 50 000 0000")
            guests = st.number_input("Guests", min_value=1, max_value=12, value=2, step=1)
        with right:
            check_in = st.date_input("Check-in", value=date(2026, 9, 15), key="booking_checkin")
            check_out = st.date_input("Check-out", value=date(2026, 9, 18), key="booking_checkout")
            room_type = st.selectbox("Room", list(room_labels), format_func=lambda key: room_labels[key])
            selected_package_ids = st.multiselect("Add a little more", list(package_labels), format_func=lambda key: package_labels[key])
        submitted = st.form_submit_button("Confirm reservation", type="primary", use_container_width=True)
    if submitted:
        with st.spinner("Checking live availability and confirming your reservation…"):
            result = tools.create_booking(
            guest_name, email, phone, room_type, check_in.isoformat(), check_out.isoformat(), int(guests), selected_package_ids
        )
        st.session_state.booking_result = result
        if result["success"]:
            st.success(f"Reservation confirmed · {result['data']['booking_id']}")
        else:
            st.error(result["error"])
    booking = st.session_state.booking_result
    if booking and booking.get("success"):
        data = booking["data"]
        st.markdown(
            f"""<div class="metric-card">
            <span>CONFIRMED RESERVATION</span>
            <strong>{data['booking_id']}</strong>
            <p><b>{data['guest_name']}</b> · {store.room(data['room_type'])['name']}<br>
            {data['check_in']} → {data['check_out']} · {data['guests']} guest(s)<br>
            <b>{money(data['total_amount'], data['currency'])}</b> total</p>
            </div>""",
            unsafe_allow_html=True,
        )

with help_tab:
    st.markdown("### We’re here to help")
    st.caption("Share a concern and a guest-care specialist will receive a trackable case.")
    with st.form("support_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            support_name = st.text_input("Your name", key="support_name")
            support_email = st.text_input("Email", key="support_email")
            category = st.selectbox("Topic", ["Room & housekeeping", "Billing", "Restaurant", "Facilities", "Other"])
        with col2:
            message = st.text_area("How can we improve this?", height=140)
        support_submitted = st.form_submit_button("Open support case", type="primary")
    if support_submitted:
        with st.spinner("Opening a tracked guest-care case…"):
            result = tools.log_complaint(support_name, support_email, category, message)
        st.session_state.support_result = result
        if result["success"]:
            st.success(f"Thank you — case **{result['data']['case_id']}** is open. We’ll follow up at {result['data']['email']}.")
        else:
            st.error(result["error"])
