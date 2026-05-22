"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from string import Template

from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from starter.edinburgh_research.integrity import _TOOL_CALL_LOG, record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"
_FLYER_TEMPLATE = Path(__file__).with_name("flyer_template.html")


def _logged_result(
    tool_name: str,
    arguments: dict,
    success: bool,
    output: dict,
    summary: str,
    error: ToolError | None = None,
) -> ToolResult:
    record_tool_call(tool_name, arguments, output)
    return ToolResult(success=success, output=output, summary=summary, error=error)


def _invalid_input_result(tool_name: str, arguments: dict, message: str, context: dict) -> ToolResult:
    err = ToolError(code="SA_TOOL_INVALID_INPUT", message=message, context=context)
    output = {"error": "invalid_input", "message": err.message}
    return _logged_result(tool_name, arguments, False, output, str(err), err)


def _execution_failed_result(tool_name: str, arguments: dict, exc: Exception) -> ToolResult:
    err = ToolError(
        code="SA_TOOL_EXECUTION_FAILED",
        message=f"tool {tool_name} raised {type(exc).__name__}: {exc}",
        context={"tool": tool_name},
        cause=exc,
    )
    output = {"error": "execution_failed", "message": err.message}
    return _logged_result(tool_name, arguments, False, output, str(err), err)


def _tool_error_result(tool_name: str, arguments: dict, err: ToolError) -> ToolResult:
    output = {"error": err.code, "message": err.message}
    return _logged_result(tool_name, arguments, False, output, str(err), err)


def _load_json_fixture(filename: str) -> object:
    fixture_path = _SAMPLE_DATA / filename

    try:
        return json.loads(fixture_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            code="SA_TOOL_DEPENDENCY_MISSING",
            message=f"could not load fixture {filename}",
            context={"path": str(fixture_path)},
            cause=exc,
        ) from exc


def _venue_matches(venue: dict, near_query: str, party_size: int, budget_max_gbp: int) -> bool:
    venue_minimum_gbp = venue.get("hire_fee_gbp", 0) + venue.get("min_spend_gbp", 0)
    return (
        venue.get("open_now") is True
        and near_query in str(venue.get("area", "")).casefold()
        and venue.get("seats_available_evening", 0) >= party_size
        and venue_minimum_gbp <= budget_max_gbp
    )


def _find_venue(venues: list, venue_id: str) -> dict | None:
    return next((venue for venue in venues if venue["id"] == venue_id), None)


def _deposit_required_gbp(total_gbp: int) -> int:
    if total_gbp < 300:
        return 0
    if total_gbp <= 1000:
        amount = total_gbp * 0.20
        return round(amount)
    amount1 = total_gbp * 0.30
    return round(amount1)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _missing_event_fields(event_details: dict, required_fields: tuple[str, ...]) -> list[str]:
    return [field for field in required_fields if field not in event_details]


def _render_fact(label: str, testid: str, value: object) -> str:
    return f"""
        <div class="fact-row">
          <dt>{_escape(label)}</dt>
          <dd data-testid="{_escape(testid)}">{_escape(value)}</dd>
        </div>"""


def _render_flyer_html(event_details: dict) -> str:
    venue_name = event_details["venue_name"]
    venue_address = event_details["venue_address"]
    date = event_details["date"]
    time = event_details["time"]
    party_size = event_details["party_size"]
    condition = event_details["condition"]
    temperature_c = event_details["temperature_c"]
    total_gbp = event_details["total_gbp"]
    deposit_required_gbp = event_details["deposit_required_gbp"]

    facts_html = "\n".join(
        [
            _render_fact("Venue", "venue_name", venue_name),
            _render_fact("Address", "venue_address", venue_address),
            _render_fact("Date", "date", date),
            _render_fact("Time", "time", time),
            _render_fact("Party size", "party_size", party_size),
            _render_fact("Weather", "condition", condition),
            _render_fact("Temperature", "temperature_c", f"{temperature_c}C"),
            _render_fact("Total", "total_gbp", f"£{total_gbp}"),
            _render_fact("Deposit", "deposit_required_gbp", f"£{deposit_required_gbp}"),
        ]
    )
    template = Template(_FLYER_TEMPLATE.read_text(encoding="utf-8"))
    return template.substitute(
        title=f"{_escape(venue_name)} Event Flyer",
        heading=f"{_escape(venue_name)} Night",
        date_summary=_escape(date),
        facts_html=facts_html,
        condition_summary=_escape(condition),
        temperature_summary=f"{_escape(temperature_c)}C",
    )


