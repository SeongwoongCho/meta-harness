# DevOps Scenario: Add Canary Deployment Stage to CI/CD Pipeline

Extend the existing GitHub Actions CI/CD pipeline to support canary deployments: route 10% of production traffic to the new version before promoting to 100%.

## Requirements

- After the staging deploy passes smoke tests, deploy the new image to 10% of production pods (Kubernetes)
- Run automated smoke tests against the canary pods for 5 minutes
- If all smoke tests pass, promote to 100% of production pods
- If any smoke test fails, roll back the canary and halt the pipeline
- Send a Slack notification on promotion and on rollback

## Acceptance Criteria

- [ ] Pipeline YAML correctly defines canary, promote, and rollback jobs with proper dependencies
- [ ] Rollback job runs automatically on canary smoke test failure
- [ ] Slack notification step fires in both success and failure paths
