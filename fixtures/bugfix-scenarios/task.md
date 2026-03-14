# Bugfix Scenario: Null Pointer Exception in Auth Module

Fix a null pointer exception in the user authentication module when the email field is empty.
The bug is in `src/auth/validate.ts` line 42.

## Reproduction Steps

1. Navigate to the login page
2. Submit the form with the email field left blank
3. Observe: `TypeError: Cannot read properties of null (reading 'toLowerCase')`

## Expected Behavior

When the email field is empty, the validator should return a validation error object
(e.g., `{ valid: false, error: "Email is required" }`) instead of throwing an exception.

## Affected File

`src/auth/validate.ts` — `validateEmail()` function at line 42 does not guard against
`null` or `undefined` input before calling `.toLowerCase()`.

## Notes

- The fix should add a null/undefined guard at the top of `validateEmail()`
- Existing tests in `src/auth/validate.test.ts` should still pass
- Add a new test case covering the empty-email path
