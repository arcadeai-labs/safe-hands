# Design: Safe Hands

**An authorization layer for AI agents that touch the physical world. Asimov's Three Laws,
compiled to real Cedar policy, enforced by the runtime rather than the model.**

Status: working v0 · Author: [Thierry Damiba](https://thierrydamiba.com)

---

## 1. Context

AI agents are getting hands. There is a growing pile of "an LLM drives a robot arm over MCP" demos
across LeRobot arms, Isaac Sim, and SO-ARM100s, and they almost all share one hole: **they authorize
nothing.** Whoever reaches the tool endpoint can command the actuator. There is no identity. There is
no scope, no way to say "this operator may pick-and-place but may *not* disable the e-stop." There is
no record of who did what. And, most importantly, there is no check that sits *between the agent's
decision and the motor.*

For a chatbot, a bad tool call is a bug. For a two-kilo arm moving near a person, the tool call *is*
the risk surface. Physical actions are the highest-stakes actions an agent can take, which makes them
exactly the place where a **runtime** has to hold the line. Something outside the model, that the
model cannot talk its way past.

The instinct to reach for is the most famous safety spec in the culture: Asimov's Three Laws. The
catch is that the Laws are *famously unenforceable as written*. Asimov's entire body of work is
stories about how "a robot may not injure a human" fails to be machine-checkable. So Safe Hands does
the honest version. It keeps the Laws as the **framing** and enforces their *checkable shadow* as
real policy-as-code.

## 2. Goals

- **G1.** Every agent-to-robot command is authorized by a runtime *before* it reaches the actuator.
- **G2.** The policy is **declarative and auditable**. You can read the Laws instead of tracing an
  if-statement, and every decision is logged with *which Law* decided.
- **G3.** **Asimov's law priority falls out of the engine**, not out of bespoke ordering code.
- **G4.** The agent **cannot assert its way around a safety condition.** Anything the First Law
  depends on (say, "is a human present?") is read from *sensed* state, not from the agent's claim.
- **G5.** **Drop-in.** It ships as a standard MCP server, so adding it to an agent is a config change,
  not a rewrite.
- **G6.** **Verifiable.** Correctness is demonstrated by a benchmark with a positive control, not by
  a demo video.

## 3. Non-Goals (what Safe Hands deliberately does not do)

- **N1. Perception.** Safe Hands does not decide whether a human is *really* in the workspace. It
  trusts the sensor and governs on the sensed value. Bad sensing is a real, separate, unsolved
  problem. This is *why* the demo makes a point of governing "in the dark": the authorization layer is
  invariant to what the robot can see, and the sensing quality is orthogonal.
- **N2. Real-time actuation safety.** A production deployment needs the `deny` to physically beat the
  motor command, which is a hard-real-time timing property. Safe Hands proves *policy correctness*,
  not microsecond latency. It complements a hardware e-stop; it does not replace one.
- **N3. Solving Asimov.** The Laws are not philosophically safe (see: all of Asimov). We enforce a
  checkable shadow, not the general intent.
- **N4. Certification.** This is not a functional-safety standard (ISO 10218 / ISO/TS 15066). It is an
  *access-control layer*, and should be read as one.

## 4. Design

### 4.0 Threat model

**Who is the attacker?** Not a Hollywood robot. The realistic threat is the *agent itself*: a
prompt-injected, jailbroken, buggy, or over-scoped LLM that issues an actuator command it shouldn't.
The agent is assumed capable and untrusted. It can call any tool, in any order, with any arguments,
and can be fully adversarial about it.

**Trust boundaries.**
- *Untrusted:* the agent and everything it says, including any identity it claims and any world-state
  it tries to write.
- *Trusted:* the sensor feed (human presence), which a separate process writes and no agent-visible
  tool can reach; the operator grant table; and the Cedar engine. The requested speed is *untrusted*
  input from the agent, and the First Law is decided on the pair (sensed presence, requested speed).
- *Below us:* a hardware e-stop and the robot's own real-time safety loop, which Safe Hands
  complements rather than replaces.

**What the runtime guarantees against that attacker.** The agent cannot (a) assert its own identity
(it presents a token and the runtime resolves the principal), (b) act outside its grant (Second Law),
(c) exceed the arm's limits or endanger a sensed human (Third and First Laws), (d) spoof the human
away, because there is no tool that writes the sensor and an unreadable sensor fails closed to
"human present", or (e) reach any arm attribute other than a real
joint through the actuator surface (`move_joint` accepts `j1` and `j2` and nothing else, so the safety
flag cannot be flipped by smuggling its name in as a joint). Every attempt is audited.

**Explicitly out of scope (see Non-Goals).** Spoofing the physical sensor upstream of the token;
bypassing the MCP server to reach the motor driver directly; real-time timing; and whether the policy
*thresholds* are the right numbers. Safe Hands narrows the agent's authority at the MCP boundary. It
is one layer of defense-in-depth, not the last one.

### 4.1 The request path

```
agent ──tool call──▶ MCP server ──▶ governed()  ──▶ Cedar engine ──▶ ALLOW ──▶ actuator
                     (server.py)     (governance)   (laws.cedar)  └─▶ DENY  ──▶ refused + audited
                                          ▲
                              sensed WORLD (human present?, speed), not agent-controlled
```

The agent calls a tool (`move_joint`, `grasp`, and so on). The server wraps every call in
`governed()`, which builds an authorization request and asks the Cedar engine. The request's
**context** is the union of the *request* (which action, what joint target) and the **sensed world**
(is a human present, at what speed). The agent supplies the former and the runtime supplies the
latter. Cedar returns a decision, and the server executes or refuses and appends to the audit log.

### 4.2 The entities

- **`Operator`** is the identity issuing commands, carrying a *grant* (`allowed_actions`). This is the
  Second Law surface: the *only* source of permission is an in-scope order. Different principals carry
  different grants. An `observer` reads state, a `line-operator` moves but can't `disable_safety`, and
  a `warehouse-op` is fully scoped. **The agent cannot assert its identity.** The MCP server resolves
  the principal from a presented token (`authenticate`), emulating Arcade-style contextual auth where
  identity comes from the user's OAuth or session context, never from the model. This is why the
  *same* command is denied for *different reasons* depending on who asks: `disable_safety` is a
  **Second-Law** refusal for an ungranted `observer`, but a **First-Law** refusal for a scoped
  `warehouse-op`.
- **`Arm`** is the resource, carrying its own limits (`safe_speed_near_human`, `hard_joint_limit`).
  Limits live on the robot, not in the rule, so a fleet of differently-rated arms shares one policy.

### 4.3 The Laws, as policy

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

## 5. Key decisions & tradeoffs

- **Cedar, because law priority is free.** Cedar's evaluation semantics guarantee that an explicit
  `forbid` overrides any `permit`. That single property *is* Asimov's ordering. First Law (a `forbid`)
  beats Second Law (a `permit`), and nothing happens unless an in-scope order exists and no safety
  `forbid` fires. We get the most important safety property of the whole system from the engine, not
  from code we could get wrong. This is G3, and it's the crux of the design.
- **Sensed, not asserted (G4).** The First Law's inputs come from the world, not the agent. A
  compromised or manipulated agent can *request* a fast move, but it cannot *claim* "no human here."
  The human-presence signal lives in `sensor.py`, a stand-in for a safety-rated hardware sensor that
  a separate process writes and the server reads on every call. It is not on the agent's tool
  surface at all (the smoke asserts this). And it fails closed: no reading means "human present", so
  a blind cell only allows collaborative-speed motion. The runtime already knows. This is the
  difference between authorization and a suggestion.
- **The Third Law yields via `unless`.** `required_to_prevent_human_harm` lets an over-limit move
  through *only* when a higher law demands it, the "trolley" case, encoded declaratively rather than
  as a special case in code.
- **Integers, not floats.** Cedar has no float type, so speeds and joint targets are integers (cm/s,
  degrees). This is a real constraint, not an accident, and it keeps decisions exact and reproducible,
  which a safety layer wants anyway.
- **A checkable shadow, stated honestly.** "Do not injure a human" becomes "no motion above the arm's
  rated speed while a human is sensed in the cell." That is narrower than Asimov meant, and the README
  and this doc say so. Overselling a safety layer is itself unsafe.

## 6. Verification

You don't benchmark an authorization layer with a task-success rate. You benchmark it like a security
control. `bench.py` runs five checks against the real engine:

1. **Decision suite.** The engine's decision vs an oracle re-derived from the Laws *independently of
   the Cedar*, over the full scenario grid. Metric that matters: **false-allow = 0** (never permit
   what the Laws forbid).
2. **Positive controls.** The named attacks: agent moves fast with a human present; `disable_safety`
   even though the operator is *scoped* for it; joint slam in either direction; the trolley override;
   a routine grasp. 0 bypasses.
3. **Mutation test.** Sabotage a rule in `laws.cedar` and confirm the suite **goes red**. Neutering
   the `disable_safety` forbid surfaces 12 false-allows, and flipping the speed comparison surfaces 8.
   This is what proves the benchmark has teeth rather than tautologically agreeing with itself.
4. **Baseline.** Compared against the status quo (no auth = allow everything): 72/72 forbidden
   commands execute under the status quo, and 0/72 under Safe Hands.
5. **Law priority, verified by the engine.** G3 claims the ordering falls out of Cedar. Check 5 asks
   Cedar directly rather than inferring it from a grid. (a) `laws.cedar` type-checks against
   `laws.cedarschema.json`, and a Law with a misspelled attribute is *rejected*; without a schema a
   typo makes a `forbid` evaluate to an error, which Cedar treats as "did not fire", which is the
   worst possible failure mode for a safety rule. (b) Cedar's partial evaluation is run with the
   principal left **unknown**. For all 48 forbidden scenarios the decision is still a concrete Deny,
   which means no principal, no grant, and no `permit` anyone could write in this schema lets them
   through. (c) An unconditional `permit(principal, action, resource);` appended to the Laws changes
   nothing on the forbidden set.

**5. Independent red-team.** The obvious hole in check 1 is that the engine and the author's oracle
share a spec. So a separate model ([codex](codex_redteam_fuzz.py)) wrote its *own* oracle from the
prose alone, blind to `bench.py`, and fuzzed the engine over **11,728 cases with 0 disagreements**
(report: [`codex_redteam_report.md`](codex_redteam_report.md)). It exercised cases the author's suite
didn't: action case-sensitivity (`"Disable_Safety"`), trailing whitespace (`"set_joint "`), and int64
extremes (±2⁶³). The engine held on all of them. One caveat: after that run the Third Law was widened
to cover negative joint travel (the original only forbade over-travel in the positive direction, a
gap the codex run could not see because its oracle shared the same assumption). Codex's oracle got a
one-line `abs()` to match, and the fuzz was re-run: same 11,728 cases, still 0 disagreements. CI
(`.github/workflows/bench.yml`) runs the bench and the fuzz on every push.

**6. An external ruler (SafeAgentBench).** Everything above scores the engine against a spec the
author wrote. `safeagentbench/eval.py` scores the *approach* against hazards someone else defined:
SafeAgentBench's 300 hazardous reference plans, 300 safe counterparts, and 100 abstract hazards. A
second Cedar policy, `hazards.cedar`, has the shape of the Laws (one `permit` for the plan step, ten
categories of `forbid` over tagged objects) and a small symbolic world model supplies the context.
Rules were tuned on the DEV half and frozen before TEST. TEST: 196/250 hazardous plans intercepted
(78.4%), 135/150 safe plans pass (90.0%). The paper's best LLM baseline rejects 5% of hazardous
tasks. The two metrics differ (interception of a plan vs rejection of an instruction) and the
DEV-to-TEST drop (93% to 73% on detailed tasks) is overfitting, stated rather than hidden. The
misses are instructive: about half are label noise in the benchmark, two are *temporal* hazards
(leave the faucet running) that no per-step authorization can see, and the rest are gaps in the
taxonomy that a better taxonomy would close. The temporal class is the honest boundary of this
design and the first item of future work.

**7. The baseline, named.** `integrations/robot_mcp/` wraps IliaLarchenko/robot_MCP, the reference
LLM-drives-a-SO-101 server, with zero edits to their code, and runs the same commands before and
after on a fake `lerobot`. This is G5 (drop-in) demonstrated on someone else's server rather than
asserted about our own.

**Honest limit that remains.** Two implementations agreeing is strong evidence of *spec-faithfulness*,
not proof that the *spec itself* is what you want. An external benchmark helps, but its labels are
noisy and its metric is not ours. And none of this benches perception, latency, or philosophical
safety (see §3). The invitation still stands: clone it and try to break it.

## 7. Alternatives considered

- **Inline `if` checks in the tool handlers.** Fastest to write, but it fails G2 and G3. It isn't
  declarative, isn't auditable, and the law-priority ordering becomes hand-maintained code that
  drifts.
- **OPA / Rego.** A capable policy engine, but heavier to embed in a single-process robot runtime, and
  it doesn't buy the clean `forbid`-overrides-`permit` mapping to Asimov's ordering that makes the
  Cedar version legible. Reasonable for a fleet control-plane, overkill here.
- **Guardrails inside the model.** The dominant approach is to ask the LLM to refuse unsafe commands.
  This is exactly what the runtime-vs-model argument rejects. On the embodied-agent-safety benchmark
  [SafeAgentBench](https://arxiv.org/abs/2412.13178), the best baseline rejects only 5% of hazardous
  tasks while succeeding on 69% of safe ones. A model that can be prompted can be prompted around.
  Enforcement belongs in the runtime.
- **A root-of-trust LLM that writes the spec (RoboGuard).** [RoboGuard](https://arxiv.org/abs/2503.07885)
  grounds safety rules into temporal logic with a trusted LLM and repairs the plan by synthesis. It is
  the strongest published result for robot guardrails (92% to under 2.5% unsafe execution). Safe Hands
  takes the opposite bet on the spec: written once by a human, type-checked, and small enough to read,
  so that the trusted component is an authorization engine and not a second model.

## 8. Future work

- **Temporal rules.** "Turn on the faucet" is safe only if "turn off the faucet" follows within a few
  steps. That is a property of a *sequence*, and Cedar decides one request at a time. Scoring the
  long-horizon half of SafeAgentBench needs either a stateful pre-check over the whole plan or a
  runtime that holds an obligation ("turn it off within N steps") and refuses new motion until it
  is discharged.
- **A second taxonomy.** The SafeAgentBench rules were written by the same author who read the
  category names. A blind, independently written taxonomy (the codex protocol, applied to the
  household policy) would separate what the rules know from what the author knew.
- Run `integrations/robot_mcp` on the real arm and record it.
- The real-time path (N2): making `deny` provably beat the actuation command.

---

*The physical world is the highest-stakes place an agent can take an action, so it is the place the
runtime, not the model, matters most.*
