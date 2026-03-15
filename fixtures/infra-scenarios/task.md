# Infrastructure Scenario: Migrate PostgreSQL to Multi-AZ RDS

Migrate the existing single-instance PostgreSQL database to an AWS RDS Multi-AZ deployment to improve availability.

## Requirements

- Provision a new RDS Multi-AZ PostgreSQL 15 instance using Terraform
- Migrate all existing data with zero data loss
- Update application connection strings via environment variables (no hardcoded values)
- Verify replication lag is under 5 seconds before cutting over
- Rollback plan: keep old instance available for 48 hours post-migration

## Acceptance Criteria

- [ ] Terraform plan shows no destructive changes to existing data
- [ ] Migration runbook documented with rollback steps
- [ ] Post-migration smoke test: application connects and queries successfully
