# Feature Scenario: Bulk CSV Import REST Endpoint

Add a REST endpoint for bulk-importing CSV data into the inventory database.
The endpoint should handle files up to 10 MB with progress reporting.

## Requirements

- `POST /api/inventory/import` accepts `multipart/form-data` with a `file` field
- Supported format: CSV with header row (`sku`, `name`, `quantity`, `price`)
- File size limit: 10 MB
- Progress reporting: return a job ID immediately; poll `GET /api/inventory/import/{jobId}/status`
  for progress (percentage, rows processed, errors encountered)
- Validation: reject rows with missing required fields; collect all row errors before responding
- Idempotency: re-importing the same SKU updates the record rather than duplicating it
- Transaction safety: if > 5% of rows fail validation, roll back the entire import

## Out of Scope

- Real-time WebSocket progress (polling is sufficient for v1)
- Support for XLSX or other formats

## Acceptance Criteria

- [ ] Endpoint returns `202 Accepted` with `{ "jobId": "..." }` within 500 ms regardless of file size
- [ ] Status endpoint returns `{ "status": "processing|complete|failed", "progress": 0-100, "errors": [...] }`
- [ ] Integration tests cover happy path, validation errors, size limit, and rollback
