"""
web_app.py
FastAPI + WebSocket server for Ticket to Ride web app.

Start:  uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload
"""
import uuid
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from game_session import GameSession

app = FastAPI(title="Ticket to Ride AI")

# In-memory session store  {session_id: GameSession}
sessions: dict[str, GameSession] = {}

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    """Lightweight endpoint for uptime pingers (keeps free host awake)."""
    return {"status": "ok", "sessions": len(sessions)}


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    # Resume or create session
    if session_id not in sessions:
        sessions[session_id] = GameSession()

    gs = sessions[session_id]

    async def send_state():
        await websocket.send_json({"type": "state", "data": gs.serialize()})

    # Send current state immediately so the client can render
    await send_state()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "msg": "bad JSON"})
                continue

            mtype = msg.get("type")
            try:
                if mtype == "start_game":
                    n_human = int(msg.get("n_human", 1))
                    n_ai    = int(msg.get("n_ai",    1))
                    strats  = msg.get("ai_strategies", [2] * n_ai)
                    gs.start_game(n_human, n_ai, strats)

                elif mtype == "confirm_init_tix":
                    gs.confirm_init_tix(msg.get("indices", []))

                elif mtype == "start_turn":
                    gs.start_turn()

                elif mtype == "advance_ai_turn":
                    gs.advance_ai_turn()

                elif mtype == "action":
                    act = msg.get("action")
                    if act == "draw_cards":
                        gs.action_draw_cards()
                    elif act == "claim_route":
                        gs.action_claim_route()
                    elif act == "draw_tickets":
                        gs.action_draw_tickets()

                elif mtype == "pick_card":
                    gs.pick_card(
                        msg.get("source", "face_down"),
                        msg.get("card"),
                    )

                elif mtype == "click_route":
                    gs.click_route(msg.get("c1", ""), msg.get("c2", ""))

                elif mtype == "select_color":
                    gs.select_color(msg.get("color", ""))

                elif mtype == "confirm_claim":
                    gs.confirm_claim()

                elif mtype == "confirm_tix":
                    gs.confirm_tix(msg.get("indices", []))

                elif mtype == "cancel":
                    gs.cancel()

                elif mtype == "new_session":
                    sessions[session_id] = GameSession()
                    gs = sessions[session_id]

                else:
                    await websocket.send_json(
                        {"type": "error", "msg": f"unknown type: {mtype}"}
                    )
                    continue

                await send_state()

            except Exception as exc:
                await websocket.send_json(
                    {"type": "error", "msg": str(exc)}
                )

    except WebSocketDisconnect:
        pass  # Client disconnected — keep session in memory for resume
