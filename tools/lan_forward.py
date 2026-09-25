"""Expose the local Locally Uncensored model servers on the LAN (no authentication).

    uv run python tools/lan_forward.py                 # 0.0.0.0:8200 -> chat, 0.0.0.0:8201 -> embeddings
    uv run python tools/lan_forward.py --chat-port 9000

Plain TCP forwarding, so streaming responses work unchanged. The target ports are read from the
running lu-llama-server processes, so it keeps working if Locally Uncensored picks new ports.
Anyone on the same network can use the model while this runs; stop it with Ctrl+C.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path


def lu_ports() -> dict[str, int]:
    """{"chat": port, "embeddings": port} of the running lu-llama-server processes."""
    found: dict[str, int] = {}
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            args = [a.decode(errors="replace") for a in (proc / "cmdline").read_bytes().split(b"\0") if a]
        except OSError:
            continue
        if not args or not Path(args[0]).name.startswith("lu-llama-server") or "--port" not in args:
            continue
        port = int(args[args.index("--port") + 1])
        found["embeddings" if "--embeddings" in args else "chat"] = port
    return found


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


def handler(target_port: int, name: str):
    async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        peer = client_w.get_extra_info("peername")
        try:
            up_r, up_w = await asyncio.open_connection("127.0.0.1", target_port)
        except OSError:
            print(f"[{name}] {peer[0]}: model server on port {target_port} is not reachable")
            client_w.close()
            return
        print(f"[{name}] connection from {peer[0]}", flush=True)
        await asyncio.gather(pipe(client_r, up_w), pipe(up_r, client_w))

    return handle


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chat-port", type=int, default=8200)
    ap.add_argument("--embed-port", type=int, default=8201)
    args = ap.parse_args()
    ports = lu_ports()
    if "chat" not in ports:
        raise SystemExit("No Locally Uncensored chat model running (lu-llama-server). Start Qwen in LU first.")
    servers = [await asyncio.start_server(handler(ports["chat"], "chat"), "0.0.0.0", args.chat_port)]
    print(f"chat:       0.0.0.0:{args.chat_port} -> 127.0.0.1:{ports['chat']}")
    if "embeddings" in ports:
        servers.append(await asyncio.start_server(handler(ports["embeddings"], "embeddings"), "0.0.0.0", args.embed_port))
        print(f"embeddings: 0.0.0.0:{args.embed_port} -> 127.0.0.1:{ports['embeddings']}")
    print("Anyone on this network can use the model while this runs. Ctrl+C to stop.", flush=True)
    await asyncio.gather(*(s.serve_forever() for s in servers))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
