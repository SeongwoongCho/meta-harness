# Documentation Scenario: Write API Reference for the Orders Endpoint

Write the complete API reference documentation for the Orders REST API, covering all endpoints introduced in the v2 release.

## Requirements

- Document all five endpoints: `GET /orders`, `POST /orders`, `GET /orders/{id}`, `PATCH /orders/{id}`, `DELETE /orders/{id}`
- Each endpoint must include: description, request parameters, request body schema, response schema, error codes, and one curl example
- Document authentication requirements (Bearer token)
- Include a migration guide from v1 to v2 (breaking changes summary)

## Acceptance Criteria

- [ ] All five endpoints documented with complete schema and examples
- [ ] v1 → v2 migration guide covers all breaking changes
- [ ] Documentation reviewed for technical accuracy against the actual implementation
