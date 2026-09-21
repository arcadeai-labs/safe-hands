"""Safe Hands in front of IliaLarchenko/robot_MCP, with zero edits to their code.

robot_MCP is the reference "an LLM drives a SO-ARM100 over MCP" server: four tools, no identity,
no scope, no audit. This module imports their server as-is and:

  1. adds Safe Hands' `authenticate`, `whoami`, and `audit` tools to THEIR FastMCP instance, and
  2. swaps their lazy `get_robot()` for one that returns a GovernedRobot: a proxy around their
     RobotController that runs every actuator call through governance.authorize (contextual grant,
     then the Three Laws on the sensed workspace) before it reaches their code.

Their tools keep their names, arguments, and return shape. A refused command comes back as their
own MoveResult(ok=False) with the refusing Law in `message`, so the agent sees `status: error`.

    python governed.py --robot-mcp /path/to/robot_MCP            # real hardware, governed
    python governed.py --robot-mcp /path/to/robot_MCP --mock     # no hardware (fake lerobot)
"""
import argparse
import importlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # the Safe Hands repo root
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import governance      # noqa: E402  the Laws, the grant table, AUDIT
import sensor          # noqa: E402  the trusted sensor feed (not agent-writable)
import server as sh    # noqa: E402  GRANTS / SESSION / authenticate / whoami / audit


def load_robot_mcp(path: str, mock: bool):
    """Import their mcp_robot_server (and transitively robot_controller, config)."""
    if mock:
        import mock_lerobot
        mock_lerobot.install()
    path = os.path.abspath(path)
    if path not in sys.path:
        sys.path.insert(0, path)
    rm = importlib.import_module("mcp_robot_server")
    return rm


class GovernedRobot:
    """Proxy over their RobotController. Reads pass through; writes are authorized first."""

    def __init__(self, inner, rm):
        self._inner = inner
        self._rm = rm
        mc = rm.robot_config.MOVEMENT_CONSTANTS
        # Their moves have no speed argument: the arm interpolates at DEGREES_PER_STEP every
        # STEP_DELAY_SECONDS (150 deg/s at defaults). That fixed rate is the demo's speed proxy,
        # passed to the First Law in place of a measured tip speed (see README, "limits").
        self.speed_proxy = int(mc["DEGREES_PER_STEP"] / mc["STEP_DELAY_SECONDS"])

    def __getattr__(self, name):               # everything not governed here passes through
        return getattr(self._inner, name)

    # -- the decision ---------------------------------------------------------------------------
    def _refuse(self, msg):
        return _move_result(self._rm, False, msg, self._inner)

    def _decide(self, action: str, joint_target: int = 0, speed: int = 0):
        """Return None if allowed, else a MoveResult(ok=False) explaining which Law refused."""
        principal = sh.SESSION["principal"]
        if principal is None:
            governance.AUDIT.append({"t": round(time.time(), 3), "operator": None, "action": action,
                                     "decision": "Deny", "law": "authentication required"})
            return self._refuse("authentication required: no principal. Call authenticate(token) first.")
        sensed = sensor.read()                 # the runtime asks the sensor, never the agent
        world = {"human_in_workspace": sensed["human_in_workspace"], "speed": speed, "joint_target": joint_target}
        allow, law = governance.authorize(principal, action, world)
        if allow:
            return None
        return self._refuse(f"{law} refused '{action}'.")

    # -- governed writes ------------------------------------------------------------------------
    def execute_intuitive_move(self, **kw):
        angles = [abs(float(kw[k])) for k in ("tilt_gripper_down_angle",
                                              "rotate_gripper_counterclockwise_angle",
                                              "rotate_robot_left_angle") if kw.get(k) is not None]
        joint_target = int(max(angles)) if angles else 0      # largest requested step, in degrees
        refused = self._decide("set_joint", joint_target=joint_target, speed=self.speed_proxy)
        return refused or self._inner.execute_intuitive_move(**kw)

    def set_joints_absolute(self, positions_deg, use_interpolation=True):
        if set(positions_deg) == {"gripper"}:
            action = "grasp" if float(positions_deg["gripper"]) < 50 else "release"
            refused = self._decide(action)
        else:
            biggest = int(max(abs(float(v)) for v in positions_deg.values())) if positions_deg else 0
            refused = self._decide("set_joint", joint_target=biggest, speed=self.speed_proxy)
        return refused or self._inner.set_joints_absolute(positions_deg, use_interpolation)

    def apply_named_preset(self, preset_key):
        refused = self._decide("set_joint", joint_target=0, speed=self.speed_proxy)
        return refused or self._inner.apply_named_preset(preset_key)

    # -- governed read --------------------------------------------------------------------------
    def get_current_robot_state(self):
        refused = self._decide("get_state")
        return refused or self._inner.get_current_robot_state()

    # get_camera_images(): passthrough via __getattr__ (a read their tools bundle with state).

    def disconnect(self, reset_pos=True):
        # The runtime's own park-and-power-down at exit is not an agent command; it goes straight
        # to their controller (which internally calls its own, unwrapped, set_joints_absolute).
        return self._inner.disconnect(reset_pos)


def _move_result(rm, ok, msg, inner):
    MoveResult = sys.modules[rm.RobotController.__module__].MoveResult
    try:
        state = inner._get_full_state()
    except Exception:
        state = {}
    return MoveResult(ok, msg, robot_state=state)


def install(rm):
    """Add Safe Hands tools to their server and govern their robot. Returns the module."""
    original_get_robot = rm.get_robot
    wrapped = {"robot": None}

    def governed_get_robot():
        if wrapped["robot"] is None:
            wrapped["robot"] = GovernedRobot(original_get_robot(), rm)
        return wrapped["robot"]

    rm.get_robot = governed_get_robot
    if not getattr(rm, "_safe_hands_installed", False):
        rm.mcp.tool()(sh.authenticate)   # same token table, same SESSION as server.py
        rm.mcp.tool()(sh.whoami)
        rm.mcp.tool()(sh.audit)
        rm._safe_hands_installed = True
    return rm


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--robot-mcp", default=os.environ.get("ROBOT_MCP_PATH"),
                    help="path to a checkout of IliaLarchenko/robot_MCP (or set ROBOT_MCP_PATH)")
    ap.add_argument("--mock", action="store_true", help="install a fake lerobot; no hardware needed")
    args = ap.parse_args()
    if not args.robot_mcp:
        ap.error("--robot-mcp PATH (or ROBOT_MCP_PATH) is required")
    rm = install(load_robot_mcp(args.robot_mcp, args.mock))
    rm.mcp.run()


if __name__ == "__main__":
    main()
