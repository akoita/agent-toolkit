"""Extract bounded worker metrics from private rollouts without copying prompts.

Usage: python collect.py LOW_ROLLOUT MEDIUM_ROLLOUT > metrics.json
The caller must verify child identity and routing separately.
"""
import json
import sys
from pathlib import Path


def collect(path):
    turns, calls, usage, routes = [], 0, None, set()
    for line in Path(path).read_text().splitlines():
        event = json.loads(line)
        payload = event.get("payload", {})
        if event.get("type") == "turn_context":
            routes.add((payload.get("model"), payload.get("effort")))
        elif event.get("type") == "event_msg":
            if payload.get("type") == "task_complete":
                turns.append(payload["duration_ms"])
            elif payload.get("type") == "token_count" and payload.get("info"):
                usage = payload["info"]["total_token_usage"]
        elif event.get("type") == "response_item" and payload.get("type") in ("function_call", "custom_tool_call"):
            calls += 1
    if len(turns) != 2 or len(routes) != 1 or usage is None:
        raise ValueError("expected one handshake and one assignment on a stable route")
    return {
        "route": list(next(iter(routes))),
        "handshake_ms": turns[0], "assignment_ms": turns[1],
        "worker_active_ms": sum(turns), "outer_tool_calls": calls,
        "tokens_including_handshake": usage,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(json.dumps({name: collect(path) for name, path in zip(("low", "medium"), sys.argv[1:])}, indent=2))
