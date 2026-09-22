"""The trusted sensor feed, as a stand-in. NOT an MCP tool.

In production the human-presence signal comes from a safety-rated hardware sensor (a light curtain,
a laser scanner, a pressure mat). Here it is a small JSON file that a separate process writes and the
MCP server reads on every governed call. The agent has no tool that writes it: the only way to change
what the runtime believes about the workspace is to be the sensor.

Fail-closed: if the file is missing or unreadable, the runtime assumes a human IS present. A blind
sensor must never read as an empty cell.

    python sensor.py enter     # a human walks into the workspace
    python sensor.py leave     # the workspace is clear
    python sensor.py status
"""
import json, os, sys, time

_HERE = os.path.dirname(os.path.abspath(__file__))
SENSOR_FILE = os.environ.get("SAFE_HANDS_SENSOR", os.path.join(_HERE, ".sensor_state.json"))
FAIL_CLOSED = {"human_in_workspace": True, "source": "fail-closed (no sensor reading)"}


def read() -> dict:
    """What the runtime believes about the workspace right now."""
    try:
        with open(SENSOR_FILE) as f:
            s = json.load(f)
        return {"human_in_workspace": bool(s["human_in_workspace"]), "source": SENSOR_FILE}
    except (OSError, ValueError, KeyError, TypeError):
        return dict(FAIL_CLOSED)


def write(human_in_workspace: bool) -> dict:
    """Only the sensor process calls this. It is deliberately not reachable from server.py's tools."""
    s = {"human_in_workspace": bool(human_in_workspace), "t": round(time.time(), 3)}
    with open(SENSOR_FILE, "w") as f:
        json.dump(s, f)
    return s


def clear():
    """Simulate a sensor outage (the file disappears). The runtime must fail closed."""
    try: os.remove(SENSOR_FILE)
    except FileNotFoundError: pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "enter":   print(write(True))
    elif cmd == "leave": print(write(False))
    elif cmd == "clear": clear(); print(read())
    else:                print(read())
