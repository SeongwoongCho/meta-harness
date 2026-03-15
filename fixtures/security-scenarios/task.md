# Security Scenario: Audit and Harden JWT Authentication

Audit the current JWT authentication implementation for vulnerabilities and harden it against common attack vectors.

## Requirements

- Verify the `alg` header is validated server-side (prevent `alg: none` attack)
- Ensure token expiry (`exp` claim) is always enforced
- Add refresh token rotation: invalidate the old refresh token on each use
- Rate-limit login attempts: block IP after 10 failed attempts in 5 minutes
- Log all authentication events (success, failure, token refresh) to the audit log

## Acceptance Criteria

- [ ] Unit tests confirm `alg: none` tokens are rejected
- [ ] Unit tests confirm expired tokens are rejected
- [ ] Integration test confirms refresh token rotation invalidates the previous token
- [ ] No hardcoded secrets in JWT configuration
