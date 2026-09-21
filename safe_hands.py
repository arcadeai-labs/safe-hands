"""
Safe Hands. The runtime that governs what an AI agent is allowed to do to a robot.

    "The model reasons. The runtime governs." Now for the things that can hurt you.

An agent calls robot tools (move, grasp, e-stop...). Every call is checked against a
per-operator authorization policy BEFORE it reaches the actuator, unsafe calls are denied,
and everything is audited. This is the missing layer under every robot-MCP demo, which today
let anyone who reaches the server command the arm with no identity, scope, or record.
"""
from __future__ import annotations
import math, time, json, functools
from dataclasses import dataclass, field
from typing import Callable

# ----------------------------------------------------------------------------- the robot
@dataclass
class Arm:
    """A minimal 2-link planar arm. Kinematic (the point here is CONTROL, not dynamics)."""
    j1: float = 0.0            # shoulder angle (rad)
    j2: float = 0.0            # elbow angle (rad)
    grasping: bool = False
    safety_engaged: bool = True
    L1: float = 0.30
    L2: float = 0.25
    J_LIMIT: float = 2.6       # hard physical joint limit (rad); beyond this = mechanical damage

    def tip(self) -> tuple[float, float]:
        x = self.L1*math.cos(self.j1) + self.L2*math.cos(self.j1 + self.j2)
        y = self.L1*math.sin(self.j1) + self.L2*math.sin(self.j1 + self.j2)
        return round(x, 3), round(y, 3)

    def state(self) -> dict:
        return {"j1": round(self.j1, 3), "j2": round(self.j2, 3),
                "tip": self.tip(), "grasping": self.grasping,
                "safety_engaged": self.safety_engaged}


# --------------------------------------------------------------------- authorization policy
@dataclass
class Scope:
    """What THIS operator (identity) is permitted to do. Arcade-style: per-user, per-action."""
    operator: str
    allowed_tools: set[str]
    joint_limit: float          # this operator's SOFTWARE limit (<= the arm's hard limit)

@dataclass
class Denied(Exception):
    tool: str
    reason: str

class Guard:
    """The runtime that governs. Wraps every tool: authorize -> execute -> audit."""
    def __init__(self, arm: Arm, scope: Scope):
        self.arm, self.scope, self.audit_log = arm, scope, []

    def _audit(self, tool, args, outcome, reason=""):
        self.audit_log.append({"t": round(time.time(), 3), "operator": self.scope.operator,
                               "tool": tool, "args": args, "outcome": outcome, "reason": reason})

    def call(self, tool: str, **args):
        # 1) identity + scope check
        if tool not in self.scope.allowed_tools:
            self._audit(tool, args, "DENIED", f"'{self.scope.operator}' not scoped for '{tool}'")
            raise Denied(tool, f"operator '{self.scope.operator}' is not authorized to call '{tool}'")
        # 2) per-action safety constraints
        if tool == "set_joint":
            target = float(args.get("value", 0.0))
            if abs(target) > self.scope.joint_limit:
                self._audit(tool, args, "DENIED", f"|{target}| exceeds operator limit {self.scope.joint_limit}")
                raise Denied(tool, f"joint target {target} exceeds this operator's safe limit ±{self.scope.joint_limit}")
        # 3) execute against the actuator
        result = TOOLS[tool](self.arm, **args)
        self._audit(tool, args, "OK")
        return result


# ------------------------------------------------------------------------------ MCP tools
# The robot's action surface, exactly what an agent would see as callable MCP tools.
JOINTS = frozenset({"j1", "j2"})   # the only attributes an actuator command may write
TOOLS: dict[str, Callable] = {}
def tool(fn):
    TOOLS[fn.__name__] = fn
    return fn

@tool
def get_state(arm: Arm): return arm.state()
@tool
def set_joint(arm: Arm, joint: str, value: float):
    if joint not in JOINTS:
        raise ValueError(f"unknown joint {joint!r}; valid joints: {sorted(JOINTS)}")
    setattr(arm, joint, float(value)); return arm.state()
@tool
def grasp(arm: Arm): arm.grasping = True; return arm.state()
@tool
def release(arm: Arm): arm.grasping = False; return arm.state()
@tool
def emergency_stop(arm: Arm): arm.j1 = arm.j2 = 0.0; arm.grasping = False; return {"estopped": True}
@tool
def disable_safety(arm: Arm): arm.safety_engaged = False; return {"safety_engaged": False}
