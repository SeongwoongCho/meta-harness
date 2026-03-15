# Security-Audit Skill

Audit a codebase or change for security vulnerabilities. Produce a structured, actionable report. Never implement fixes — report and recommend only.

---

## Steps

1. **Scope the audit**
   - Identify all entry points (HTTP endpoints, CLI arguments, file reads, env vars)
   - Map trust boundaries (user-controlled vs. internal data)
   - Identify sensitive data flows (passwords, tokens, PII, secrets)
   - Write down scope before proceeding

2. **OWASP Top-10 scan**
   - Check each category methodically:
     1. **Injection** — SQL, command, LDAP, XPath injection vectors
     2. **Broken authentication** — session management, credential storage, token handling
     3. **Sensitive data exposure** — encryption at rest/in transit, data minimization
     4. **XML/IDOR** — insecure direct object references, path traversal
     5. **Security misconfiguration** — default credentials, exposed admin endpoints, CORS
     6. **Vulnerable components** — outdated or known-vulnerable libraries
     7. **Insufficient logging** — missing audit trails for sensitive operations
     8. **SSRF** — server-side request forgery via user-controlled URLs
     9. **Broken access control** — horizontal/vertical privilege escalation
     10. **Insecure deserialization** — pickle, YAML load, eval on user input

3. **Dependency audit**
   - Run `pip audit`, `npm audit`, or equivalent if available
   - Grep `requirements.txt`, `package.json`, `Cargo.toml` for known vulnerable versions
   - List all outdated dependencies with their latest safe version

4. **Secrets scan**
   - Grep for patterns: `password`, `secret`, `api_key`, `token`, `private_key`, `AWS_SECRET`
   - Check `.env`, config files, and test fixtures
   - Redact any discovered secrets in the report (show only the file path and line number)

5. **Threat model**
   - Enumerate attack vectors relevant to the scoped components
   - For each vector: assess likelihood (Low/Medium/High) and impact (Low/Medium/High/Critical)

6. **Prioritize findings**
   - Assign severity using the matrix: Critical (High likelihood + High impact), High, Medium, Low
   - Order findings by severity descending

7. **Generate fix recommendations**
   - For each finding: provide a specific, actionable recommendation
   - Include a code example for Critical and High severity findings
   - Reference relevant CVEs or CWEs where applicable

8. **Produce the report**
   - Structure: Executive Summary → Critical Findings → High → Medium → Low → Dependency Report → Secrets Summary
   - Each finding includes: severity, file/line, description, recommendation
   - End with a risk score (0–10) and a "top 3 actions" list
