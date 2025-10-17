from __future__ import annotations
from typing import Any, Callable, Dict, Optional
import os
import json
import httpx
import asyncio
from .llm_providers import get_provider
from .logger import setup_logger
from .mcp_tasks_local import run_local

logger = setup_logger("mcp")


async def mcp_task_async(
    agent_name: str,
    task: str,
    payload: Dict[str, Any],
    fallback: Optional[Callable[[], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    endpoint = os.getenv("MCP_ENDPOINT")
    req = {"agent": agent_name, "task": task, "payload": payload}
    logger.info(f"MCP call -> {json.dumps(req)}")

    # Optional preference: only call remote if explicitly preferred
    prefer_remote = os.getenv("MCP_PREFER_REMOTE", "0") in {"1", "true", "True"}
    if endpoint and prefer_remote:
        try:
            timeout_s = float(os.getenv("MCP_TIMEOUT", "5"))
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(endpoint.rstrip("/") + "/task", json=req)
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"MCP remote <- {json.dumps(data)}")
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning(f"MCP remote call failed: {e}")

    # Provider-first path (Anthropic/OpenAI) when available
    provider_name = os.getenv("LLM_PROVIDER") or ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else "local")
    provider = get_provider(provider_name)
    try:
        if agent_name == "intent" and task == "classify_intent":
            labels = payload.get("labels", [])
            text = payload.get("text", "")
            prompt = (
                "Classify the intent of the user as one of: "
                + ", ".join(labels)
                + ". Just answer with the label.\nUser: "
                + text
            )
            out = provider.generate(prompt)
            guess = next((l for l in labels if l.lower() in (out or "").lower()), None)
            data = {"intent": guess or (labels[0] if labels else "other")}
            logger.info(f"MCP provider <- {json.dumps(data)}")
            return data
        if agent_name == "datetime" and task == "extract_datetime":
            text = payload.get("text", "")
            prompt = (
                "Extract future date (YYYY-MM-DD), day (Weekday), and time (HH:MM) from the text. "
                "Respond as JSON with keys date, day, time. If unsure, null.\nText: "
                + text
            )
            out = provider.generate(prompt)
            try:
                data = json.loads(out)
            except Exception:
                # Use the local deterministic parser for reliability
                from .mcp_tasks_local import task_datetime as _local_datetime
                data = _local_datetime({"text": text})
            else:
                # Validate and repair using local deterministic parser if any field is missing/invalid
                if not isinstance(data, dict) or not data.get("date") or not data.get("time"):
                    from .mcp_tasks_local import task_datetime as _local_datetime
                    local_data = _local_datetime({"text": text})
                    # Prefer provider fields if present, otherwise local
                    data = {
                        "date": data.get("date") or local_data.get("date"),
                        "day": data.get("day") or local_data.get("day"),
                        "time": data.get("time") or local_data.get("time"),
                    }
            logger.info(f"MCP provider <- {json.dumps(data)}")
            return data
        if agent_name == "mode" and task == "infer_mode":
            text = payload.get("text", "")
            prompt = (
                "Infer appointment mode as 'virtual' or 'telephonic'. Answer with one word.\nText: "
                + text
            )
            out = (provider.generate(prompt) or "").lower()
            mode = "virtual"
            if "tele" in out or "phone" in out:
                mode = "telephonic"
            data = {"mode": mode}
            logger.info(f"MCP provider <- {json.dumps(data)}")
            return data
        if agent_name == "confirmation" and task == "generate_confirmation":
            date = payload.get("date")
            day = payload.get("day")
            time = payload.get("time")
            mode = payload.get("mode")
            data = {"text": f"Your {mode} appointment is booked for {day}, {date} at {time}."}
            logger.info(f"MCP provider <- {json.dumps(data)}")
            return data
    except Exception as e:
        logger.warning(f"Local provider generation failed: {e}")

    # Local registry as fallback
    try:
        data = run_local(agent_name, task, payload)
        if data:
            logger.info(f"MCP local <- {json.dumps(data)}")
            return data
    except Exception as e:
        logger.warning(f"MCP local registry error: {e}")

    if fallback:
        data = fallback()  # type: ignore
        logger.info(f"MCP fallback <- {json.dumps(data)}")
        return data
    return {}


def mcp_task(
    agent_name: str,
    task: str,
    payload: Dict[str, Any],
    fallback: Optional[Callable[[], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return asyncio.run(mcp_task_async(agent_name, task, payload, fallback))
