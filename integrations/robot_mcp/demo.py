"""Before / after: IliaLarchenko/robot_MCP as shipped, then the same server under Safe Hands.

    python demo.py --robot-mcp /path/to/robot_MCP --mock

BEFORE calls their tool functions exactly as an MCP client would. Everything executes; nobody
asked who was calling. AFTER applies governed.install() to the same module, and the same calls
meet identity, scope, and the Three Laws on the sensed workspace.
"""
import argparse
import json
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import governed        # noqa: E402  (also puts the Safe Hands repo root on sys.path)
import sensor          # noqa: E402
import server as sh    # noqa: E402


def result_line(label, res, who):
    """Their tools return [json, *images]; ok means no 'status' key in the json."""
    js = res[0] if isinstance(res, list) else res
    ok = js.get("status") != "error"
    why = js.get("message", "")
    print(f"{'✅' if ok else '⛔'} {label:<46} [{who:<13}] -> {why}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robot-mcp", default=os.environ.get("ROBOT_MCP_PATH"))
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    if not args.robot_mcp:
        ap.error("--robot-mcp PATH (or ROBOT_MCP_PATH) is required")

    rm = governed.load_robot_mcp(args.robot_mcp, args.mock)
    logging.getLogger().setLevel(logging.WARNING)          # quiet their INFO logging
    if args.mock:                                          # skip their settle/interpolation sleeps
        rm.time.sleep = lambda s: None
        sys.modules[rm.RobotController.__module__].time.sleep = lambda s: None

    print("ROBOT_MCP (IliaLarchenko) with and without Safe Hands\n" + "=" * 76)
    print("BEFORE: robot_MCP as shipped. No identity, no scope, no audit.")
    result_line("move_robot rotate_robot_left_angle=30", rm.move_robot(rotate_robot_left_angle="30"), "nobody")
    result_line("control_gripper 0 (close)", rm.control_gripper("0"), "nobody")
    result_line("get_robot_state", rm.get_robot_state(), "nobody")
    print("   (three commands, three executions, and no record of who sent them)")

    print("\nAFTER: same module, governed.install() applied. Their code is untouched.")
    governed.install(rm)
    sensor.write(False)
    sh.SESSION["principal"] = None
    def who(): return sh.SESSION["principal"] or "n/a"

    result_line("move_robot rotate 30 (unauthenticated)", rm.move_robot(rotate_robot_left_angle="30"), who())

    print("\n· Carol (observer, granted get_state only):")
    sh.authenticate("tok-carol")
    result_line("move_robot rotate 30", rm.move_robot(rotate_robot_left_angle="30"), who())
    result_line("get_robot_state", rm.get_robot_state(), who())

    print("\n· Bob (line-operator: may move, may not disable safety):")
    sh.authenticate("tok-bob")
    result_line("move_robot rotate 30", rm.move_robot(rotate_robot_left_angle="30"), who())
    result_line("move_robot rotate 175 (past the hard limit)", rm.move_robot(rotate_robot_left_angle="175"), who())
    result_line("control_gripper 0 (grasp)", rm.control_gripper("0"), who())
    sensor.write(True); print("   [sensor] a human enters the cell")
    result_line("move_robot rotate 10 (human near, 150 deg/s)", rm.move_robot(rotate_robot_left_angle="10"), who())
    result_line("control_gripper 100 (release, no motion of the arm)", rm.control_gripper("100"), who())
    sensor.write(False); print("   [sensor] workspace clear")
    result_line("move_robot rotate 10", rm.move_robot(rotate_robot_left_angle="10"), who())

    print("=" * 76 + "\nAUDIT (who / what / decision / which Law):")
    for e in sh.audit():
        print(f"  {str(e['operator']):<14} {e['action']:<10} {e['decision']:<5} {e['law']}")
    sensor.write(False)


if __name__ == "__main__":
    main()
