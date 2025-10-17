from __future__ import annotations
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.mcp_tasks_local import run_local, task_datetime
from services.storage import StorageService
from services.llm_providers import get_provider
from services.logger import setup_logger
import json

logger = setup_logger("mcp-server")

app = FastAPI(title="MCP Server")


class TaskRequest(BaseModel):
    agent: str
    task: str
    payload: Dict[str, Any]


@app.post("/task")
def task_endpoint(req: TaskRequest) -> Dict[str, Any]:
    logger.info(f"/task -> {json.dumps(req.model_dump())}")
    try:
        # First: local deterministic registry
        data = run_local(req.agent, req.task, req.payload)
        if data:
            logger.info(f"/task local <- {json.dumps(data)}")
            return data

        # Second: LLM provider path for robustness
        provider_name = os.getenv("LLM_PROVIDER", "local")
        provider = get_provider(provider_name)
        if req.agent == "intent" and req.task == "classify_intent":
            labels = req.payload.get("labels", [])
            text = req.payload.get("text", "")
            prompt = (
                "Classify the intent of the user as one of: "
                + ", ".join(labels)
                + ". Just answer with the label.\nUser: "
                + text
            )
            out = provider.generate(prompt) or ""
            guess = next((l for l in labels if l.lower() in out.lower()), None)
            data = {"intent": guess or (labels[0] if labels else "other")}
            logger.info(f"/task provider <- {json.dumps(data)}")
            return data
        if req.agent == "datetime" and req.task == "extract_datetime":
            text = req.payload.get("text", "")
            # Prefer deterministic local parser for reliability
            data = task_datetime({"text": text})
            logger.info(f"/task provider(datetime_local) <- {json.dumps(data)}")
            return data
        if req.agent == "mode" and req.task == "infer_mode":
            text = req.payload.get("text", "")
            out = (provider.generate(
                "Infer appointment mode as 'virtual' or 'telephonic'. Answer with one word.\nText: "
                + text
            ) or "").lower()
            mode = "virtual" if "tele" not in out and "phone" not in out else "telephonic"
            data = {"mode": mode}
            logger.info(f"/task provider <- {json.dumps(data)}")
            return data
        if req.agent == "confirmation" and req.task == "generate_confirmation":
            date = req.payload.get("date")
            day = req.payload.get("day")
            time = req.payload.get("time")
            mode = req.payload.get("mode")
            data = {"text": f"Your {mode} appointment is booked for {day}, {date} at {time}."}
            logger.info(f"/task provider <- {json.dumps(data)}")
            return data

        # Unknown task fallback
        logger.warning("/task unknown task, returning empty result")
        return {}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/task error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/appointments")
def list_appointments() -> Dict[str, Any]:
    s = StorageService()
    return {"items": s.list_appointments()}


class AppointmentIn(BaseModel):
    date: str
    day: str | None = None
    time: str
    mode: str
    notes: str | None = ""
    user_id: str


@app.post("/appointments")
def create_appointment(appt: AppointmentIn) -> Dict[str, Any]:
    s = StorageService()
    if s.has_time_slot_taken(appt.date, appt.time):
        raise HTTPException(status_code=409, detail="Time slot taken")
    saved = s.save_appointment(
        date=appt.date,
        day=appt.day,
        time=appt.time,
        mode=appt.mode,
        notes=appt.notes or "",
        user_id=appt.user_id,
    )
    return {"item": saved}
