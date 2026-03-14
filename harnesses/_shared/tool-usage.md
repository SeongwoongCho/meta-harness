## Tool Usage

- Use Glob to discover files by pattern before reading them.
- Use Grep to find patterns, error messages, call sites, and existing conventions.
- Use Read to understand code before modifying it — never edit code you haven't read.
- Use Edit to modify existing files (preferred over Write for existing files).
- Use Write only to create new files.
- Use Bash to run tests, build, and verify. Always show the command and its full output.
- Never assume tests pass — always run them.

## Chain Adaptation Hint (optional)

If you are part of a harness chain and discover during execution that the **next planned harness** is not optimal for the task, you may emit a `next_harness_hint` in your output. The orchestrator will consider replacing the next chain step.

Format — include this at the end of your output if needed:
```
## next_harness_hint
{"harness": "migration-safe", "reason": "Discovered that this task requires schema migration, not just refactoring"}
```

Rules:
- Only suggest a hint if you have strong evidence the planned next step is wrong
- The hint is advisory — the orchestrator may ignore it
- Include a clear `reason` explaining why the switch is needed
- If no adaptation is needed, do not include this section
