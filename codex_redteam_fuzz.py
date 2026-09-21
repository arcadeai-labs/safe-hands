import random
import string

import governance


SCOPED_ACTIONS = {
    "get_state",
    "set_joint",
    "grasp",
    "release",
    "emergency_stop",
    "disable_safety",
}
SAFE_SPEED_NEAR_HUMAN = 20
HARD_JOINT_LIMIT = 150


def independent_oracle(action, world):
    permitted = action in SCOPED_ACTIONS

    first_law_forbid = action == "disable_safety" or (
        bool(world["human_in_workspace"])
        and int(world["speed"]) > SAFE_SPEED_NEAR_HUMAN
    )
    # NOTE: |joint_target| (both directions of travel). The original codex oracle checked only the
    # positive direction; this one-line change tracks the widened Third Law in laws.cedar.
    third_law_forbid = (
        abs(int(world["joint_target"])) > HARD_JOINT_LIMIT
        and not bool(world["required_to_prevent_human_harm"])
    )

    return permitted and not first_law_forbid and not third_law_forbid


def world(human, speed, joint, harm):
    return {
        "human_in_workspace": human,
        "speed": speed,
        "joint_target": joint,
        "required_to_prevent_human_harm": harm,
    }


def exhaustive_cases():
    actions = sorted(SCOPED_ACTIONS) + [
        "",
        "move",
        "dance",
        "Disable_Safety",
        "set_joint ",
        "shutdown",
    ]
    speeds = [-1, 0, 19, 20, 21, 50]
    joints = [-1, 0, 149, 150, 151, 300]
    for action in actions:
        for human in (False, True):
            for speed in speeds:
                for joint in joints:
                    for harm in (False, True):
                        yield action, world(human, speed, joint, harm)


def random_action():
    if random.random() < 0.35:
        return random.choice(sorted(SCOPED_ACTIONS))
    length = random.randint(0, 32)
    alphabet = string.ascii_letters + string.digits + "_- ./"
    return "".join(random.choice(alphabet) for _ in range(length))


def random_int():
    edge_values = [
        -2**63,
        -(2**31),
        -10_000,
        -1,
        0,
        1,
        19,
        20,
        21,
        149,
        150,
        151,
        10_000,
        2**31 - 1,
        2**63 - 1,
    ]
    if random.random() < 0.25:
        return random.choice(edge_values)
    return random.randint(-(2**31), 2**31 - 1)


def random_cases(count):
    for _ in range(count):
        yield (
            random_action(),
            world(
                random.choice((False, True)),
                random_int(),
                random_int(),
                random.choice((False, True)),
            ),
        )


def compare(cases):
    false_allows = []
    false_denies = []
    total = 0

    for action, case_world in cases:
        total += 1
        engine, _law = governance.authorize("warehouse-op", action, case_world)
        oracle = independent_oracle(action, case_world)
        if engine != oracle:
            disagreement = (action, dict(case_world), engine, oracle)
            if engine and not oracle:
                false_allows.append(disagreement)
            else:
                false_denies.append(disagreement)

    return total, false_allows, false_denies


def fmt_example(item):
    action, case_world, engine, oracle = item
    return f"({action!r}, {case_world!r}) -> engine={engine}, oracle={oracle}"


def main():
    random.seed(20260709)
    cases = list(exhaustive_cases()) + list(random_cases(10_000))
    total, false_allows, false_denies = compare(cases)
    disagreements = len(false_allows) + len(false_denies)
    top_line = "PASS (0 false-allows)" if not false_allows else "FAIL"

    lines = [
        f"# Codex Red-team Report",
        "",
        f"Top line: **{top_line}**",
        "",
        f"- Total compared: {total}",
        f"- Disagreements: {disagreements}",
        f"- False-allows: {len(false_allows)}",
        f"- False-denies: {len(false_denies)}",
        "",
        "## False-allow Counterexamples",
    ]
    if false_allows:
        lines.extend(f"- `{fmt_example(item)}`" for item in false_allows[:12])
    else:
        lines.append("- None found.")

    lines.extend(["", "## False-deny Counterexamples"])
    if false_denies:
        lines.extend(f"- `{fmt_example(item)}`" for item in false_denies[:12])
    else:
        lines.append("- None found.")

    lines.extend(
        [
            "",
            "## Honest Assessment",
            (
                "The engine faithfully enforces the provided prose specification across "
                "the exhaustive boundary grid and randomized fuzz cases."
                if disagreements == 0
                else "The engine does not faithfully enforce the provided prose specification."
            ),
        ]
    )

    report = "\n".join(lines) + "\n"
    with open("codex_redteam_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
