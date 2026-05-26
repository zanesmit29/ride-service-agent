# Hackathon plan

Next steps (recommended order):

1. Improve the trip-planning agent.
	Approach: tighten date/origin validation, strengthen candidate scoring, and standardize outputs (best option, comparison, rationale).
	Execution:
	- [ ] Add targeted eval cases for date parsing and weather-preference routing.
	- [ ] Normalize relative date handling into exact YYYY-MM-DD before any DB calls.
	- [ ] Add a simple scoring rubric (temp, wind, rain) to compare candidates consistently.
	- [ ] Ensure output always includes a single recommendation plus brief comparison.

2. Significantly improve the UI so it feels like a production-grade motorcycle co-pilot application.
	Approach: elevate layout, typography, and interaction flow; add clarity for session state and streaming.
	Execution:
	- [ ] Add a “session status” banner (connected, streaming, error).
	- [ ] Add message grouping, timestamps, and a clear “new session” affordance.
	- [ ] Add mobile-first layout tweaks and a loading skeleton for streams.
	- [ ] Build the tabbed layout: Copilot, Vehicle status, Reminders, Trips, Profile.
	- [ ] Vehicle status data: `ride_logs` latest `odometer_end_km`, last ride date, next service highlight.
	- [ ] Reminders data: open items from `service_reminders` (due km/date + status).
	- [ ] Trips data: recent `ride_logs` (last N, totals, weather summary).
	- [ ] Profile data: read-only preferences from `rider_profiles` for `eval_user`.
	- [ ] Add a compact preferences panel (read-only) pulled from `get_rider_profile`.
	- [ ] Add per-tab loading + empty states and a refresh action.
	- [ ] Keep a single user selector at the top to reuse across tabs.

3. Add a garage operations agent.
	Approach: synthesize service history, reminders, stock, and planned trips into a maintenance calendar.
	Execution:
	- [ ] Define a “maintenance calendar” output schema (due now, due soon, planned windows).
	- [ ] Add a tool that aggregates service intervals + ride logs into next-due dates.
	- [ ] Incorporate parts stock and open reminders into the final plan.
	- [ ] Add a “next 30/60/90 days” view to keep it actionable.

4. Add a post-ride learning loop.
	Approach: capture structured feedback after a trip and feed it back into planning.
	Execution:
	- [ ] Create a `post_ride_feedback` collection schema (comfort, weather tolerance, route quality).
	- [ ] Add a lightweight UI prompt after a trip to log outcomes.
	- [ ] Update preference fields if the user explicitly confirms changes.
	- [ ] Use feedback to adjust future trip-planning scoring weights.

5. Optimize code and configuration for deployment.
	Approach: remove surprises and make deployment repeatable.
	Execution:
	- [ ] Document required env vars and example `.env` values.
	- [ ] Ensure `/ready` reports critical dependencies (Mongo, MCP server).
	- [ ] Add a one-command Cloud Run deploy guide and expected URLs.
	- [ ] Add lightweight logging for request IDs and tool errors.

Additional recommendations

- Create a thin “adapter layer” for agent responses so UI rendering is stable even if ADK event shapes evolve.
- Add a small seed dataset for Mongo collections to enable instant demos.
- Add a single “demo script” prompt in the UI to show the best end-to-end flow.
- Keep each new feature behind a simple toggle or “beta” path to reduce demo risk.
