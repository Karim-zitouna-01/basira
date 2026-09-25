"""Faux serveur LLM compatible OpenAI (llama-server) pour tester l'assistant sans le Qwen distant.

    uv run uvicorn tools.faux_llm:app --port 8200
    LLM_BASE_URL=http://127.0.0.1:8200/v1 uv run uvicorn api.main:app --port 8000

FAUX_LLM_SANS_OUTILS=1 : refuse le paramètre `tools` (HTTP 400), comme llama-server lancé sans --jinja.
Chaque requête reçue est journalisée (outils demandés, enable_thinking, taille des messages).
"""

import json
import os
import re
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
SANS_OUTILS = os.environ.get("FAUX_LLM_SANS_OUTILS") == "1"


def _reponse(message: dict, fin: str = "stop") -> dict:
    return {"id": f"chatcmpl-{time.time_ns()}", "object": "chat.completion", "created": int(time.time()),
            "model": "faux-qwen", "choices": [{"index": 0, "finish_reason": fin, "message": message}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    corps = await req.json()
    msgs = corps.get("messages", [])
    print(f"[faux_llm] outils={bool(corps.get('tools'))} kwargs={corps.get('chat_template_kwargs')} "
          f"messages={len(msgs)} systeme={sum(m['role'] == 'system' for m in msgs)} "
          f"caracteres={sum(len(m.get('content') or '') for m in msgs)}", flush=True)
    if corps.get("tools") and SANS_OUTILS:
        return JSONResponse({"error": {"code": 400, "message": "tools param requires --jinja flag",
                                       "type": "invalid_request_error"}}, status_code=400)
    outils_vus = [m for m in msgs if m["role"] == "tool"]
    if corps.get("tools") and not outils_vus:
        return _reponse({"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "get_entreprise", "arguments": "{}"}}]}, "tool_calls")
    contexte = " ".join(m.get("content") or "" for m in msgs)
    codes = list(dict.fromkeys(re.findall(r'"code_signal": "([A-Z_]+)"', contexte)))[:2]
    texte = ("Le risque s'explique surtout par " + (" et ".join(codes) or "aucun signal actif")
             + ". La décision appartient à l'inspecteur.\nSOURCES : " + ", ".join(codes))
    return _reponse({"role": "assistant", "content": texte})


@app.get("/v1/models")
def modeles():
    return {"object": "list", "data": [{"id": "faux-qwen", "object": "model"}]}


if __name__ == "__main__":
    print(json.dumps(modeles()))
