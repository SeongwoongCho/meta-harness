# Mobile Scenario: Push Notification Deep Link Handler

Add deep link handling to a React Native app so push notifications route users to the correct in-app screen.

## Requirements

- When the app receives a push notification with a `deep_link` payload (e.g., `app://orders/123`), navigate the user to the correct screen on tap
- Support three link schemes: `app://orders/{id}`, `app://profile`, `app://settings`
- If the app is in the background, navigate on foreground resume
- If the link target does not exist, show a fallback toast

## Acceptance Criteria

- [ ] Tapping a notification with `deep_link: "app://orders/42"` navigates to `OrderDetailScreen` with `orderId=42`
- [ ] Unknown schemes show a toast: "Link not supported"
- [ ] Unit tests cover all three valid schemes and the fallback
