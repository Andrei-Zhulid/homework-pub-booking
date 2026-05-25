# Ex6 — Rasa structured half

## Your answer

Ex6 is implemented as a real Rasa-backed structured half. The validator
normalises loop-side booking data, the structured half POSTs it to Rasa's
REST webhook as `metadata.booking`, and the response is converted back
into a sovereign-agent `HalfResult`. The Rasa action enforces the
assignment rules: reject `party_size > 8`, reject `deposit_gbp > 300`, and
otherwise set a booking reference.

I ran `make ex6-real` four times against real Rasa on `localhost:5005`
and the action server on `localhost:5055`. The two happy-path runs
completed in sessions `sess_b910824b17e7` and `sess_ee50233a01bf` with
`next_action=complete` and booking reference `BK-7D401E9E`. The successful
output contained this normalised payload:

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
by `Is there anything else I can help you with?`.

The rejection runs exercised both policy branches:
* Session `sess_65d303d93714` used `party_size: 12` and returned
`next_action=escalate` with reason `party_too_large`.
* Session `sess_f1b857fa8773` used `deposit_gbp: 400` and returned
`next_action=escalate` with reason `deposit_too_high`.

The Rasa validation behavior was successfully verified.

## Citations

- terminal output:

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
andrei_zhulid@Mac homework-pub-booking % make ex6-real

✓ Rasa is up at http://localhost:5005
    HTTP 200 — {"version":"3.16.4","minimum_compatible_version":"3.16.0rc2"}
✓ Action server is up at http://localhost:5055
    HTTP 200 — {"status":"ok"}

▶ Running Ex6 scenario...

📂 Session sess_65d303d93714
   dir: <project_directory>/sessions/examples/ex6-rasa-half/sess_65d303d93714
   (tier 2: assuming rasa-actions + rasa-serve are already
    running in two other terminals. If you see a connection
    error below, run `make ex6-help` for the setup recipe.)
   Rasa URL: http://localhost:5005/webhooks/rest/webhook

Structured half outcome: escalate
  summary: booking rejected: party_too_large
  output:  {'status': 'rejected', 'reason': 'party_too_large', 'booking': {'venue_id': 'haymarket_tap', 'date': '2026-04-25', 'time': '19:30', 'party_size': 12, 'deposit_gbp': 200, 'duration_hours': 3, 'catering_tier': 'bar_snacks'}, 'rasa_messages': [{'recipient_id': 'homework-185d7d73', 'text': "Sorry, we can't accept this booking. Reason: party_too_large"}, {'recipient_id': 'homework-185d7d73', 'text': 'Is there anything else I can help you with?'}]}

📂 Session artifacts: <project_directory>/sessions/examples/ex6-rasa-half/sess_65d303d93714
📜 Narrate this run:   make narrate SESSION=sess_65d303d93714
make: *** [ex6-real] Error 1
andrei_zhulid@Mac homework-pub-booking % make ex6-real

✓ Rasa is up at http://localhost:5005
    HTTP 200 — {"version":"3.16.4","minimum_compatible_version":"3.16.0rc2"}
✓ Action server is up at http://localhost:5055
    HTTP 200 — {"status":"ok"}

▶ Running Ex6 scenario...

📂 Session sess_f1b857fa8773
   dir: <project_directory>/sessions/examples/ex6-rasa-half/sess_f1b857fa8773
   (tier 2: assuming rasa-actions + rasa-serve are already
    running in two other terminals. If you see a connection
    error below, run `make ex6-help` for the setup recipe.)
   Rasa URL: http://localhost:5005/webhooks/rest/webhook

Structured half outcome: escalate
  summary: booking rejected: deposit_too_high
  output:  {'status': 'rejected', 'reason': 'deposit_too_high', 'booking': {'venue_id': 'haymarket_tap', 'date': '2026-04-25', 'time': '19:30', 'party_size': 6, 'deposit_gbp': 400, 'duration_hours': 3, 'catering_tier': 'bar_snacks'}, 'rasa_messages': [{'recipient_id': 'homework-185d7d73', 'text': "Sorry, we can't accept this booking. Reason: deposit_too_high"}, {'recipient_id': 'homework-185d7d73', 'text': 'Is there anything else I can help you with?'}]}

📂 Session artifacts: <project_directory>/sessions/examples/ex6-rasa-half/sess_f1b857fa8773
📜 Narrate this run:   make narrate SESSION=sess_f1b857fa8773
make: *** [ex6-real] Error 1
andrei_zhulid@Mac homework-pub-booking % make ex6-real

✓ Rasa is up at http://localhost:5005
    HTTP 200 — {"version":"3.16.4","minimum_compatible_version":"3.16.0rc2"}
✓ Action server is up at http://localhost:5055
    HTTP 200 — {"status":"ok"}

▶ Running Ex6 scenario...

📂 Session sess_ee50233a01bf
   dir: <project_directory>/sessions/examples/ex6-rasa-half/sess_ee50233a01bf
   (tier 2: assuming rasa-actions + rasa-serve are already
    running in two other terminals. If you see a connection
    error below, run `make ex6-help` for the setup recipe.)
   Rasa URL: http://localhost:5005/webhooks/rest/webhook

Structured half outcome: complete
  summary: booking confirmed: BK-7D401E9E
  output:  {'status': 'committed', 'booking': {'venue_id': 'haymarket_tap', 'date': '2026-04-25', 'time': '19:30', 'party_size': 6, 'deposit_gbp': 200, 'duration_hours': 3, 'catering_tier': 'bar_snacks'}, 'booking_reference': 'BK-7D401E9E', 'rasa_messages': [{'recipient_id': 'homework-185d7d73', 'text': 'Booking confirmed. Reference: BK-7D401E9E.'}, {'recipient_id': 'homework-185d7d73', 'text': 'Is there anything else I can help you with?'}]}

📂 Session artifacts: <project_directory>/sessions/examples/ex6-rasa-half/sess_ee50233a01bf
📜 Narrate this run:   make narrate SESSION=sess_ee50233a01bf
```
