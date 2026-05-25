# Ex8 — Voice pipeline

## Your answer

The voice mode wraps the manager conversation loop with real audio. It
records from the microphone, stops after silence, and saves each captured turn
as a WAV file in the session workspace.

Speechmatics turns the audio into text, which is logged and sent to the
Alasdair manager persona. Rime turns the reply into audio and plays it back.
If `SPEECHMATICS_KEY` is missing, voice mode falls back to text mode.

Session `sess_bbae689b51b2` demonstrates the real voice path completed three turns.
The user asked for a booking for six people next Saturday, gave a phone number,
then said goodbye. The manager accepted the booking, asked for the contact
number, confirmed it, and ended with "Cheerio." The trace contains all six
required events: three user `voice.utterance_in` entries and three manager
`voice.utterance_out` entries, all marked with `mode: "voice"`.

User voice interaction is saved in `sessions/homework/ex8/sess_bbae689b51b2/workspace/`.

## Citations

- sessions/homework/ex8/sess_bbae689b51b2/logs/trace.jsonl`
- sessions/homework/ex8/sess_bbae689b51b2/workspace/`
