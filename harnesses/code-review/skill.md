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

2. **Automated security scan (MANDATORY — run before manual review)**
   Run these Grep patterns against all source files. Record every match as a preliminary finding:
   - `Grep pattern="(secret|password|api.?key|token)\s*[:=]\s*[\"'][^\"']{3,}" glob="*.{ts,js,py,go,java,yaml,json}"` → hardcoded secrets (auto-CRITICAL)
   - `Grep pattern="(default|changeme|password123|dev.?secret|TODO.*secret)" glob="*.{ts,js,py,yaml,json,env}"` → placeholder credentials (auto-HIGH)
   - `Grep pattern="\bas\s+(any|[A-Z]\w+)" glob="*.{ts,tsx}"` → unsafe type assertions (auto-HIGH unless justified)
   - `Grep pattern="(SELECT|INSERT|UPDATE|DELETE).*\+.*\"|f[\"'].*SELECT" glob="*.{ts,js,py}"` → SQL injection risk
   - `Grep pattern="\b(eval|exec|Function)\s*\(" glob="*.{ts,js,py}"` → code injection risk
   - For each major exported class/function, verify it has at least one consumer via Grep. Zero-consumer exports = dead code (auto-HIGH)

   Any match on hardcoded secrets → CRITICAL. Any unsafe type assertion → HIGH unless a comment justifies it.

3. **Manual security review**
   For each file, also evaluate:
   - Input validation: is all user-supplied input validated and sanitized before use?
   - Authentication/authorization: are access controls enforced at the right layer?
   - Injection risks: SQL injection, command injection, template injection, XSS
   - Hardcoded secrets: API keys, passwords, tokens in source code
   - Dependency vulnerabilities: new dependencies with known CVEs
   - Cryptography: weak algorithms (MD5, SHA1 for security), custom crypto, improper key/IV reuse
   - Information leakage: error messages that expose internal paths, stack traces, or credentials

   For each finding: record `[SEVERITY] [file:line] — security: [description]`

4. **Code quality review**
   For each file, evaluate:
   - Single responsibility: does each function/class do exactly one thing?
   - DRY violations: duplicated logic that should be extracted into a shared function
   - Cyclomatic complexity: functions with more than 10 branches/paths
   - Error handling: are error paths handled? Are exceptions caught too broadly (bare `except`)?
   - Edge cases: null/undefined, empty collections, boundary values, integer overflow
   - Test coverage: are the changes covered by tests? Are the tests meaningful?

   For each finding: record `[SEVERITY] [file:line] — quality: [description]`

5. **Performance review**
   For each file, evaluate:
   - Algorithmic complexity: O(n²) or worse loops where O(n) or O(n log n) is achievable
   - N+1 query patterns: database queries inside loops
   - Large allocations: unbounded collections, large buffers allocated per-request
   - Blocking I/O in async contexts: synchronous file/network calls in async functions
   - Repeated expensive operations: missing memoization or caching for stable results
   - Unnecessary work: computing values that are discarded or rarely used

   Only flag issues observable at realistic scale. For each finding: record `[SEVERITY] [file:line] — performance: [description]`

6. **Maintainability review**
   For each file, evaluate:
   - Naming: do variables, functions, and types communicate their intent clearly?
   - Comments: are complex sections explained? Are there outdated or misleading comments?
   - Coupling: does this code create tight coupling that will resist future changes?
   - Consistency: does this code follow established patterns in the rest of the codebase?
   - Magic values: unexplained numeric or string literals that should be named constants
   - Dead code: unreachable code, unused imports, variables that are set but never read

   For each finding: record `[SEVERITY] [file:line] — maintainability: [description]`

7. **Synthesize the report**
   - Group findings by severity: CRITICAL → HIGH → MEDIUM → LOW
   - For each finding, write:
     ```
     [SEVERITY] [file:line] — [dimension]
     Issue: [clear description of the problem]
     Why it matters: [impact if not fixed]
     Fix: [concrete suggestion]
     ```
   - Note any areas done well — good patterns worth acknowledging

8. **Write the executive summary**
   - Total findings by severity (e.g., "0 CRITICAL, 2 HIGH, 4 MEDIUM, 3 LOW")
   - Items that must be fixed before this is considered complete (CRITICAL + HIGH)
   - Items that should be addressed in follow-up (MEDIUM)
   - Overall verdict: **APPROVED** / **APPROVED WITH CHANGES** / **NEEDS REVISION**
     - APPROVED: 0 CRITICAL, 0 HIGH
     - APPROVED WITH CHANGES: 0 CRITICAL, HIGH items noted but author acknowledged
     - NEEDS REVISION: Any CRITICAL, or multiple HIGH items
