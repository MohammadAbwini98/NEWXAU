---
name: frontend-ui-review
description: Use when modifying frontend screens, dashboards, UI/UX, CSS, components, forms, charts, notifications, or layouts in src/dashboard_static/.
---

# Frontend UI Review Skill

When modifying the Vanilla JS/HTML dashboard located in `src/dashboard_static/`:

## UI Consistency Rules
- Maintain the existing styling (Vanilla CSS).
- Do not introduce heavy frameworks (React, Vue) without explicit permission.

## Component Reuse Rules
- If adding a new chart or widget, see if an existing DOM creation pattern in `index.html` or `app.js` can be reused.

## Responsiveness Checklist
- [ ] Does the UI scale correctly on mobile devices?
- [ ] Are flexbox/grid containers wrapping correctly?

## Loading/Error/Empty State Checklist
- [ ] Is there a loading spinner or indicator while fetching `/api` endpoints?
- [ ] How does the dashboard behave if the websocket connection fails?
- [ ] Is there an empty state if no signals exist?

## Accessibility Checklist
- [ ] Do buttons and inputs have proper `aria-labels` or semantic HTML (`<button>`, `<input>`)?
- [ ] Is color contrast adequate?

## Dashboard Validation Checklist
- Check if websocket events correctly mutate the DOM without requiring a full page refresh.
- Check browser console for undefined variables or CORS errors.
