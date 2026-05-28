"""visual-obs-remote — OBS WebSocket v5 で録画制御.

OBS Studio の obs-websocket plugin (v5+) 越しに StartRecord/StopRecord/
GetRecordStatus を発行。販売物録画の standard runner。
"""
from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-obs-remote"


async def obs_call(host: str, port: int, password: str, op: str,
                   payload: dict | None = None) -> dict:
    try:
        import websockets
    except ImportError:
        raise RuntimeError("websockets not installed: pip install websockets")
    url = f"ws://{host}:{port}"
    async with websockets.connect(url) as ws:
        # Hello (op 0)
        hello = json.loads(await ws.recv())
        d = hello["d"]
        # Identify (op 1)
        ident = {"op": 1, "d": {"rpcVersion": 1}}
        if "authentication" in d:
            chal = d["authentication"]["challenge"]
            salt = d["authentication"]["salt"]
            secret = base64.b64encode(
                hashlib.sha256((password + salt).encode()).digest()).decode()
            auth = base64.b64encode(
                hashlib.sha256((secret + chal).encode()).digest()).decode()
            ident["d"]["authentication"] = auth
        await ws.send(json.dumps(ident))
        await ws.recv()  # Identified (op 2)
        req_id = str(uuid.uuid4())
        req = {"op": 6, "d": {"requestType": op, "requestId": req_id,
                              "requestData": payload or {}}}
        await ws.send(json.dumps(req))
        while True:
            msg = json.loads(await ws.recv())
            if msg["op"] == 7 and msg["d"]["requestId"] == req_id:
                return msg["d"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual obs-remote")
    p.add_argument("action", choices=["start", "stop", "status", "toggle"])
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=4455)
    p.add_argument("--password", default="", help="env OBS_PASSWORD 推奨")
    return p


def run(args: argparse.Namespace) -> int:
    import os
    password = args.password or os.environ.get("OBS_PASSWORD", "")
    op_map = {"start": "StartRecord", "stop": "StopRecord",
              "status": "GetRecordStatus", "toggle": "ToggleRecord"}
    op = op_map[args.action]
    try:
        result = asyncio.run(obs_call(args.host, args.port, password, op))
    except Exception as e:
        logger.error(TOOL_ID, f"obs ws failed: {e}")
        return 3
    print(json.dumps(result, indent=2))
    logger.done(TOOL_ID, f"obs {args.action} -> {result.get('requestStatus', {}).get('result')}")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
