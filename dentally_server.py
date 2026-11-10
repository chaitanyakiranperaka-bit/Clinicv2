import json
import re
import time
import asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse

from dentally_config import (
    DUBLIN_TZ,
    DENTALLY_SERVER_PORT,
    BEDROCK_MODEL_ID,
    build_dentally_system_prompt,
    DENTALLY_BEDROCK_TOOLS,
    KNOWN_PATIENTS
)
from dentally_client import dentally_client
import dentally_service

app = FastAPI(
    title="Dentally NexGen API Read Test Server",
    description="Standalone test server for verifying Dentally NexGen API read integration in production environment."
)

@app.get("/", response_class=HTMLResponse)
async def test_dashboard():
    """Lightweight web dashboard for testing Dentally read endpoints."""
    site = dentally_service.get_clinic_site_summary() or {}
    site_name = site.get("name", "Star Dental Care")
    address = site.get("address", "N/A")
    phone = site.get("phone", "N/A")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Dentally Test Server - {site_name}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #0f172a; color: #f8fafc; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #334155; }}
        h1 {{ color: #38bdf8; margin-top: 0; }}
        h2 {{ color: #94a3b8; font-size: 1.1rem; border-bottom: 1px solid #334155; padding-bottom: 8px; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; background: #065f46; color: #34d399; }}
        button {{ background: #0284c7; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 500; }}
        button:hover {{ background: #0369a1; }}
        pre {{ background: #0b1120; padding: 12px; border-radius: 8px; overflow-x: auto; color: #a5f3fc; font-size: 0.85rem; }}
        .row {{ display: flex; gap: 12px; margin-bottom: 12px; }}
        input, select {{ background: #0b1120; border: 1px solid #334155; color: white; padding: 8px 12px; border-radius: 6px; }}
    </style>
</head>
<body>
    <h1>🦷 Dentally NexGen Test Environment (Read-Only)</h1>
    <div class="card">
        <span class="badge">● Live Dentally Connected</span>
        <p><strong>Practice:</strong> {site_name} | <strong>Phone:</strong> {phone}</p>
        <p><strong>Address:</strong> {address}</p>
        <p><em>Strictly Read-Only Mode: Live PMS schedules and appointments are read directly from Dentally. No writes or bookings are executed.</em></p>
    </div>

    <div class="card">
        <h2>Live Availability Check</h2>
        <div class="row">
            <select id="clinician">
                <option value="Dentist Shailaja">Dentist Shailaja (Shailja Sharma)</option>
                <option value="Reihaneh Afrasaiabi">Dr. Reihaneh Afrasaiabi</option>
                <option value="Aubrey Agang">Dr. Aubrey Agang</option>
                <option value="Salma Naz">Dr. Salma Naz</option>
            </select>
            <input type="date" id="checkDate" value="2026-11-11">
            <input type="text" id="checkTime" placeholder="e.g. 10:00 or morning" value="10:00">
            <button onclick="checkSlots()">Check Slots</button>
        </div>
        <pre id="availOutput">// Results will appear here</pre>
    </div>

    <div class="card">
        <h2>Recent Live Appointments</h2>
        <button onclick="loadAppointments()">Fetch Recent Appointments</button>
        <pre id="apptsOutput">// Click to load live appointments</pre>
    </div>

    <script>
        async function checkSlots() {{
            const c = document.getElementById('clinician').value;
            const d = document.getElementById('checkDate').value;
            const t = document.getElementById('checkTime').value;
            document.getElementById('availOutput').innerText = 'Loading live availability from Dentally...';
            try {{
                const res = await fetch(`/api/dentally/availability?clinician=${{encodeURIComponent(c)}}&date=${{d}}&time=${{encodeURIComponent(t)}}`);
                const json = await res.json();
                document.getElementById('availOutput').innerText = JSON.stringify(json, null, 2);
            }} catch(e) {{
                document.getElementById('availOutput').innerText = 'Error: ' + e;
            }}
        }}

        async function loadAppointments() {{
            document.getElementById('apptsOutput').innerText = 'Loading appointments from Dentally...';
            try {{
                const res = await fetch('/api/dentally/appointments?limit=10');
                const json = await res.json();
                document.getElementById('apptsOutput').innerText = JSON.stringify(json, null, 2);
            }} catch(e) {{
                document.getElementById('apptsOutput').innerText = 'Error: ' + e;
            }}
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/status")
async def get_status():
    """Returns status badge and configuration info."""
    configured = dentally_client.is_configured()
    site = dentally_service.get_clinic_site_summary() if configured else None
    return {
        "dentally_badge": "🟢 Live Dentally PMS (Star Dental Care)" if (configured and site) else "🔴 Disconnected",
        "practice_name": site.get("name") if site else None,
        "practice_id": dentally_client.practice_id,
        "mode": "STRICTLY_READ_ONLY",
        "model_id": BEDROCK_MODEL_ID
    }

@app.get("/api/dentally/site")
async def get_site_details():
    """GET /api/dentally/site: Returns practice details from Dentally."""
    summary = dentally_service.get_clinic_site_summary()
    if not summary:
        return JSONResponse({"status": "error", "message": "Could not fetch practice site"}, status_code=500)
    return summary

@app.get("/api/dentally/availability")
async def get_availability(
    clinician: str = Query("Dentist Shailaja"),
    date: str = Query("2026-11-11"),
    time: str = Query("any")
):
    """GET /api/dentally/availability: Queries live practitioner availability."""
    res = dentally_service.check_dentally_slots(clinician, date, time)
    return res

@app.get("/api/dentally/appointments")
async def get_recent_appointments(limit: int = 10):
    """GET /api/dentally/appointments: Returns recent appointments."""
    appts = dentally_service.list_upcoming_appointments(limit=limit)
    return {"count": len(appts), "data": appts}

@app.websocket("/ws/call")
async def dentally_call_websocket(websocket: WebSocket):
    """WebSocket softphone handler for Dentally read test calls."""
    await websocket.accept()
    caller_phone = websocket.query_params.get("caller_id", "+353871234567")
    prompt = build_dentally_system_prompt(caller_phone)
    print(f"\n[DENTALLY WS CONNECTED] Inbound test call from: {caller_phone}", flush=True)

    matched = KNOWN_PATIENTS.get(caller_phone)
    greeting = (
        f"Hello, welcome to Star Dental Care in Clonsilla. You are speaking with Deirdre. Am I speaking with {matched['name']}?"
        if matched else
        "Hello, welcome to Star Dental Care in Clonsilla. You are speaking with Deirdre. How can I help you today?"
    )

    await websocket.send_text(json.dumps({"type": "transcript", "role": "Deirdre", "text": greeting}))

    try:
        while True:
            packet = await websocket.receive()
            if "text" in packet:
                data = json.loads(packet["text"])
                if data.get("action") == "hangup":
                    break
                elif data.get("action") == "check_availability":
                    c = data.get("clinician", "Dentist Shailaja")
                    d = data.get("date", "2026-11-11")
                    t = data.get("time", "any")
                    res = dentally_service.check_dentally_slots(c, d, t)
                    await websocket.send_text(json.dumps({"type": "availability_result", "data": res}))
    except WebSocketDisconnect:
        print("[DENTALLY WS DISCONNECTED]", flush=True)
    except Exception as e:
        print(f"[DENTALLY WS ERROR]: {e}", flush=True)

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Dentally Read Test Server on port {DENTALLY_SERVER_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=DENTALLY_SERVER_PORT)
