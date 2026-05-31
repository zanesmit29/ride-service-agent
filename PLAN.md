# Hackathon plan

Next steps (recommended order):

1. Improve the trip-planning agent.
	Approach: tighten date/origin validation, strengthen candidate scoring, and standardize outputs (best option, comparison, rationale).
	Execution:
	- [x] Add targeted eval cases for date parsing and weather-preference routing.
	- [x] Normalize relative date handling into exact YYYY-MM-DD before any DB calls.
	- [x] Add a simple scoring rubric (temp, wind, rain) to compare candidates consistently.
	- [x] Ensure output always includes a single recommendation plus brief comparison.
	- [x] Ensure that the output format is consistent and easy to render in the UI
	- [x] Add ride-logging date normalization helpers and prompt safeguards for natural-language dates.
	- [x] Wire the ride logger into its own subagent and keep its write path JSON-safe for ADK.
	- [x] Teach ride logging to collect optional metadata like route type, weather, notes, fuel, and average speed.
	- [x] Wire trip planning to the existing shared date parser and keep ambiguous phrases like "next weekend" as clarification cases.

2. Significantly improve the UI so it feels like a production-grade motorcycle co-pilot application.
	Approach: elevate layout, typography, and interaction flow; add clarity for session state and streaming.
	Execution:
	- [x] Add a “session status” banner (connected, streaming, error).
	- [x] Add message grouping, timestamps, and a clear “new session” affordance.
	- [x] Add mobile-first layout tweaks and a loading skeleton for streams.
	- [x] Build the tabbed layout: Copilot, Vehicle status, Reminders, Trips, Profile.
	- [x] Keep a single user selector at the top to reuse across tabs.
	- [x] Remove the right-side landing panel so the landing content reads cleanly on its own.
	- [x] Rewrite the landing page tips so each tab is explained before the user enters the app.
	- [x] Add a lightweight assistant thinking indicator so streamed answers feel live.
	- [x] Vehicle status data: `ride_logs` latest `odometer_end_km`, last ride date, next service highlight.
	- [x] Reminders data: open items from `service_reminders` (due km/date + status).
	- [x] Trips data: recent `ride_logs` (last N, totals, weather summary).
	- [x] Profile data: read-only preferences from `rider_profiles` for `eval_user`.
	- [x] Add a compact preferences panel (read-only) pulled from `get_rider_profile`.
	- [x] Add per-tab loading + empty states and a refresh action.

	Current handoff point:
	- The landing page is now a single-column overview with tab tips.
	- The app shell and chat flow are in place.
	- The ride logger and trip-planning date handling are now wired and validated.
	- Next pick-up point is adding analytics/aggregation to better showcase the MongoDB MCP capabilities.

3. Add a MongoDB aggregation showcase.
	Approach: use aggregate pipelines to turn ride history into clear, demo-friendly insights that prove the MCP toolset is useful beyond simple lookups.
	Execution:
	- [ ] Add a ride-history summary output (total distance, ride count, average distance, average speed if available).
	- [ ] Add a route-type breakdown using `ride_logs` aggregation.
	- [ ] Add a weather/season breakdown from historical rides to show pattern discovery.
	- [ ] Surface one or two aggregation-backed insights in the UI so the demo visibly exercises `aggregate`.
	- [ ] Keep the aggregation logic read-only and separate from ride logging/reminder writes.

4. Add a garage operations agent.
	Approach: synthesize service history, reminders, stock, and planned trips into a maintenance calendar.
	Execution:
	- [ ] Define a “maintenance calendar” output schema (due now, due soon, planned windows).
	- [ ] Add a tool that aggregates service intervals + ride logs into next-due dates.
	- [ ] Incorporate parts stock and open reminders into the final plan.
	- [ ] Add a “next 30/60/90 days” view to keep it actionable.

5. Add a post-ride learning loop.
	Approach: capture structured feedback after a trip and feed it back into planning.
	Execution:
	- [ ] Create a `post_ride_feedback` collection schema (comfort, weather tolerance, route quality).
	- [ ] Add a lightweight UI prompt after a trip to log outcomes.
	- [ ] Update preference fields if the user explicitly confirms changes.
	- [ ] Use feedback to adjust future trip-planning scoring weights.

6. Optimize code and configuration for deployment.
	Approach: remove surprises and make deployment repeatable.
	Execution:
	- [ ] Document required env vars and example `.env` values.
	- [ ] Ensure `/ready` reports critical dependencies (Mongo, MCP server).
	- [ ] Add a one-command Cloud Run deploy guide and expected URLs.
	- [ ] Add lightweight logging for request IDs and tool errors.

Additional recommendations

- Create a thin “adapter layer” for agent responses so UI rendering is stable even if ADK event shapes evolve.
- Add a small seed dataset for Mongo collections to enable instant demos, especially for the aggregation showcase.
- Add a single “demo script” prompt in the UI to show the best end-to-end flow.
- Keep each new feature behind a simple toggle or “beta” path to reduce demo risk.
