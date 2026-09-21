"""
Safe Hands MCP server. It exposes a robot arm to AI agents over the Model Context Protocol, with
every action governed first by contextual authorization (WHO is calling and what they're granted),
and then by Asimov's Three Laws (compiled to Cedar policy). Both layers, every call.

Two things the agent CANNOT do:
  1. Assert its own identity. It must present a token; the runtime resolves the principal and its
     grant. (This emulates Arcade-style contextual auth, where in production the identity comes from the
     user's OAuth/session context, not from anything the model says.)
  2. Assert whether a human is present. That comes from a trusted sensor feed gated by an out-of-band
     token the agent does not hold; the runtime enforces the First Law on the sensed value itself.

    Run as an MCP server:   python server.py           (stdio; add to any MCP client)
    Or see it governed:     python server.py --smoke
"""
import math
try:                                     # mcp >= 2.0 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:                      # mcp 1.x
    from mcp.server.fastmcp import FastMCP
from safe_hands import Arm, TOOLS, JOINTS
from governance import authorize, scopes_of, AUDIT

mcp = FastMCP("safe-hands")
ARM = Arm()
WORLD = {"human_in_workspace": False, "speed": 10}   # sensed environment state (not agent-controlled)

# Arcade-style contextual auth: an opaque token resolves to a principal and its contextual grant.
# The agent never names itself. It presents a token and the runtime decides who that is.
GRANTS = {"tok-alice": "warehouse-op", "tok-bob": "line-operator", "tok-carol": "observer"}
SESSION = {"principal": None}

# The human-presence signal is a TRUSTED SENSOR FEED, not an agent capability. In production it is a
# hardware safety sensor; here it is a stand-in that requires an out-of-band token the agent does not
# hold. This is what makes "the agent cannot assert whether a human is present" true and not just
# aspirational: an agent that calls human_presence() without this token is refused.
SENSOR_TOKEN = "sensor-feed-key"


def _governed(action: str, joint_target: int = 0, **actuator_kw) -> dict:
    principal = SESSION["principal"]
    if principal is None:
        return {"status": "DENIED", "law": "authentication required",
                "action": action, "message": "No authenticated principal. Call authenticate(token) first."}
    allow, law = authorize(principal, action, {**WORLD, "joint_target": joint_target})
    if not allow:
        return {"status": "DENIED", "principal": principal, "law": law, "action": action,
                "message": f"{law} refused '{action}'."}
    result = TOOLS[action](ARM, **actuator_kw)
    return {"status": "OK", "principal": principal, "law": law, "action": action, "state": result}


@mcp.tool()
def authenticate(token: str) -> dict:
    """Present a token; the runtime resolves your principal and contextual grant (Arcade-style).
    The agent cannot assert an identity, only present a token the runtime validates."""
    principal = GRANTS.get(token)
    if principal is None:
        SESSION["principal"] = None
        return {"status": "DENIED", "message": "Unknown token, no principal."}
    SESSION["principal"] = principal
    return {"status": "OK", "principal": principal, "granted_actions": scopes_of(principal)}

@mcp.tool()
def whoami() -> dict:
    """The current authenticated principal and the actions it is granted."""
    p = SESSION["principal"]
    return {"principal": p, "granted_actions": scopes_of(p) if p else []}

@mcp.tool()
def move_joint(joint: str, target_degrees: int) -> dict:
    """Move a joint of the arm (j1 or j2) to a target angle (degrees). Governed by contextual auth + the Three Laws."""
    if joint not in JOINTS:   # only real joints are actuator targets; never an arbitrary attribute
        return {"status": "DENIED", "law": "invalid joint", "action": "set_joint",
                "message": f"Unknown joint '{joint}'. Valid joints: {sorted(JOINTS)}."}
    return _governed("set_joint", joint_target=target_degrees, joint=joint, value=math.radians(target_degrees))

@mcp.tool()
def grasp() -> dict:
    """Close the gripper. Governed by contextual auth + the Three Laws."""
    return _governed("grasp")

@mcp.tool()
def release() -> dict:
    """Open the gripper. Governed by contextual auth + the Three Laws."""
    return _governed("release")

@mcp.tool()
def emergency_stop() -> dict:
    """Halt the arm immediately (requires a grant for it)."""
    return _governed("emergency_stop")

@mcp.tool()
def disable_safety() -> dict:
    """Attempt to disable the safety system. (An unscoped identity is refused by the Second Law;
    even a scoped one is refused by the First Law.)"""
    return _governed("disable_safety")

@mcp.tool()
def get_state() -> dict:
    """Read the arm's current joint angles, tip position, and safety status (requires a grant for it)."""
    return _governed("get_state")

@mcp.tool()
def human_presence(present: bool = True, speed: int = 90, sensor_token: str = "") -> dict:
    """Trusted sensor feed: report whether a human is in the workspace. Requires the out-of-band
    sensor token; an agent does not hold it, so it cannot spoof the human away to bypass the First
    Law. In production this is a hardware sensor, not an agent-exposed tool at all."""
    if sensor_token != SENSOR_TOKEN:
        return {"status": "DENIED", "message": "human_presence is a trusted sensor feed; "
                "the agent cannot write it (out-of-band sensor token required)."}
    WORLD["human_in_workspace"] = present
    WORLD["speed"] = speed if present else 10
    return {"status": "OK", "human_in_workspace": present, "speed": WORLD["speed"]}

@mcp.tool()
def audit() -> list:
    """The audit trail: every action, its principal, decision, and which Law decided."""
    return AUDIT[-25:]


def _smoke():
    import json
    print("SAFE HANDS MCP. Contextual auth + the Three Laws\n" + "=" * 72)
    def show(label, r):
        who = r.get("principal", "n/a")
        print(f"{'✅' if r.get('status')=='OK' else '⛔'} {label:<40} [{who:<13}] -> {r.get('law') or r.get('message')}")

    print("\n· Carol (observer, granted get_state only):")
    authenticate("tok-carol")
    show("move_joint j1 -> 45deg", move_joint("j1", 45))       # no grant -> Second Law
    show("disable_safety", disable_safety())                    # no grant -> Second Law

    print("\n· Bob (line-operator, can move but cannot disable safety):")
    authenticate("tok-bob")
    show("grasp (routine)", grasp())                            # allowed
    show("move_joint j1 -> 45deg", move_joint("j1", 45))        # allowed
    show("disable_safety", disable_safety())                    # no grant -> Second Law

    print("\n· Alice (warehouse-op, fully scoped, even for disable_safety):")
    authenticate("tok-alice")
    show("move_joint j1 -> 175deg (past limit)", move_joint("j1", 175))   # Third Law
    show("move_joint j1 -> -175deg (past limit)", move_joint("j1", -175)) # Third Law, other direction
    show("move_joint 'safety_engaged' -> 0 (smuggle)", move_joint("safety_engaged", 0))  # not a joint
    human_presence(True, 90, SENSOR_TOKEN)                                # trusted sensor: a human enters
    show("[trusted sensor: human enters]", {"status": "OK", "principal": "sensor", "law": "sensed"})
    show("agent tries to spoof the human away", human_presence(False, sensor_token="guessed"))  # refused
    show("move_joint j2 -> 30deg (fast, human near)", move_joint("j2", 30))  # First Law
    show("disable_safety (scoped, but forbidden)", disable_safety())          # First Law overrides grant

    print("=" * 72 + "\nAUDIT:")
    print(json.dumps(audit(), indent=2))


if __name__ == "__main__":
    import sys
    if "--smoke" in sys.argv:
        _smoke()
    else:
        mcp.run()
