# Safe Hands in front of robot_MCP

[IliaLarchenko/robot_MCP](https://github.com/IliaLarchenko/robot_MCP) (Apache-2.0, pinned here to
commit `5087718`) is the reference "an LLM drives a SO-ARM100 / SO-101 over MCP" server. Four
tools, an agent loop, real hardware. It authenticates nothing, scopes nothing, and keeps no audit
trail: anyone who reaches the server commands the arm.

This directory puts Safe Hands in front of it **with zero edits to their code.** `governed.py`
imports their `mcp_robot_server` as-is, adds `authenticate`, `whoami`, and `audit` to their FastMCP
instance, and replaces their lazy `get_robot()` with a proxy that runs every actuator call through
`governance.authorize` (contextual grant, then the Three Laws on the sensed workspace) before it
reaches their `RobotController`. Their tool names, arguments, and return shape are unchanged. A
refused command comes back as their own `MoveResult(ok=False)` with the refusing Law in `message`.

## Run

```bash
git clone https://github.com/IliaLarchenko/robot_MCP && (cd robot_MCP && git checkout 5087718)

# before / after, no hardware (a fake lerobot is installed in-process)
python demo.py --robot-mcp ./robot_MCP --mock

# their server, governed, no hardware
python governed.py --robot-mcp ./robot_MCP --mock

# their server, governed, real arm (their requirements.txt installed, config.py set up as they document)
python governed.py --robot-mcp ./robot_MCP
```

The sensor is `sensor.py` at the repo root: `python sensor.py enter` / `leave` from another shell.

## Mapping

| robot_MCP call                            | Safe Hands action | context passed to the Laws                                  |
|-------------------------------------------|-------------------|-------------------------------------------------------------|
| `move_robot(...)` (any angle or mm args)  | `set_joint`       | `joint_target` = largest requested angle step (deg); `speed` = their interpolation rate |
| `control_gripper(pct < 50)`               | `grasp`           |                                                             |
| `control_gripper(pct >= 50)`              | `release`         |                                                             |
| `get_robot_state()`                       | `get_state`       |                                                             |
| `get_initial_instructions()`              | ungoverned        | static text, touches no hardware                            |
| camera images                             | passthrough       | a read their tools bundle with state                        |

Identities are the same token table as `server.py`: `tok-carol` (observer), `tok-bob`
(line-operator), `tok-alice` (warehouse-op).

## Limits, stated plainly

- `joint_target` is the **magnitude of the requested step**, not the resulting absolute pose. Their
  controller still enforces its own calibrated range on the absolute target after we allow the step.
- `speed` is their **fixed interpolation rate** (`DEGREES_PER_STEP / STEP_DELAY_SECONDS`, 150 deg/s
  at defaults), used as a proxy because their tools carry no speed argument. It is not a measured
  tip speed. With a human sensed in the cell, any motion at that rate exceeds the collaborative
  threshold and the First Law refuses it.
- Identity is a demo token table. In production the principal comes from the user's OAuth or
  session context, never from anything the model says.
- The fake lerobot (`mock_lerobot.py`) exists so the wrapper can be exercised in CI. It moves no motor.
