# CivicLens Controlled Demo Public Service Portal

This directory contains the self-contained local web application used by **Phase 14 (Playwright Browser Automation)** to demonstrate citizen digital service workflows.

## Safety & Privacy Guarantees
1. **Loopback Only**: This portal is hosted strictly on localhost (`/demo-portal/`). It does not connect to any external network or public government infrastructure.
2. **Zero Real Personal Data**: Real personal identifiers (Aadhaar, PAN, phone numbers, real emails) are strictly rejected by the backend PII guard. Only fictional sample data with `(Demo)` indicators is permitted.
3. **No Database Persistence**: Form submissions return simulated reference identifiers (e.g. `DEMO-IC-8F2K9M`) and are immediately discarded. No personal data is stored to disk or database.
4. **Permanent Demo Disclaimers**: All pages display prominent educational simulation banners, page titles containing `[DEMO]`, and clear simulation tags.

## Structure
- `manifest.json`: Structured definition of the 5-step Income Certificate workflow, field selectors (`data-field`), validation rules, and fictional sample values.
- `public/`:
  - `index.html`: Responsive, accessible 5-step form with bilingual English/Tamil toggle.
  - `style.css`: Clean, zero-CDN CSS styles with clear step indicators and review tables.
  - `app.js`: Lightweight client-side script managing step transitions, validations, and simulation confirmation.
