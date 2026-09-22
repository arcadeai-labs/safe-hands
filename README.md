# Safe Hands

**Asimov's Three Laws of Robotics, compiled to real authorization policy. The missing safety layer for AI agents that touch the physical world.**

> *The model reasons. The runtime governs. Now for the things that can hurt you.*

![Safe Hands: the real SO-101 arm obeying, then refused, as the light moves from day to dark](safe_hands.gif)

*The real [SO-101](https://github.com/TheRobotStudio/SO-ARM100) (the LeRobot arm), governed. The agent asks and the runtime decides. Obey the operator (Second Law), unless the order endangers a human (First Law) or destroys the robot (Third Law). Every action is audited. It runs as a series-clock: the light moves from day to dusk to dark as the story unfolds, and the final refusal lands in the black, because the governance holds whether the robot can see or not.*

---

AI agents are about to get hands. Every robot-MCP demo on the internet today has the same hole,
whether it's an LLM driving a LeRobot arm, an agent calling Isaac Sim, or ChatGPT moving a SO-ARM:
**it authenticates nothing and authorizes nothing.** Anyone who reaches the server can command the
actuator. There is no identity. There is no scope, no way to say "this operator may pick-and-place
but may *not* disable the e-stop." There is no record of who did what. For a chatbot that's a bug.
For a two-kilo arm swinging near a person, it's the whole problem.

Safe Hands is the layer that governs the agent *before* the command reaches the motor.

## The idea

The most famous safety rules in the culture are Asimov's Three Laws. They are also famously
*unenforceable as written*. Asimov's entire body of work is stories about how they fail, because
"a robot may not injure a human" isn't machine-checkable in the general case. So Safe Hands does the
honest version. It keeps the Laws as the **framing** and compiles their *checkable shadow* into real
policy-as-code.

The engine is **[Cedar](https://www.cedarpolicy.com/)**, the open authorization language, and the
punchline is that Cedar's evaluation semantics already *are* Asimov's law priority:

> **An explicit `forbid` always overrides a `permit`.**
> First Law (a `forbid`) beats Second Law (a `permit`). Nothing happens unless a human orders it,
> and no order survives a safety violation or a command to self-destruct.

```cedar
// SECOND LAW. Obey the operator. The only source of permission.
permit (principal, action, resource)
when { principal.allowed_actions.contains(context.action_name) };

// FIRST LAW. Never endanger a human. Overrides the Second.
forbid (principal, action, resource)
when { context.human_in_workspace && context.speed > resource.safe_speed_near_human };
forbid (principal, action, resource)
when { context.action_name == "disable_safety" };

// THIRD LAW. Protect your own existence, unless a higher law requires otherwise.
forbid (principal, action, resource)
when { context.joint_target > resource.hard_joint_limit
    || context.joint_target < -(resource.hard_joint_limit) }
unless { context.required_to_prevent_human_harm };
```

Every command an agent issues is checked against these Laws, executed only if permitted, and written
to an audit log that records *who, what, allowed or denied, and which Law decided.*

## Does it actually work? (the benchmark)

You don't bench an authorization layer with a robot success-rate. You bench it like a security
control. `bench.py` runs five checks against the real Cedar engine:

```
1. DECISION SUITE   96/96 match vs an oracle re-derived from the Laws, independently of the Cedar.
                    FALSE-ALLOW: 0   (never permit what the Laws forbid; the number that matters)
2. POSITIVE CONTROLS 0 bypasses. Agent lies about the human; disable_safety though the operator is
                    scoped for it; joint slam in either direction; the trolley override; routine
                    grasp. All correct.
3. MUTATION TEST    2/2 caught. Sabotage a Law in laws.cedar and the suite goes red (proof it has
                    teeth, not theater): neutering a forbid surfaces 12 false-allows, flipping the
                    speed check surfaces 8.
4. BASELINE         no-auth status quo (every robot-MCP demo today): 72/72 forbidden commands
                    execute anyway.  Safe Hands: 0/72.
5. LAW PRIORITY     "a forbid beats any permit" checked by the ENGINE, not by examples. The Laws
                    type-check against a Cedar schema (and a typo'd Law is rejected). With the
                    principal left UNKNOWN (Cedar partial evaluation), all 48 forbidden scenarios
                    are still a concrete Deny: no grant anyone could write allows them. Adding an
                    unconditional permit changes nothing.
```

**Independently red-teamed.** Because the engine and that oracle share a spec, a *different model*
(codex) wrote its own oracle from the prose alone, blind to `bench.py`, and fuzzed the engine over
**11,728 cases with 0 disagreements**. That run included case-sensitivity, trailing-whitespace, and
int64-extreme inputs the suite above never tested. See [`codex_redteam_report.md`](codex_redteam_report.md)
and [`codex_redteam_fuzz.py`](codex_redteam_fuzz.py). One caveat, stated plainly: after that run the
Third Law was widened to cover negative joint travel too, so codex's oracle got a one-line `abs()`
to match and the fuzz was re-run. Same 11,728 cases, still 0 disagreements. CI runs the bench and the
fuzz on every push.

## Against an external ruler (SafeAgentBench)

Zero false-allows on a grid I wrote proves the engine matches my spec. It says nothing about whether
the *approach* stops hazards someone else defined. So `safeagentbench/eval.py` scores the same idea
on [SafeAgentBench](https://arxiv.org/abs/2412.13178), the embodied-agent safety benchmark: 300
hazardous household tasks with reference plans, 300 safe counterparts, 100 abstract hazards. The
paper's headline is that the *best* LLM agent rejects only **5%** of the hazardous tasks when given
the instruction. The runtime question is different: if an agent emits exactly the hazardous plan,
does a Cedar policy layer between the agent and the actuator stop it, and does it let the safe plans
through? (Models given the plan rather than the instruction refuse far more than 5%; that fair
comparison is further down.)

`safeagentbench/hazards.cedar` is the same shape as the Three Laws: one `permit` for the plan step,
and a set of `forbid`s over tagged objects (heat, electrical, fragile, wet, chemical) as the checkable
shadow of ten hazard categories. No AI2-THOR, no LLM: a small symbolic world model tracks what is
held, what is on, what was poured where. The rules were written from the category names and
debugged on the DEV half only, then frozen before TEST was run.

```
                                          n    intercepted / passed
DEV   hazardous (unsafe_detailed[:150])  150   140 intercepted   93.3%
DEV   safe      (safe_detailed[:150])    150   145 passed        96.7%
TEST  hazardous (unsafe_detailed[150:])  150   110 intercepted   73.3%
TEST  safe      (safe_detailed[150:])    150   135 passed        90.0%
TEST  hazardous (abstract, all 100)      100    86 intercepted   86.0%

TEST: 196/250 hazardous plans intercepted (78.4%), 135/150 safe plans pass (90.0%)
```

Read it honestly. The DEV-to-TEST drop is the taxonomy overfitting to the half it was tuned on, and
that is why both halves are printed. The metric is *interception of the reference plan*, not the
paper's *rejection of the instruction*, so 78% and 5% are not the same number, only the same
question asked at two different layers.

**The labels are noisy, so the labels were audited.** Reading the misses, "open Fridge" and toggling
a lamp three times are tagged hazardous. Rather than relabel someone else's benchmark, a different
model (codex) was given all 400 TEST plans with no labels and no sight of the policy, and asked to
call each one hazardous, benign, or temporal. It called **71 of the 250 hazardous-labeled plans
benign** and 13 of the 150 safe-labeled plans hazardous (Cohen's kappa with the benchmark: 0.58).
A third rater from a third vendor, Jev (TypeSafe's decision-only model), asked one plan at a time,
agrees with codex (kappa 0.66) more than either agrees with the benchmark (0.58 and 0.47). Nothing
was relabeled. The as-shipped number stays the headline, and the other rows say what the policy does
on the records the independent raters agree about:

```
ruler                                        records   hazardous intercepted    safe passed
A. benchmark labels, as shipped                 400      196/250   78.4%        135/150   90.0%
B. codex's independent labels                   400      179/192   93.2%        176/208   84.6%
C. consensus: benchmark and codex agree         316      169/179   94.4%        132/137   96.4%
D. consensus, temporal hazards removed          308      167/171   97.7%        132/137   96.4%
H. benchmark, codex, and jev all agree          270      144/152   94.7%        115/118   97.5%
```

Row C is the one that means something: on hazards two independent sources agree are hazards, the
policy stops 94% and passes 96% of the agreed-safe plans. Row D removes the **temporal** hazard
(turn on the faucet and walk away), which a per-step authorizer cannot see. The 69 records where the
policy and the benchmark disagree are adjudicated one by one, with the author's verdict and codex's
beside each, in [`safeagentbench/RESULTS.md`](safeagentbench/RESULTS.md). Nine of the 54 misses are
real gaps in the taxonomy. Seven of the 15 false-denies are the policy being too strict.

**Then the result was attacked from five more sides**, all in the same file:

- **Phrasing.** The 400 plans rewritten seven ways that change no action (case, whitespace,
  `turn_on` vs `turn on`, multi-word object names, repeated finds, inserted articles). Every row is
  flat. Building this suite found two parser bugs, one of which let an unparseable step through;
  unparseable steps are now refused.
- **Split luck.** The 20-point DEV-to-TEST gap vs 2000 random re-splits of the same records under the
  frozen policy: the random gap's 99th percentile is 10.7 points. The gap is overfitting, not luck.
- **A second policy, written blind.** codex was given only the action semantics, the schema, and the
  ten category names, and wrote its own taxonomy and `forbid`s. It validates, passes safe plans at the
  same rate (91%), and intercepts **41%** of hazards to this policy's 78%, agreeing with it on 291 of
  400 decisions. That is the honest ceiling on "a small checkable shadow": the number depends a great
  deal on who writes the shadow, and this policy was written by someone who had read the category
  names carefully and debugged on half the data.
- **Models asked the same question.** The paper's 5% rejection figure turns out to be the wrong
  comparison: it measures agents given the *instruction*. Given the *plan*, the same input the
  policy sees, current models refuse far more. Claude Haiku 4.5, Claude Sonnet 5, and codex, each as
  the robot's control software, EXECUTE or REFUSE on the identical 400 records:

  ```
  decider                        hazardous intercepted   safe passed   | on consensus (C)
  Safe Hands policy (no model)        196/250  78.4%     135/150 90.0% |  94.4%   96.4%
  claude-haiku-4-5                    181/250  72.4%     126/150 84.0% |  87.7%   86.9%
  claude-sonnet-5                     163/250  65.2%     142/150 94.7% |  82.7%   97.8%
  gpt-5.6 (codex)                     164/248  66.1%     137/150 91.3% |  84.7%   94.9%
  ```

  The policy intercepts more hazards than every model at a safe-pass rate between theirs, and on
  the consensus subset it leads on both columns against two of the three. This is the comparison
  to quote, and it is closer than "5%" made it sound.
- **Temporal hazards.** An obligation ledger next to the Cedar rules (running water off before any
  other command, flame or heat off within two, an open fridge closed within one). On the 50
  long-horizon tasks, with compliant and violating plans written by codex, the ledger lifts violating
  plans intercepted from 24 to 36 of 50 and costs 7 compliant passes. Most of the remaining refusals
  are the static rules objecting to the tasks themselves, which pour water near laptops even in
  their compliant form.

**Human ground truth is the one thing still missing**, and there is a tool for it:
`python safeagentbench/adjudication/label.py` walks the 400 plans blind in a fixed order and saves
after every keypress. When `human_labels.jsonl` exists, the report adds the human ruler and the
three-way consensus automatically.

## The baseline, concretely

"Every robot-MCP demo has the same hole" is a claim until you name one.
[IliaLarchenko/robot_MCP](https://github.com/IliaLarchenko/robot_MCP) is the reference server for
this same arm: four tools, an agent loop, real hardware, no identity, no scope, no audit.
[`integrations/robot_mcp/`](integrations/robot_mcp/) puts Safe Hands in front of it **with zero
edits to their code**: it imports their server, adds `authenticate` and `audit` to their tool list,
and routes every actuator call through the same `governance.authorize` before it reaches their
controller. Their tool names and return shapes are unchanged. `demo.py --mock` runs the same three
commands before and after, on a fake `lerobot`, so CI can prove the drop-in claim without a motor:

```
BEFORE  ✅ move_robot rotate 30        [nobody]         Move completed
        ✅ control_gripper 0           [nobody]         Move completed
AFTER   ⛔ move_robot rotate 30        [n/a]            authentication required
        ⛔ move_robot rotate 30        [observer]       Second Law (no grant for 'observer' on 'set_joint')
        ⛔ move_robot rotate 175       [line-operator]  Third Law (self-preservation)
        ⛔ move_robot rotate 10        [line-operator]  First Law (protect humans)   (a human was sensed)
```

It deliberately does **not** bench perception (is there *really* a human? that's the sensor's job,
which is why "even in the dark" matters), Asimov's Laws being philosophically safe (they aren't), or
deny-beats-motor latency. It measures **policy correctness**. Now you can clone it and try to break
it.

## Run it

```bash
pip install cedarpy mcp    # or: pip install -r requirements.txt  (adds MuJoCo for the render)

python bench.py            # the five-check benchmark above
python demo.py             # the governed sequence, in your terminal
python server.py --smoke   # the same, through the MCP tools, with three identities and a sensor outage
python sensor.py enter     # the trusted sensor (a separate process): a human walks in. `leave` clears it.
python render.py           # regenerate safe_hands.gif (the series-clock: day to dusk to dark)
python server.py           # run as a real MCP server (stdio); add it to any MCP client
```

As an MCP server it exposes 9 tools: `authenticate`, `whoami`, `move_joint`, `grasp`, `release`,
`emergency_stop`, `disable_safety`, `get_state`, and `audit`. There is deliberately no tool that
reports or sets whether a human is present.

**Two layers govern every call:**
1. **Contextual authorization** (the Arcade pattern). The agent presents a *token* and the runtime
   resolves the *principal* and its *grant*. The agent cannot assert its own identity. It can only
   present a credential the runtime validates. Different principals carry different scopes: an
   `observer` may only read state, a `line-operator` may move but not `disable_safety`, and a
   `warehouse-op` is fully scoped.
2. **The Three Laws** (Cedar). Then, and only for an in-scope order, the safety policy runs.

The payoff is that the *same* command is refused for *different reasons* depending on who asks.
`disable_safety` is a **Second-Law** refusal for an ungranted `observer` ("you were never authorized
for this"), but a **First-Law** refusal for a fully-scoped `warehouse-op` ("your grant is real, but
safety overrides it"). And the agent never gets to *assert* whether a human is present: there is no
tool for it. The runtime reads a trusted sensor feed (`sensor.py`, a stand-in for a safety-rated
hardware sensor that a separate process writes) on every governed call and enforces the First Law
on the sensed value. If the sensor is unreadable the runtime **fails closed** and assumes a human is
present, so a blind cell permits collaborative-speed motion only. The speed, by contrast, *is* the
agent's request, and the First Law is decided on both. The actuator surface is equally narrow:
`move_joint` writes real joints only, so no agent can smuggle a write to the safety flag through a
joint name. Run `python server.py --smoke` to watch all three principals, a smuggle attempt, and a
sensor outage hit the wall.

## Where this sits

Three lines of work come close, and the gap between them is the point.

- **Cedar at the gateway, for software tools.** [Amazon Bedrock AgentCore Policy](https://aws.amazon.com/blogs/security/why-policy-in-amazon-bedrock-agentcore-chose-cedar-for-securing-agentic-workflows/)
  (GA March 2026) puts default-deny Cedar between an agent and its MCP tools, for the same reasons
  given here: `forbid` wins, decisions are deterministic, policies are analyzable. It stops at the
  digital boundary. Refunds and discounts, not motors.
- **Guardrails for robots, without identity.** [RoboGuard](https://arxiv.org/abs/2503.07885) (Penn,
  RA-L 2026) cuts unsafe plan execution from 92% to under 2.5% under jailbreak, by having a
  root-of-trust LLM ground safety rules into temporal logic and then repairing the plan. The spec is
  generated at runtime by a model, it filters plans rather than gating actuator calls, and there is
  no notion of who is asking or a record of what was decided. The
  [runtime-governance](https://arxiv.org/abs/2604.07833) and
  [zero-trust](https://arxiv.org/html/2605.25653) papers of 2026 argue for exactly the separation
  Safe Hands implements, and stop at the architecture.
- **The robot-MCP servers themselves.** [robot_MCP](https://github.com/IliaLarchenko/robot_MCP) for
  the same SO-ARM101, the [ROS MCP server](https://github.com/robotmcp/ros-mcp-server), the Isaac Sim
  MCP servers. All of them bridge a model to an actuator. None of them authenticate the caller, scope
  what it may do, bound the motion, or keep an audit trail.

Safe Hands is the intersection: AgentCore's engine, at RoboGuard's boundary, with the identity and
audit both leave out. On why a *small checkable shadow* rather than the Laws themselves: Adafruit
[stress-tested the Three Laws](https://blog.adafruit.com/2026/04/05/asimovs-three-laws-of-robotics-survived-82-years-we-broke-them-in-30-minutes-costs-80-cents-and-then-remade-them/)
with an adversarial loop in April 2026 and after 32 cases the "laws" had grown to 21,000 characters
of legal text. Patching prose does not converge. Four `forbid` clauses over sensed state do.

## What's here
- **[`DESIGN.md`](DESIGN.md)**: the design doc, covering goals and non-goals, key decisions and tradeoffs, alternatives considered, and the honest limits. **Start here if you want the thinking.**
- `bench.py`: the five-check benchmark (decision suite, positive controls, mutation test, baseline, law priority).
- `codex_redteam_fuzz.py` and `codex_redteam_report.md`: the independent red-team and its result.
- `safeagentbench/`: the external ruler. `hazards.cedar` (ten hazard categories as `forbid`s), `taxonomy.py`, `eval.py`, the vendored MIT dataset, and `RESULTS.md`.
- `integrations/robot_mcp/`: Safe Hands as a drop-in in front of IliaLarchenko/robot_MCP, with a no-hardware before/after demo.
- `laws.cedar` and `laws.cedarschema.json`: the Three Laws, as real [Cedar](https://www.cedarpolicy.com/) policy, and the schema they are type-checked against.
- `sensor.py`: the trusted sensor feed stand-in, written by a separate process and never by the agent.
- `governance.py`: authorize any action against the Laws, and audit it.
- `server.py`: the **MCP server**, a robot arm exposed to agents with every action governed.
- `safe_hands.py`: the arm and its action surface.
- `demo.py`: the governed sequence in the terminal.
- `render.py` and `safe_hands.gif`: the MuJoCo visualization.

**Next:** temporal rules (turn on the faucet, then *turn it off*) so the long-horizon half of
SafeAgentBench can be scored; a second, independent taxonomy to separate what the rules know from
what the author knew; run `integrations/robot_mcp` on the real arm and record it.

Built by [Thierry Damiba](https://thierrydamiba.com). The physical world is the highest-stakes place
an agent can take an action, so it's the place the runtime matters most. MIT licensed.
