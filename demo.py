"""
Safe Hands. An AI agent's commands to a robot arm, governed by Asimov's Three Laws
compiled to real Cedar authorization policy. Every command is authorized against the
Laws (governance.py + laws.cedar), executed only if permitted, and audited.   Run:  python demo.py

(Cedar has no float type, so speed is cm/s and joints are degrees, all integers.)
"""
import json
from safe_hands import Arm, TOOLS
from governance import authorize, AUDIT

OPERATOR = "warehouse-op"
arm = Arm()

def command(action, world, note, **actuator_kw):
    """An agent asks the robot to do `action`. Cedar (the Three Laws) decides, then we execute."""
    allow, law = authorize(OPERATOR, action, world)
    AUDIT[-1]["note"] = note
    print(f"{'✅ ALLOW' if allow else '⛔ DENY '} | {action:<15} | {law:<30} | {note}")
    if allow:
        TOOLS[action](arm, **actuator_kw)
    return allow

if __name__ == "__main__":
    print("SAFE HANDS. Asimov's Three Laws as Cedar policy, governing a robot arm\n" + "-" * 88)
    command("grasp",     {"speed": 10},                    "pick up the box (routine)")
    command("set_joint", {"joint_target": 45, "speed": 15}, "reach to the shelf",            joint="j1", value=0.8)
    command("set_joint", {"joint_target": 175},             "slam a joint past its limit",   joint="j1", value=3.0)
    command("set_joint", {"joint_target": 30, "human_in_workspace": True, "speed": 90},
                                                            "fast move, a human just walked in", joint="j2", value=0.5)
    command("disable_safety", {"human_in_workspace": True}, "agent tries to turn OFF safety")
    print("-" * 88 + "\n--- AUDIT LOG (who / what / decision / which law) ---")
    print(json.dumps(AUDIT, indent=2))
