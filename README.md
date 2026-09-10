# Al Waha Grand Hotel Concierge

A polished Streamlit hotel sales and customer-service app powered by a small
LangGraph workflow. It uses `hotel_data.json` as the source of truth for the
hotel catalogue, policies, live inventory, packages, and bookings.

## Features

- **LangGraph agent:** understand → retrieve verified hotel data → respond.
- **Deterministic by default:** no API key is required. Responses never invent
  inventory or policy details.
- **Optional LLM polish:** if `OPENAI_API_KEY` is set and `langchain-openai`
  is installed, the model can rewrite verified deterministic responses. The
  app still falls back safely if the provider is unavailable.
- **Booking flow:** validates dates, occupancy, contact details, room capacity,
  inventory, package pricing, and overlapping bookings before persisting a
  confirmation in the existing `bookings` array.
- **Customer care:** searchable FAQs, contextual add-on recommendations, and
  complaint cases stored separately in `data/complaints.json`.
- **Persistent session memory:** recent conversations and preferences are kept
  in `data/memory.json`; these auxiliary files do not alter the hotel schema.
- **Typed tools:** `check_availability`, `create_booking`,
  `recommend_package`, `log_complaint`, and `get_hotel_info` each have a
  Pydantic input schema and return structured success/error data.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL shown by Streamlit. The supplied availability includes
sample inventory from 2026-09-15 through 2026-09-19, so those dates are useful
for a first booking test.

If PowerShell says `streamlit` is not recognized, use `python -m streamlit run
app.py` instead. This launches Streamlit through the active Python interpreter
and does not depend on the Python `Scripts` directory being on your PATH. You
can also double-click `run_app.bat` or run `.\run_app.ps1` from PowerShell.

### Windows setup troubleshooting

If `python` is not recognized, install Python 3.11+ from
https://www.python.org/downloads/windows/ and select **Add python.exe to PATH**
during installation. Then open a new PowerShell window and run the setup
commands above. If PowerShell blocks the script activation command, use
`python -m pip install -r requirements.txt` followed by
`python -m streamlit run app.py` without activating the environment.

## Where the agent is used

The agent is the `HotelAgent` class in `hotel_app/agent.py`. Streamlit calls
`agent.invoke(...)` from the chat interface in `app.py`. The same class can be
used by a future hotel website, WhatsApp integration, call-center service, or
REST API; those channels only need to pass a guest message and conversation
history to the agent.

## Turning this into a sellable hotel product

The current project is a strong demo/MVP. A production product should be
packaged as a multi-tenant hotel concierge platform:

1. Replace JSON persistence with PostgreSQL and keep each hotel's catalogue,
   policies, inventory, packages, and bookings isolated by `hotel_id`.
2. Add authentication and roles for hotel managers, reservations agents, and
   administrators.
3. Build a REST API around the agent, then connect the Streamlit interface as
   an internal demo/admin console. Add web chat, WhatsApp, and email adapters.
4. Connect to a hotel's PMS/channel manager for real inventory and bookings.
   Never promise live availability from a local JSON file in production.
5. Add an LLM provider behind a controlled service layer, with tool-only
   access, prompt/version tracking, usage limits, and a deterministic fallback.
6. Add audit logs, consent, encryption, PII retention rules, rate limiting,
   monitoring, backups, and human escalation for refunds, disputes, and
   exceptional requests.
7. Create a hotel onboarding flow so staff can configure branding, rooms,
   rates, amenities, policies, packages, escalation contacts, and tone without
   changing code.
8. Sell it as a recurring service: setup/integration fee plus a monthly
   platform fee and usage-based messaging or AI charges. Start with one narrow
   promise such as "convert more direct bookings and answer guest questions
   24/7", then measure booking conversion, response time, and escalation rate.

For a first pilot, deploy the app behind authentication on a managed host,
use one hotel's real data through a sandbox PMS integration, provide a human
handoff button, and agree on success metrics before expanding the scope.

## Deploying it live

The simplest demo deployment is Streamlit Community Cloud:

1. Push this repository to GitHub.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Choose `Wafi5632/hotel-ai-concierge`.
4. Set the main file to `app.py`.
5. Deploy.

This gives the app a hosted `streamlit.app` URL. For a branded custom URL such
as `concierge.yourhotel.com`, use a paid host that supports custom domains
(Render, Railway, Fly.io, Azure, or AWS) and point the domain's DNS record to
that host. Streamlit Community Cloud is excellent for demos, but custom-domain
support and production controls depend on the hosting plan. Add secrets such as
`OPENAI_API_KEY` in the host's secrets manager rather than committing them to
GitHub.

## Data and safety notes

Do not rename or add keys to `hotel_data.json`: `HotelDataStore` validates the
exact top-level schema on load. Confirmed bookings are appended to its existing
`bookings` list; support cases and conversation memory live in `data/`.
For production, replace JSON persistence with a transactional database and
add authentication/PII retention controls.