# ---------------------------------------------------------------------------
# venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    tool_name = "venue_search"
    arguments = {
        "near": near,
        "party_size": party_size,
        "budget_max_gbp": budget_max_gbp,
    }

    if not isinstance(near, str) or not near.strip():
        return _invalid_input_result(
            tool_name,
            arguments,
            message="near must be a non-empty string",
            context={"near": near},
        )

    if type(party_size) is not int or party_size < 1:
        return _invalid_input_result(
            tool_name,
            arguments,
            message="party_size must be a positive integer",
            context={"party_size": party_size},
        )

    if type(budget_max_gbp) is not int or budget_max_gbp < 0:
        return _invalid_input_result(
            tool_name,
            arguments,
            message="budget_max_gbp must be a non-negative integer",
            context={"budget_max_gbp": budget_max_gbp},
        )

    try:
        venues = _load_json_fixture("venues.json")

        search_count = sum(1 for record in _TOOL_CALL_LOG if record.tool_name == tool_name)
        if search_count >= 3:
            output = {"error": "too_many_searches", "count": search_count}
            return _logged_result(
                tool_name,
                arguments,
                False,
                output,
                "STOP calling venue_search; use the results you already have.",
            )

        near_query = near.casefold()
        results = [
            venue
            for venue in venues
            if _venue_matches(venue, near_query, party_size, budget_max_gbp)
        ]
        output = {
            "near": near,
            "party_size": party_size,
            "results": results,
            "count": len(results),
        }
        return _logged_result(
            tool_name,
            arguments,
            True,
            output,
            f"venue_search({near}, party={party_size}): {len(results)} result(s)",
        )
    except ToolError as exc:
        return _tool_error_result(tool_name, arguments, exc)
    except Exception as exc:
        return _execution_failed_result(tool_name, arguments, exc)


# ---------------------------------------------------------------------------
# get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    tool_name = "get_weather"
    arguments = {"city": city, "date": date}

    if not isinstance(city, str) or not city.strip():
        return _invalid_input_result(
            tool_name,
            arguments,
            message="city must be a non-empty string",
            context={"city": city},
        )

    if not isinstance(date, str) or not date.strip():
        return _invalid_input_result(
            tool_name,
            arguments,
            message="date must be a non-empty string in YYYY-MM-DD format",
            context={"date": date},
        )

    try:
        weather = _load_json_fixture("weather.json")

        city_key = city.strip().casefold()
        city_weather = weather.get(city_key)
        if city_weather is None:
            return _invalid_input_result(
                tool_name,
                arguments,
                message=f"no weather fixture for city {city!r}",
                context={"city": city, "available_cities": sorted(weather)},
            )

        date_key = date.strip()
        forecast = city_weather.get(date_key)
        if forecast is None:
            return _invalid_input_result(
                tool_name,
                arguments,
                message=f"no weather fixture for {city_key} on {date_key}",
                context={
                    "city": city_key,
                    "date": date_key,
                    "available_dates": sorted(city_weather),
                },
            )

        output = {"city": city_key, "date": date_key, **forecast}
        return _logged_result(
            tool_name,
            arguments,
            True,
            output,
            f"get_weather({city}, {date_key}): "
            f"{forecast['condition']}, {forecast['temperature_c']}C",
        )
    except ToolError as exc:
        return _tool_error_result(tool_name, arguments, exc)
    except Exception as exc:
        return _execution_failed_result(tool_name, arguments, exc)


