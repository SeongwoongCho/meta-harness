# System-Design Skill

Design and implement multi-component systems from scratch. This harness handles greenfield projects that span multiple services, external integrations, and infrastructure — going beyond single-module TDD to produce deployable, production-ready systems.

---

## Steps

1. **Architecture Decision Records (ADR)**
   - Read the task description and any prior chain context (from ralplan-consensus)
   - Identify all components mentioned or implied by the task
   - For each component, decide:
     - Technology choice (framework, library, database) with rationale
     - Communication pattern (sync HTTP, async queue, event-driven)
     - Whether it needs its own process/container or can be in-process
   - Document decisions as a concise ADR list:
     - ADR-1: "[Decision] because [rationale]"
     - ADR-2: ...
   - Specifically address:
     - Sync vs async processing (use task queues for operations >5s)
     - Data flow between components (who calls whom, what format)
     - External service integration strategy (real client vs stub)

2. **Project skeleton**
   - Create the project directory structure following the ADR decisions
   - Set up:
     - Package/dependency file (requirements.txt, package.json, go.mod, etc.)
     - Configuration management (settings file, .env.example with all required vars)
     - Docker infrastructure (Dockerfile for each service, docker-compose.yml for orchestration)
     - Entry point for each service
   - Install dependencies and verify the skeleton builds/imports without errors
   - This step produces a runnable empty shell — no business logic yet

3. **Data models and interfaces**
   - Define all data models/schemas (Pydantic, TypeScript interfaces, protobuf, etc.)
   - Define API contracts:
     - Endpoint signatures (path, method, request/response types)
     - Event/message schemas (for queues/pubsub)
     - Database schemas (tables, indexes, migrations)
   - Write model validation tests (schema correctness, serialization roundtrip)

4. **Component implementation (ordered by dependency)**
   - Identify the dependency order: which components must exist before others can be built
   - For each component (in dependency order):
     a. Implement core business logic
     b. Write unit tests for the component (target 70%+ coverage)
     c. Run tests — confirm green before moving to next component
   - For external service integrations:
     - Implement the real client (not just a stub/mock)
     - Include authentication, error handling, pagination where applicable
     - Write tests that mock the external service at the HTTP level (not at the function level)

5. **Infrastructure and deployment**
   - Finalize Dockerfile(s):
     - Multi-stage builds where appropriate
     - Non-root user for security
     - Proper dependency caching layers
   - Finalize docker-compose.yml:
     - All services with health checks
     - Proper networking between services
     - Volume mounts for persistence
     - Environment variable configuration
   - Add any provisioning needed (Grafana dashboards, DB init scripts, etc.)

6. **Integration verification**
   - Write or run an end-to-end smoke test that exercises the full pipeline:
     - Input enters the system (API call, webhook, etc.)
     - Data flows through all components
     - Output is stored/displayed correctly
   - If docker-compose is used, verify services can start together (ports, env vars, dependencies)
   - Fix any integration issues before proceeding

7. **Async and resilience patterns**
   - If the system has long-running operations:
     - Verify task queue / worker is properly configured
     - Test retry logic for transient failures
     - Verify timeout handling
   - If the system has external dependencies:
     - Verify graceful degradation when external services are unavailable
     - Ensure no data loss on transient failures

8. **Security and operational readiness**
   - Verify secrets are not hardcoded (use environment variables)
   - Add structured logging (not print statements)
   - Add a health check endpoint
   - Verify input validation on all external-facing endpoints
   - Check for common vulnerabilities (injection, SSRF, etc.)

9. **Final verification**
   - Run the full test suite — all tests must pass
   - Run the build — no errors
   - Verify docker-compose up works (if applicable)
   - Grep for debug artifacts: `console.log`, `debugger`, `print(`, `TODO`, `HACK`, `FIXME`
   - Remove unintentional artifacts

10. **Handoff report**
    - **Architecture:** Summarize the ADR decisions and component diagram
    - **Components implemented:** List each with its responsibility
    - **API surface:** List all endpoints with request/response types
    - **Infrastructure:** Describe the deployment setup
    - **Test coverage:** State coverage percentage per component
    - **How to run:** Exact commands to start the system
    - **Known limitations:** What was deferred and why
    - **Security considerations:** What was hardened and what needs attention
