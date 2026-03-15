# Frontend Scenario: Dark Mode Support for Settings Page

Add dark mode support to the application settings page, respecting the OS-level preference and allowing the user to override it manually.

## Requirements

- Detect OS dark mode preference via `prefers-color-scheme` media query
- Store user override in `localStorage` (values: `light`, `dark`, `system`)
- Apply the correct CSS theme class to `<body>` on load and on toggle
- Settings page includes a theme selector with three options: Light, Dark, System
- Theme switches without a page reload

## Acceptance Criteria

- [ ] Unit tests confirm correct theme class applied for each combination of OS preference and user override
- [ ] Accessibility: theme selector has correct ARIA labels
- [ ] No flash of unstyled content on page load
