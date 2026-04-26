# Haudi — myAudi Connect for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Connect your Audi vehicle to Home Assistant using the official myAudi / CARIAD APIs.

## Highlights

- **30+ entities** — battery, charging, climate, doors, location, and more
- **Remote control** — lock/unlock, start/stop climate, set temperature
- **No HTML scraping** — browser-based OAuth2 login, resilient to Audi login page changes
- **No credentials stored** — only OAuth2 tokens are persisted
- **Multi-vehicle** — all vehicles on your account are auto-discovered
- **Multi-region** — supports EMEA, North America, and Asia-Pacific

## Quick Start

1. Install via HACS → Custom repository
2. Add the integration in Settings → Devices & Services
3. Log in via the provided link in your browser
4. Paste the redirect URL back — done!

See the [full documentation](README.md) for details.
