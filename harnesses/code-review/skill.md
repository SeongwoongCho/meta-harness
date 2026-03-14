# Code Review Skill

Evaluate code changes across four dimensions: security, quality, performance, and maintainability. Produce findings with severity ratings and concrete fix suggestions.

---

## Steps

1. **Understand the scope**
   - Read the task description to understand what was implemented and the intent
   - Glob to find all modified or created files
   - Read each file completely — do not skim
   - Identify: primary language, framework, security-sensitive domains (auth, storage, network, user input)
   - Note: "Reviewing [N] files. Domains: [list]."

2. **Security review**
   For each file, evaluate:
   - Input validation: is all user-supplied input validated and sanitized before use?
   - Authentication/authorization: are access controls enforced at the right layer?
   - Injection risks: SQL injection, command injection, template injection, XSS
   - Hardcoded secrets: API keys, passwords, tokens in source code
   - Dependency vulnerabilities: new dependencies with known CVEs
   - Cryptography: weak algorithms (MD5, SHA1 for security), custom crypto, improper key/IV reuse
   - Information leakage: error messages that expose internal paths, stack traces, or credentials

   For each finding: record `[SEVERITY] [file:line] — security: [description]`

3. **Code quality review**
   For each file, evaluate:
   - Single responsibility: does each function/class do exactly one thing?
   - DRY violations: duplicated logic that should be extracted into a shared function
   - Cyclomatic complexity: functions with more than 10 branches/paths
   - Error handling: are error paths handled? Are exceptions caught too broadly (bare `except`)?
   - Edge cases: null/undefined, empty collections, boundary values, integer overflow
   - Test coverage: are the changes covered by tests? Are the tests meaningful?

   For each finding: record `[SEVERITY] [file:line] — quality: [description]`

4. **Performance review**
   For each file, evaluate:
   - Algorithmic complexity: O(n²) or worse loops where O(n) or O(n log n) is achievable
   - N+1 query patterns: database queries inside loops
   - Large allocations: unbounded collections, large buffers allocated per-request
   - Blocking I/O in async contexts: synchronous file/network calls in async functions
   - Repeated expensive operations: missing memoization or caching for stable results
   - Unnecessary work: computing values that are discarded or rarely used

   Only flag issues observable at realistic scale. For each finding: record `[SEVERITY] [file:line] — performance: [description]`

5. **Maintainability review**
   For each file, evaluate:
   - Naming: do variables, functions, and types communicate their intent clearly?
   - Comments: are complex sections explained? Are there outdated or misleading comments?
   - Coupling: does this code create tight coupling that will resist future changes?
   - Consistency: does this code follow established patterns in the rest of the codebase?
   - Magic values: unexplained numeric or string literals that should be named constants
   - Dead code: unreachable code, unused imports, variables that are set but never read

   For each finding: record `[SEVERITY] [file:line] — maintainability: [description]`

6. **Synthesize the report**
   - Group findings by severity: CRITICAL → HIGH → MEDIUM → LOW
   - For each finding, write:
     ```
     [SEVERITY] [file:line] — [dimension]
     Issue: [clear description of the problem]
     Why it matters: [impact if not fixed]
     Fix: [concrete suggestion]
     ```
   - Note any areas done well — good patterns worth acknowledging

7. **Write the executive summary**
   - Total findings by severity (e.g., "0 CRITICAL, 2 HIGH, 4 MEDIUM, 3 LOW")
   - Items that must be fixed before this is considered complete (CRITICAL + HIGH)
   - Items that should be addressed in follow-up (MEDIUM)
   - Overall verdict: **APPROVED** / **APPROVED WITH CHANGES** / **NEEDS REVISION**
     - APPROVED: 0 CRITICAL, 0 HIGH
     - APPROVED WITH CHANGES: 0 CRITICAL, HIGH items noted but author acknowledged
     - NEEDS REVISION: Any CRITICAL, or multiple HIGH items
