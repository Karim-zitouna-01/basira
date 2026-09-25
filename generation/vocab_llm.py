"""Enrich the name vocabularies with the local Qwen model (optional, offline step).

    uv run python -m generation.vocab_llm [--url http://127.0.0.1:8127/v1]

By default it finds the chat model served by Locally Uncensored (its `lu-llama-server`
process, skipping the embeddings server) and reads the port from the process arguments.
`--url` or the BASIRA_LLM_URL variable override that with any OpenAI-compatible endpoint.
Everything stays on the machine. The result is cached in generation/vocab/llm_vocab.json and read by
generation.vocab; the data pipeline itself never calls the model.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import urllib.request
from pathlib import Path

from .vocab import RESERVED, SUPPLIER_PARTS, VOCAB_FILE

VALID = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' \-]{1,22}$")

PROMPTS = {
    "tn_stems": (
        "Donne 60 mots ou courtes expressions (1 à 3 mots, translittération latine) utilisés comme nom commercial "
        "par des PME tunisiennes : noms arabes positifs (ex. El Amen, Ennour, El Baraka), lieux et sites historiques "
        "tunisiens (ex. Carthage, Sahel, Byrsa). Pas de noms de personnes connues, pas de marques existantes."
    ),
    "tn_families": (
        "Donne 60 noms de famille tunisiens courants, en translittération française (ex. Ben Salah, Masmoudi, "
        "Ellouze). Pas de personnalités publiques."
    ),
}
COUNTRY_NAMES = {"CN": "chinoises", "IT": "italiennes", "FR": "françaises", "DE": "allemandes", "TR": "turques",
                 "ES": "espagnoles", "DZ": "algériennes"}


def find_lu_server() -> tuple[str, str] | None:
    """Locate the Locally Uncensored chat server: (base url, model file name), or None."""
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            args = (proc / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        args = [a.decode(errors="replace") for a in args if a]
        if not args or not Path(args[0]).name.startswith("lu-llama-server") or "--embeddings" in args:
            continue
        opts = {args[k]: args[k + 1] for k in range(len(args) - 1) if args[k].startswith("-")}
        host = opts.get("--host", "127.0.0.1")
        port = opts.get("--port", "8080")
        model = Path(opts.get("-m", opts.get("--model", "model"))).stem
        return f"http://{host}:{port}/v1", model
    return None


def resolve_endpoint(url: str | None) -> tuple[str, str]:
    if url:
        return url, "local"
    if os.environ.get("BASIRA_LLM_URL"):
        return os.environ["BASIRA_LLM_URL"], "local"
    found = find_lu_server()
    if found:
        return found
    raise SystemExit("No Locally Uncensored chat server found (lu-llama-server). Start a chat model in LU "
                     "or pass --url " + shlex.quote("http://127.0.0.1:<port>/v1") + ".")


def ask(url: str, model: str, prompt: str) -> list[str]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Tu réponds uniquement par un tableau JSON de chaînes, sans texte autour."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 1200,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(f"{url.rstrip('/')}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        content = json.loads(resp.read())["choices"][0]["message"]["content"]
    match = re.search(r"\[.*\]", content, re.S)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return clean(items)


def clean(items: list) -> list[str]:
    out, seen = [], set()
    for it in items:
        if not isinstance(it, str):
            continue
        w = " ".join(it.strip().split())
        if not VALID.match(w) or w.lower() in seen or set(w.lower().split()) & RESERVED:
            continue
        seen.add(w.lower())
        out.append(w)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=None, help="OpenAI-compatible base URL (default: auto-detect Locally Uncensored)")
    args = ap.parse_args()
    url, model = resolve_endpoint(args.url)
    print(f"LLM endpoint: {url} ({model})")

    vocab: dict = {"source": f"{url} ({model})", "supplier_words": {}}
    for key, prompt in PROMPTS.items():
        vocab[key] = ask(url, model, prompt)
        print(f"{key}: {len(vocab[key])} entries")
    for cc in SUPPLIER_PARTS:
        prompt = (f"Donne 30 mots utilisables dans des raisons sociales d'entreprises industrielles {COUNTRY_NAMES[cc]} "
                  "fictives : noms de famille, villes ou régions du pays. Un ou deux mots maximum, sans forme juridique.")
        vocab["supplier_words"][cc] = ask(url, model, prompt)
        print(f"supplier_words[{cc}]: {len(vocab['supplier_words'][cc])} entries")
    VOCAB_FILE.parent.mkdir(parents=True, exist_ok=True)
    VOCAB_FILE.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {VOCAB_FILE}")


if __name__ == "__main__":
    main()
