# Ex6 — Rasa structured half

## Your answer

Ex6 is implemented as a real Rasa-backed structured half. The Python
validator normalises the loop-side booking dictionary before the HTTP
handoff: `Haymarket Tap` becomes `haymarket_tap`, `25th April 2026`
becomes `2026-04-25`, `7:30pm` becomes `19:30`, party size is converted
to an integer, and `£200` becomes `deposit_gbp: 200`. The structured half
then POSTs the Rasa REST message to `/webhooks/rest/webhook` with the
normalised booking in `metadata.booking`, parses Rasa's response messages,
and converts them back into a `HalfResult`.

The Rasa action server contains the strict booking policy from the
assignment. `ActionValidateBooking` reads `metadata.booking`, sets the
Rasa slots, rejects bookings where `party_size > 8` with
`party_too_large`, rejects bookings where `deposit_gbp > 300` with
`deposit_too_high`, and otherwise sets a deterministic booking reference.
The flow calls that validation action, branches on `validation_error`, and
utters either the confirmed or rejected response.

The real Rasa path with `make ex6-real`. The preflight checks showed
Rasa running on `localhost:5005` and the action server running on
`localhost:5055`, then the scenario completed successfully in session
`sess_b910824b17e7`. The structured half returned `next_action=complete`
with summary `booking confirmed: BK-7D401E9E`. The output contained the
normalised booking payload:

```python
{
    "venue_id": "haymarket_tap",
    "date": "2026-04-25",
    "time": "19:30",
    "party_size": 6,
    "deposit_gbp": 200,
    "duration_hours": 3,
    "catering_tier": "bar_snacks",
}
```

Rasa responded with `Booking confirmed. Reference: BK-7D401E9E.` followed
by its normal follow-up message, `Is there anything else I can help you
with?`. This confirms the real HTTP route from the structured half into
Rasa, through the custom validation action, and back into the sovereign
agent `HalfResult` is working for the valid booking case.


## Citations

- starter/rasa_half/validator.py — normalise_booking_payload + helpers
- starter/rasa_half/structured_half.py — RasaStructuredHalf.run + mock server
- rasa_project/actions/actions.py - Rasa custom actions
- rasa_project/data/flows.yml - Rasa flows
- terminal output

```terminaloutput
make ex6-real

✓ Rasa is up at http://localhost:5005
    HTTP 200 — {"version":"3.16.4","minimum_compatible_version":"3.16.0rc2"}
✓ Action server is up at http://localhost:5055
    HTTP 200 — {"status":"ok"}

▶ Running Ex6 scenario...

📂 Session sess_b910824b17e7
   dir: <project_directory>/sessions/examples/ex6-rasa-half/sess_b910824b17e7
   (tier 2: assuming rasa-actions + rasa-serve are already
    running in two other terminals. If you see a connection
    error below, run `make ex6-help` for the setup recipe.)
   Rasa URL: http://localhost:5005/webhooks/rest/webhook

Structured half outcome: complete
  summary: booking confirmed: BK-7D401E9E
  output:  {'status': 'committed', 'booking': {'venue_id': 'haymarket_tap', 'date': '2026-04-25', 'time': '19:30', 'party_size': 6, 'deposit_gbp': 200, 'duration_hours': 3, 'catering_tier': 'bar_snacks'}, 'booking_reference': 'BK-7D401E9E', 'rasa_messages': [{'recipient_id': 'homework-185d7d73', 'text': 'Booking confirmed. Reference: BK-7D401E9E.'}, {'recipient_id': 'homework-185d7d73', 'text': 'Is there anything else I can help you with?'}]}

📂 Session artifacts: <project_directory>/sessions/examples/ex6-rasa-half/sess_b910824b17e7
📜 Narrate this run:   make narrate SESSION=sess_b910824b17e7
```
