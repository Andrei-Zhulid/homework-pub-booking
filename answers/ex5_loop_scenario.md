# Ex5 — Edinburgh research loop scenario

## Your answer

The successful Ex5 workflow depends on the planner preserving the correct
dataflow between tools, not just listing the right tools somewhere in the overall task.
`calculate_cost` needs a concrete `venue_id` from `venue_search`, plus the `party_size`
and `duration` from the task context. In the failed runs, the original planner
split cost calculation into a separate subgoal that only mentioned "the venue".
`depends_on` ordered it after venue search, but the loop executor was prompted with
only the current subgoal, so it did not have the previous tool output available as
arguments.

The correct plan describes the right tool call sequence and makes the data flow between
the tools explicit. This gives the executor everything it needs before the
`generate_flyer` step, so the flyer can be produced without fabricating values.


## Citations

- sessions/examples/ex5-edinburgh-research/sess_eec1ae441648/logs/trace.jsonl — tool call sequence
- sessions/examples/ex5-edinburgh-research/sess_eec1ae441648/workspace/flyer.html — the produced flyer
