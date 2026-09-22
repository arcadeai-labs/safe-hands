"""
Safe Hands MCP server. It exposes a robot arm to AI agents over the Model Context Protocol, with
every action governed first by contextual authorization (WHO is calling and what they're granted),
and then by Asimov's Three Laws (compiled to Cedar policy). Both layers, every call.

Two things the agent CANNOT do:
  1. Assert its own identity. It must present a token; the runtime resolves the principal and its
     grant. (This emulates Arcade-style contextual auth, where in production the identity comes from the
     user's OAuth/session context, not from anything the model says.)
  2. Assert whether a human is present. There is no tool for it. The runtime reads a trusted sensor
     feed (sensor.py, a stand-in for a safety-rated hardware sensor) on every governed call and
     enforces the First Law on the sensed value. If the sensor is unreadable, the runtime fails closed
     and assumes a human is present.

    Run as an MCP server:   python server.py           (stdio; add to any MCP client)
    Or see it governed:     python server.py --smoke
"""
import math, time
try:                                     # mcp >= 2.0 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:                      # mcp 1.x
    from mcp.server.fastmcp import FastMCP
from safe_hands import Arm, TOOLS, JOINTS
from governance import authorize, scopes_of, AUDIT
import sensor

mcp = FastMCP("safe-hands")
ARM = Arm()

# Arcade-style contextual auth: an opaque token resolves to a principal and its contextual grant.
# The agent never names itself. It presents a token and the runtime decides who that is.
GRANTS = {"tok-alice": "warehouse-op", "tok-bob": "line-operator", "tok-carol": "observer"}
SESSION = {"principal": None}

# Every tool the agent can see, so the smoke can prove what is NOT on the surface.
TOOL_SURFACE: list[str] = []
def agent_tool(fn):
    TOOL_SURFACE.append(fn.__name__)
    return mcp.tool()(fn)


def _refuse(principal, action: str, law: str, message: str) -> dict:
    """A refusal that never reached the Laws is still an event the audit must hold."""
    AUDIT.append({"t": round(time.time(), 3), "operator": principal, "action": action, "decision": "Deny", "law": law})
    return {"status": "DENIED", "principal": principal, "law": law, "action": action, "message": message}


def _governed(action: str, joint_target: int = 0, speed: int = 0, **actuator_kw) -> dict:
    principal = SESSION["principal"]
    if principal is None:
        return _refuse(None, action, "authentication required", "No authenticated principal. Call authenticate(token) first.")
    sensed = sensor.read()                        # the runtime asks the sensor, never the agent
    world = {"human_in_workspace": sensed["human_in_workspace"], "speed": speed, "joint_target": joint_target}
    allow, law = authorize(principal, action, world)
    if not allow:
        return {"status": "DENIED", "principal": principal, "law": law, "action": action,
                "sensed": sensed, "message": f"{law} refused '{action}'."}
    result = TOOLS[action](ARM, **actuator_kw)
    return {"status": "OK", "principal": principal, "law": law, "action": action, "state": result}


@agent_tool
def authenticate(token: str) -> dict:
    """Present a token; the runtime resolves your principal and contextual grant (Arcade-style).
    The agent cannot assert an identity, only present a token the runtime validates."""
    principal = GRANTS.get(token)
    if principal is None:
        SESSION["principal"] = None
        return {"status": "DENIED", "message": "Unknown token, no principal."}
    SESSION["principal"] = principal
    return {"status": "OK", "principal": principal, "granted_actions": scopes_of(principal)}

@agent_tool
def whoami() -> dict:
    """The current authenticated principal and the actions it is granted."""
    p = SESSION["principal"]
    return {"principal": p, "granted_actions": scopes_of(p) if p else []}

@agent_tool
def move_joint(joint: str, target_degrees: int, speed_cm_s: int = 10) -> dict:
    """Move a joint of the arm (j1 or j2) to a target angle (degrees) at a requested tip speed (cm/s).
    Governed by contextual auth + the Three Laws: the speed is the agent's request, whether a human
    is present is the sensor's report, and the First Law is decided on both."""
    if joint not in JOINTS:   # only real joints are actuator targets; never an arbitrary attribute
        return _refuse(SESSION["principal"], "set_joint", "invalid joint", f"Unknown joint '{joint}'. Valid joints: {sorted(JOINTS)}.")
    return _governed("set_joint", joint_target=target_degrees, speed=speed_cm_s,
                     joint=joint, value=math.radians(target_degrees))

