# Evaluation Sets

This directory contains evaluation sets for testing agent behavior using `adk eval`.

## Running Evaluations

```bash
# Run default evalset
make eval

# Run specific evalset
make eval EVALSET=tests/eval/evalsets/basic.evalset.json

# Run all evalsets
make eval-all
```

## Evalset Format

Each `.evalset.json` follows the ADK evaluation format:

```json
{
  "eval_set_id": "unique_id",
  "name": "Human-readable name",
  "description": "What this evalset tests",
  "eval_cases": [
    {
      "eval_id": "case_id",
      "conversation": [
        {
          "user_content": {
            "parts": [{"text": "User message"}]
          },
          "intermediate_data": {
            "tool_uses": [
              {"name": "tool_name", "args": {"param": "value"}}
            ]
          }
        }
      ],
      "session_input": {
        "app_name": "app_name",
        "user_id": "test_user",
        "state": {}
      }
    }
  ]
}
```

## Key Fields

- `eval_cases`: Array of test scenarios
- `conversation`: Sequence of user messages
- `intermediate_data.tool_uses`: Expected tool calls (for trajectory matching)
- `session_input`: Initial session state

## Evaluation Metrics

ADK eval measures:

- **tool_trajectory_avg_score**: Are the correct tools called in the right order?
- **response_match_score**: How similar is the response to expected output?

## Creating Custom Evalsets

1. Copy `basic.evalset.json` as a template
2. Add cases based on your `DESIGN_SPEC.md` scenarios
3. Include expected tool calls for capability tests
4. Run `make eval EVALSET=your_evalset.json`

## Tips

- Start with 3-5 representative cases
- Include both happy path and edge cases
- Test each core capability from DESIGN_SPEC.md
- Add cases when you find bugs in production

## Debugging the ADK Eval Setup

We debugged the evaluation workflow in a stepwise way:

1. Confirmed the active virtual environment with `$env:VIRTUAL_ENV`.
2. Verified the actual Python interpreter using `python -c "import sys; print(sys.executable)"`.
3. Targeted the active parent venv explicitly using `uv ... --active`.
4. Fixed a Windows file lock issue where `adk.exe` was being used by another process.
5. Re-synced dependencies with `uv sync --active --dev --extra eval`.
6. Ran the full eval command with `uv run --active adk eval ...`.
7. Reduced the problem by creating a minimal one-case evalset.
8. Fixed the evalset schema so it matched ADK’s expected object structure.
9. Confirmed the smoke test passed with `1/1` tests passing.
10. Split failing cases into separate one-case evalsets and verified them individually.
11. Kept the small evalsets as stable regression tests for future debugging.
12. Used uv run --active adk eval ./app "tests/eval/evalsets/memory_regression.evalset.json" --config_file_path="tests/eval/eval_config.json" for example to run specific evalsets.

**Lesson learned:** When ADK eval becomes flaky on a larger suite, isolate the failure into single-case evalsets first. This makes it much easier to separate environment problems, schema problems, and tool-routing problems.


See [ADK documentation](https://google.github.io/adk-docs/) for advanced evaluation options.
