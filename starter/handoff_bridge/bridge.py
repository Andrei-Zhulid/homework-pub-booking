"""Ex7 — handoff bridge.

Routes between the loop half and the Rasa-backed structured half,
supporting REVERSE handoffs (structured → loop) when the structured
half rejects.

The base sovereign-agent LoopHalf only knows how to request a handoff
FORWARD. The bridge you're building here is the thing that decides
what to do when the structured half says "no, go back and try again".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sovereign_agent.halves import HalfResult
from sovereign_agent.halves.loop import LoopHalf
from sovereign_agent.halves.structured import StructuredHalf
from sovereign_agent.handoff import Handoff
from sovereign_agent.session.directory import Session
from sovereign_agent.session.state import now_utc

BridgeOutcome = Literal["completed", "failed", "max_rounds_exceeded"]


@dataclass
class BridgeResult:
    outcome: BridgeOutcome
    rounds: int
    final_half_result: HalfResult | None
    summary: str


class HandoffBridge:
    """Orchestrates round-trips between LoopHalf and a StructuredHalf.

    Not a sovereign-agent Half itself — it lives one level up, deciding
    which half should run next.
    """

    def __init__(
        self,
        *,
        loop_half: LoopHalf,
        structured_half: StructuredHalf,
        max_rounds: int = 3,
    ) -> None:
        self.loop_half = loop_half
        self.structured_half = structured_half
        self.max_rounds = max_rounds

    # ------------------------------------------------------------------
    # TODO — the main run method
    # ------------------------------------------------------------------
    async def run(self, session: Session, initial_task: dict) -> BridgeResult:
        """Run the bridge until the session completes, fails, or hits max_rounds."""
        from sovereign_agent.handoff import write_handoff

        rounds = 0
        current_input: dict = initial_task
        last_loop: HalfResult | None = None
        last_struct: HalfResult | None = None

        while rounds < self.max_rounds:
            rounds += 1
            if session.state.state == "planning":
                session.update_state(state="executing", current_half="loop")
            session.append_trace_event(
                {
                    "event_type": "bridge.round_start",
                    "actor": "bridge",
                    "timestamp": now_utc().isoformat(),
                    "payload": {"round": rounds, "half": "loop"},
                }
            )

            last_loop = await self.loop_half.run(session, current_input)

            if last_loop.next_action == "complete":
                session.mark_complete(last_loop.output)
                _append_state_change(
                    session,
                    from_state="executing",
                    to_state="completed",
                    round_number=rounds,
                    summary=last_loop.summary,
                )
                return BridgeResult(
                    outcome="completed",
                    rounds=rounds,
                    final_half_result=last_loop,
                    summary=last_loop.summary,
                )

            if last_loop.next_action != "handoff_to_structured":
                reason = (
                    f"loop half returned unexpected next_action="
                    f"{last_loop.next_action!r}: {last_loop.summary}"
                )
                failed_from = session.state.state
                session.mark_failed(reason)
                _append_state_change(
                    session,
                    from_state=failed_from,
                    to_state="failed",
                    round_number=rounds,
                    reason=reason,
                )
                return BridgeResult(
                    outcome="failed",
                    rounds=rounds,
                    final_half_result=last_loop,
                    summary=reason,
                )

            handoff = build_forward_handoff(session, last_loop)
            handoff_path = write_handoff(session, "structured", handoff)
            session.update_state(
                state="handed_off_to_structured",
                current_half="structured",
                handoff_history=[
                    *session.state.handoff_history,
                    handoff.to_dict(),
                ],
            )
            _append_state_change(
                session,
                from_state="loop",
                to_state="structured",
                round_number=rounds,
                reason=handoff.reason,
            )

            last_struct = await self.structured_half.run(session, {"data": handoff.data})
            _archive_forward_handoff(session, handoff_path, rounds)

            if last_struct.next_action == "complete":
                session.mark_complete(last_struct.output)
                _append_state_change(
                    session,
                    from_state="structured",
                    to_state="completed",
                    round_number=rounds,
                    summary=last_struct.summary,
                )
                return BridgeResult(
                    outcome="completed",
                    rounds=rounds,
                    final_half_result=last_struct,
                    summary=last_struct.summary,
                )

            if last_struct.next_action == "escalate":
                reason = last_struct.output.get("reason") or last_struct.summary
                current_input = build_reverse_task(last_loop, last_struct)
                session.update_state(state="executing", current_half="loop")
                _append_state_change(
                    session,
                    from_state="structured",
                    to_state="loop",
                    round_number=rounds,
                    rejection_reason=_rejection_reason_text(last_struct) or reason,
                )
                continue

            reason = (
                f"structured half returned unexpected next_action="
                f"{last_struct.next_action!r}: {last_struct.summary}"
            )
            failed_from = session.state.state
            session.mark_failed(reason)
            _append_state_change(
                session,
                from_state=failed_from,
                to_state="failed",
                round_number=rounds,
                reason=reason,
            )
            return BridgeResult(
                outcome="failed",
                rounds=rounds,
                final_half_result=last_struct,
                summary=reason,
            )

        reason = f"bridge exceeded max_rounds={self.max_rounds}"
        failed_from = session.state.state
        session.mark_failed(reason)
        _append_state_change(
            session,
            from_state=failed_from,
            to_state="failed",
            round_number=rounds,
            reason=reason,
        )
        return BridgeResult(
            outcome="max_rounds_exceeded",
            rounds=rounds,
            final_half_result=last_struct or last_loop,
            summary=reason,
        )


# ---------------------------------------------------------------------------
# Helper constructors — you may use these or write your own
# ---------------------------------------------------------------------------
def build_forward_handoff(session: Session, loop_result: HalfResult) -> Handoff:
    """Package a loop result into a forward-handoff payload for structured."""
    return Handoff(
        from_half="loop",
        to_half="structured",
        written_at=now_utc(),
        session_id=session.session_id,
        reason="loop-half requested confirmation",
        context=loop_result.summary,
        data=(loop_result.handoff_payload or {}).get("data") or loop_result.output,
        return_instructions=(
            "If you cannot confirm (party too large, deposit too high, etc.), "
            "respond with next_action=escalate and include a human-readable "
            "'reason' in output so the loop half can adapt."
        ),
    )


def build_reverse_task(loop_result: HalfResult, struct_result: HalfResult) -> dict:
    """Build the task dict to pass back to the loop half after a reject."""
    reason = (
        _rejection_reason_text(struct_result)
        or struct_result.output.get("reason")
        or struct_result.summary
    )
    return {
        "task": (
            "The structured half rejected the previous proposal. "
            f"Reason: {reason}. Produce an alternative."
        ),
        "context": {
            "prior_result": loop_result.output,
            "rejection_reason": reason,
            "retry": True,
        },
    }


def _append_state_change(
    session: Session,
    *,
    from_state: str,
    to_state: str,
    round_number: int,
    reason: str | None = None,
    rejection_reason: str | None = None,
    summary: str | None = None,
) -> None:
    payload = {
        "from": from_state,
        "to": to_state,
        "round": round_number,
    }
    if reason is not None:
        payload["reason"] = reason
    if rejection_reason is not None:
        payload["rejection_reason"] = rejection_reason
    if summary is not None:
        payload["summary"] = summary
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "timestamp": now_utc().isoformat(),
            "payload": payload,
        }
    )


def _rejection_reason_text(struct_result: HalfResult) -> str | None:
    messages = struct_result.output.get("rasa_messages")
    if not isinstance(messages, list):
        return None

    for message in messages:
        if not isinstance(message, dict):
            continue
        text = message.get("text")
        if isinstance(text, str) and text:
            return text.lower()

    return None


def _archive_forward_handoff(session: Session, handoff_path: Path, round_number: int) -> None:
    """Move the visible IPC handoff into the audit log before the next round."""
    if not handoff_path.exists():
        return
    archive_path = session.handoffs_audit_dir / f"round_{round_number}_forward.json"
    if archive_path.exists():
        archive_path.unlink()
    handoff_path.replace(archive_path)


__all__ = [
    "BridgeOutcome",
    "BridgeResult",
    "HandoffBridge",
    "build_forward_handoff",
    "build_reverse_task",
]
