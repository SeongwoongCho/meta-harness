# Refactor Scenario: Payment Processing — Switch-Case to Strategy Pattern

Refactor the payment processing module to use the Strategy pattern instead of the current
switch-case approach. There are currently 6 payment methods supported.

## Current State

`src/payments/processor.ts` contains a single `processPayment(method, payload)` function
with a large switch-case block handling: `credit_card`, `paypal`, `stripe`, `apple_pay`,
`google_pay`, and `bank_transfer`. Each case has 30-80 lines of logic inline.

## Target State

- Extract each payment method into its own class implementing a `PaymentStrategy` interface
- `processor.ts` becomes a thin dispatcher that selects and invokes the correct strategy
- Adding a 7th payment method requires only creating a new strategy class — no changes to
  the dispatcher

## Constraints

- External behavior must be identical (same inputs, same outputs, same error codes)
- All 47 existing unit tests must continue to pass without modification
- No changes to the public API of `processPayment()`

## Definition of Done

- [ ] `PaymentStrategy` interface defined in `src/payments/strategy.ts`
- [ ] 6 strategy classes created, one per payment method
- [ ] `processor.ts` reduced to < 30 lines
- [ ] All 47 existing tests pass
- [ ] New integration test verifies strategy dispatch correctness
