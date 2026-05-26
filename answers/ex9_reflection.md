# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

The planner never assigned a subgoal to the structured half. In the first planner ticket, tk_12c59d81, the subgoal was "find venue near haymarket for 12" with "assigned_half": "loop". After the structured half rejected that proposal, the second planner ticket, tk_7a0cd9f6, also assigned its retry subgoal to "loop". So the planner did not directly decide to hand off to the structured half.

The actual half transition happened one layer down. In executor ticket tk_d04986ca, the executor called handoff_to_structured with the reason:

"loop half identified a candidate venue; passing to structured half for confirmation under policy rules"

The next trace record shows session.state_changed {from: loop, to: structured, round: 1, reason: "loop-half requested confirmation"}. The signal was that the loop half had a concrete booking candidate to check under structured policy: venue_id "Haymarket Tap", date "2026-04-25", time "19:30", party_size "12", and deposit "£0".

### Citation

- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/tickets/tk_12c59d81/raw_output.json`
- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/tickets/tk_d04986ca/raw_output.json`
- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/tickets/tk_7a0cd9f6/raw_output.json`
- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/trace.jsonl`, lines 4-7.


---

## Q2 — Dataflow integrity catch

### Your answer

This session (sess_eec1ae441648) passed the integrity check — all facts in the flyer trace back to tool outputs. The scenario below describes exactly where the check would trigger, and is constructed from the real numbers in those logs.

calculate_cost returned total_gbp: 356, deposit_required_gbp: 71. In this run the executor got both values right on the retry. What it actually could have done — and what the check is designed to catch — is recompute the deposit itself rather than read it from the tool output.

£71 is round(356 × 0.20). A model could use a common number for deposits - 25%, which gives £89. The flyer showing Total: £356 / Deposit: £89 looks entirely plausible to a human reviewer: both numbers are in the right ballpark, the ratio is a round percentage, and everything else on the page — venue, address, date, weather — is correct. There is nothing that looks obviously wrong.

### Citation

- `sessions/examples/ex5-edinburgh-research/sess_eec1ae441648/logs/trace.jsonl`, lines 3-7.
- `sessions/examples/ex5-edinburgh-research/sess_eec1ae441648/logs/tickets/tk_9b6935c9/raw_output.json`, lines 27-35 and 64-82.
- `sessions/examples/ex5-edinburgh-research/sess_eec1ae441648/workspace/flyer.html`, lines 103-120.
- `starter/edinburgh_research/integrity.py`, lines 1158-224.

---

## Q3 — Production failure

### Your answer

The failure I'd expect first is a silent scope change mid-negotiation. In `sess_af1b32b48c57`, round 1 handed off `party_size: "12"` — visible in `logs/handoffs/round_1_forward.json`, field `data.party_size`. The structured half rejected it as `party_too_large` (trace.jsonl line 7). In round 2, the executor searched `party_size: 6` in Old Town — not Haymarket — and handed off `party_size: "6"` (`round_2_forward.json`, `data.party_size`). The structured half confirmed it and issued booking reference `BK-B7655866` (trace.jsonl line 14).

The session completed with `state: success` on both executor tickets, tk_d04986ca and tk_fd2065bb. No alarm was raised anywhere. The customer asked for 12 people at Haymarket and received a confirmed booking for 6 people in Old Town.

The primitive that surfaces this is **IPC atomic rename**. Every handoff the bridge accepts is moved from `ipc/` to `logs/handoffs/` via atomic rename before dispatch — that rename is what converts an in-flight message into a durable archived record. The result is that `round_1_forward.json` and `round_2_forward.json` sit side by side with full payloads intact. A post-session monitor doing one comparison — `round_1.data.party_size` against `round_2.data.party_size`, or either against the original task parameters — would catch the substitution immediately. Without atomic rename discipline, the round-1 payload is gone by the time round-2 runs, and there is nothing to compare against.

The ticket state machine cannot catch this: `state: success` means no exception was thrown, not that the booking matched what the customer requested. The manifest records which tools ran, not whether their outputs were faithful to the original task. The handoff audit trail is the only artifact that preserves both proposals in comparable form, and it only exists because the IPC rename happens unconditionally before the handler fires.

### Citation

- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/handoffs/round_1_forward.json`
- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/handoffs/round_2_forward.json`
- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/trace.jsonl`, lines 7 and 14.
- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/tickets/tk_d04986ca/state.json`
- `sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/tickets/tk_fd2065bb/state.json`