# ---------------------------------------------------------------------------
# calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = max(subtotal, venue.min_spend_gbp) + service + <venue's hire_fee_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    tool_name = "calculate_cost"
    arguments = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
    }

    if not isinstance(venue_id, str) or not venue_id.strip():
        return _invalid_input_result(
            tool_name,
            arguments,
            message="venue_id must be a non-empty string",
            context={"venue_id": venue_id},
        )

    if type(party_size) is not int or party_size < 1:
        return _invalid_input_result(
            tool_name,
            arguments,
            message="party_size must be a positive integer",
            context={"party_size": party_size},
        )

    if type(duration_hours) is not int:
        return _invalid_input_result(
            tool_name,
            arguments,
            message="duration_hours must be an integer",
            context={"duration_hours": duration_hours},
        )

    if not isinstance(catering_tier, str) or not catering_tier.strip():
        return _invalid_input_result(
            tool_name,
            arguments,
            message="catering_tier must be a non-empty string",
            context={"catering_tier": catering_tier},
        )

    try:
        catering = _load_json_fixture("catering.json")
        venues = _load_json_fixture("venues.json")
        base_rates = catering["base_rates_gbp_per_head"]
        venue_modifiers = catering["venue_modifiers"]

        tier_key = catering_tier.strip()
        if tier_key not in base_rates:
            return _invalid_input_result(
                tool_name,
                arguments,
                message=f"unknown catering tier {catering_tier!r}",
                context={"catering_tier": catering_tier, "available_tiers": sorted(base_rates)},
            )

        venue_key = venue_id.strip()
        venue = _find_venue(venues, venue_key)
        if venue is None or venue_key not in venue_modifiers:
            return _invalid_input_result(
                tool_name,
                arguments,
                message=f"unknown venue_id {venue_id!r}",
                context={"venue_id": venue_id, "available_venues": sorted(venue_modifiers)},
            )

        base_per_head = base_rates[tier_key]
        venue_multiplier = venue_modifiers[venue_key]
        service_percent = catering["service_charge_percent"]
        hire_fee_gbp = venue["hire_fee_gbp"]
        min_spend_gbp = venue["min_spend_gbp"]

        billable_hours = max(1, duration_hours)
        subtotal_gbp = round(base_per_head * venue_multiplier * party_size * billable_hours)
        service_gbp = round(subtotal_gbp * service_percent / 100)
        total_gbp = round(max(subtotal_gbp, min_spend_gbp) + service_gbp + hire_fee_gbp)
        deposit_required_gbp = _deposit_required_gbp(total_gbp)

        output = {
            "venue_id": venue_key,
            "party_size": party_size,
            "duration_hours": duration_hours,
            "catering_tier": tier_key,
            "subtotal_gbp": subtotal_gbp,
            "service_gbp": service_gbp,
            "total_gbp": total_gbp,
            "deposit_required_gbp": deposit_required_gbp,
        }
        return _logged_result(
            tool_name,
            arguments,
            True,
            output,
            f"calculate_cost({venue_key}, {party_size}): total £{total_gbp}, "
            f"deposit £{deposit_required_gbp}",
        )
    except ToolError as exc:
        return _tool_error_result(tool_name, arguments, exc)
    except Exception as exc:
        return _execution_failed_result(tool_name, arguments, exc)


# ---------------------------------------------------------------------------
# generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    tool_name = "generate_flyer"
    arguments = {"event_details": event_details}
    required_fields = (
        "venue_name",
        "venue_address",
        "date",
        "time",
        "party_size",
        "condition",
        "temperature_c",
        "total_gbp",
        "deposit_required_gbp",
    )

    if not isinstance(event_details, dict):
        return _invalid_input_result(
            tool_name,
            arguments,
            message="event_details must be a dictionary",
            context={"event_details_type": type(event_details).__name__},
        )

    missing = _missing_event_fields(event_details, required_fields)
    if missing:
        return _invalid_input_result(
            tool_name,
            arguments,
            message=f"event_details missing required field(s): {', '.join(missing)}",
            context={"missing_fields": missing},
        )

    try:
        flyer_html = _render_flyer_html(event_details)
        flyer_path = session.path("workspace/flyer.html")
        flyer_path.parent.mkdir(parents=True, exist_ok=True)
        flyer_path.write_text(flyer_html, encoding="utf-8")

        output = {
            "path": "workspace/flyer.html",
            "bytes_written": len(flyer_html.encode("utf-8")),
        }
        return _logged_result(
            tool_name,
            arguments,
            True,
            output,
            f"generate_flyer: wrote workspace/flyer.html ({len(flyer_html)} chars)",
        )
    except ToolError as exc:
        return _tool_error_result(tool_name, arguments, exc)
    except Exception as exc:
        return _execution_failed_result(tool_name, arguments, exc)


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