@agent_tool
def grasp() -> dict:
    """Close the gripper. Governed by contextual auth + the Three Laws."""
    return _governed("grasp")

@agent_tool
def release() -> dict:
    """Open the gripper. Governed by contextual auth + the Three Laws."""
    return _governed("release")

@agent_tool
def emergency_stop() -> dict:
    """Halt the arm immediately (requires a grant for it)."""
    return _governed("emergency_stop")

@agent_tool
def disable_safety() -> dict:
    """Attempt to disable the safety system. (An unscoped identity is refused by the Second Law;
    even a scoped one is refused by the First Law.)"""
    return _governed("disable_safety")

@agent_tool
def get_state() -> dict:
    """Read the arm's current joint angles, tip position, and safety status (requires a grant for it)."""
    return _governed("get_state")

@agent_tool
def audit() -> list:
    """The audit trail: every action, its principal, decision, and which Law decided."""
    return AUDIT[-25:]


def _smoke():
    import json
    print("SAFE HANDS MCP. Contextual auth + the Three Laws\n" + "=" * 72)
    print("agent-visible tools:", ", ".join(TOOL_SURFACE))
    assert "human_presence" not in TOOL_SURFACE and not any("sensor" in t for t in TOOL_SURFACE)
    print("(no tool writes the sensor; the agent cannot say whether a human is present)")
    def show(label, r):
        who = r.get("principal", "n/a")
        print(f"{'✅' if r.get('status')=='OK' else '⛔'} {label:<44} [{who:<13}] -> {r.get('law') or r.get('message')}")
    def event(label): print(f"   [sensor] {label}")

    sensor.write(False); event("workspace clear")
    print("\n· Carol (observer, granted get_state only):")
    authenticate("tok-carol")
    show("get_state", get_state())                              # allowed (granted)
    show("move_joint j1 -> 45deg", move_joint("j1", 45))        # no grant -> Second Law
    show("disable_safety", disable_safety())                    # no grant -> Second Law

    print("\n· Bob (line-operator, can move but cannot disable safety):")
    authenticate("tok-bob")
    show("grasp (routine)", grasp())                            # allowed
    show("move_joint j1 -> 45deg", move_joint("j1", 45))        # allowed
    show("disable_safety", disable_safety())                    # no grant -> Second Law

    print("\n· Alice (warehouse-op, fully scoped, even for disable_safety):")
    authenticate("tok-alice")
    show("move_joint j1 -> 175deg (past limit)", move_joint("j1", 175))     # Third Law
    show("move_joint j1 -> -175deg (past limit)", move_joint("j1", -175))   # Third Law, other direction
    show("move_joint 'safety_engaged' -> 0 (smuggle)", move_joint("safety_engaged", 0))  # not a joint
    sensor.write(True); event("a human enters the cell")
    show("move_joint j2 -> 30deg at 90 cm/s (human near)", move_joint("j2", 30, speed_cm_s=90))  # First Law
    show("move_joint j2 -> 30deg at 10 cm/s (human near)", move_joint("j2", 30, speed_cm_s=10))  # allowed: slow
    show("disable_safety (scoped, but forbidden)", disable_safety())        # First Law overrides grant
    sensor.clear(); event("sensor OFFLINE (file gone): runtime fails closed")
    show("move_joint j1 -> 20deg at 90 cm/s (sensor blind)", move_joint("j1", 20, speed_cm_s=90))  # First Law
    show("move_joint j1 -> 20deg at 10 cm/s (sensor blind)", move_joint("j1", 20, speed_cm_s=10))  # allowed
    sensor.write(False)

    print("=" * 72 + "\nAUDIT:")
    print(json.dumps(audit(), indent=2))


if __name__ == "__main__":
    import sys
    if "--smoke" in sys.argv:
        _smoke()
    else:
        mcp.run()
