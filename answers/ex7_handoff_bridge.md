# Ex7 — Handoff bridge

## Your answer

The handoff bridge sits above the two halves and decides which one runs next.
It runs the loop half until it asks for `handoff_to_structured`, writes the
handoff, calls the structured half with the handoff data, and either completes
the session or builds a retry task from the rejection reason and returns to
the loop.

Session `sess_af1b32b48c57` demonstrates the expected two-round bridge flow.

Round 1 handed `Haymarket Tap` to the structured half for a party of `12`.
Rasa rejected it, and the bridge sent control back to the loop with:

`sorry, we can't accept this booking. reason: party_too_large`

Round 2 used that rejection in the next planner task, searched again, and
handed off `The Royal Oak` for party size `6`. The structured half confirmed
the booking with reference `BK-B7655866`.

The trace shows the expected transitions:

- round 1: `loop` -> `structured`
- round 1: `structured` -> `loop`
- round 2: `loop` -> `structured`
- round 2: `structured` -> `completed`

The forward handoff files were archived under `logs/handoffs/`, leaving no
visible handoff files under `ipc/` at the end.

## Citations

- sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/trace.jsonl
- sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/handoffs/round_1_forward.json
- sessions/examples/ex7-handoff-bridge/sess_af1b32b48c57/logs/handoffs/round_2_forward.json