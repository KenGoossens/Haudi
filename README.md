# Haudi — myAudi Connect for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration for Audi vehicles using the official myAudi / CARIAD APIs (reverse-engineered from the myAudi 5.2.2 Android app).

**No HTML scraping.** Authentication happens entirely in your browser via standard OAuth2 + PKCE — the integration never sees your password and is resilient to login page changes.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Setup](#setup)
- [Entities](#entities)
- [Automations](#automations)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## Features

| Category | Capabilities |
|----------|-------------|
| **Monitoring** | Battery %, fuel level, electric & total range, mileage, oil level |
| **Charging** | State, power (kW), rate (km/h), remaining time, plug status, charge type |
| **Climate** | Pre-conditioning on/off, target temperature, zone control |
| **Security** | Door lock status, remote lock/unlock (with S-PIN), trunk & hood status |
| **Location** | Last parked GPS position on the map |
| **Actions** | Force refresh, vehicle wakeup, start/stop climate |

- Supports **multiple vehicles** per account (auto-discovered)
- Data polled every **5 minutes** (configurable)
- Works with **EMEA**, **North America**, and **Asia-Pacific** regions

---

## Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click **⋮** → **Custom repositories**
3. Add this repository URL with category **Integration**
4. Search for **Haudi** and install it
5. **Restart** Home Assistant

### Manual

1. Download or clone this repository
2. Copy the `custom_components/haudi/` folder into your Home Assistant `config/custom_components/` directory
3. **Restart** Home Assistant

---

## Setup

Haudi uses a **browser-based OAuth2 flow** — you log in on Audi's official login page in your own browser. Your credentials are never stored by the integration.

### Step 1 — Add the integration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Haudi (myAudi Connect)**
3. Select your **Region** (Europe/NA/APAC)
4. Optionally enter your **S-PIN** (Security PIN) if you want remote lock/unlock

### Step 2 — Authenticate in your browser

1. The integration shows you a login link — **click it** (or copy/paste into your browser)
2. Log in with your **myAudi account** on the VW Group login page
3. After successful login your browser will try to navigate to a `myaudi:///` URL — this will fail with an error page. **This is expected.**
4. Copy the **full URL** from your browser's address bar (it looks like `myaudi:///?code=abc123&state=xyz...`)

### Step 3 — Paste the redirect URL

1. Go back to Home Assistant
2. Paste the full `myaudi:///...` URL you copied
3. Click **Submit**
4. Your vehicles are automatically discovered and entities are created

> **Tip:** After initial setup, the integration uses OAuth2 refresh tokens automatically. You only need to repeat the browser login if your tokens expire (typically months).

### Screenshots

<details>
<summary>Step 1 — Region selection</summary>

The first screen asks for your region and optional S-PIN.
</details>

<details>
<summary>Step 2 — Browser authentication</summary>

A clickable link opens the VW Group login page. After login, copy the redirect URL.
</details>

<details>
<summary>Step 3 — Paste redirect URL</summary>

Paste the `myaudi:///...` URL and the integration exchanges it for tokens.
</details>

---

## Entities

Each vehicle creates a device with the following entities. Entities with no data from your vehicle will automatically be marked unavailable.

### Sensors

| Entity | Unit | Description |
|--------|------|-------------|
| Battery | % | State of charge (EVs / PHEVs) |
| Fuel level | % | Current fuel level |
| Electric range | km | Remaining electric-only range |
| Total range | km | Combined range (fuel + electric) |
| Mileage | km | Odometer reading |
| Charging power | kW | Current charging power |
| Charge rate | km/h | Charging speed |
| Remaining charge time | min | Time until full charge |
| Charging state | — | `charging`, `ready_for_charging`, etc. |
| Charge type | — | `AC`, `DC`, `off` |
| Climatisation state | — | `off`, `cooling`, `heating`, `ventilation` |
| Oil level | % | Engine oil level |
| Remaining climatisation time | min | Time until climate stops |

### Binary Sensors

| Entity | Type | On = |
|--------|------|------|
| Doors locked | Lock | Unlocked |
| Doors closed | Door | Open |
| Trunk | Opening | Open |
| Hood | Opening | Open |
| Charging plug | Plug | Connected |
| Plug lock | Lock | Unlocked |
| Charging | Battery charging | Charging |
| Lights | Light | On |
| Climatisation | Running | Active |

### Other Platforms

| Platform | Entity | Description |
|----------|--------|-------------|
| **Device Tracker** | Parking position | Last parked GPS coordinates shown on the HA map |
| **Lock** | Vehicle lock | Lock / unlock doors remotely (unlock requires S-PIN) |
| **Climate** | Climate control | Start/stop pre-conditioning, set target temperature (16–30 °C) |
| **Button** | Force refresh | Immediately poll the vehicle for updated data |
| **Button** | Vehicle wakeup | Send a wakeup command to the vehicle |
| **Button** | Start climate | Start pre-conditioning |
| **Button** | Stop climate | Stop pre-conditioning |

---

## Automations

### Example: Notify when charging complete

```yaml
automation:
  - alias: "Audi charging complete"
    trigger:
      - platform: state
        entity_id: binary_sensor.audi_xxxxxx_charging
        from: "on"
        to: "off"
    action:
      - service: notify.mobile_app
        data:
          title: "Charging complete"
          message: "Your Audi is fully charged ({{ states('sensor.audi_xxxxxx_state_of_charge') }}%)"
```

### Example: Pre-heat in winter mornings

```yaml
automation:
  - alias: "Pre-heat Audi at 7 AM in winter"
    trigger:
      - platform: time
        at: "07:00:00"
    condition:
      - condition: numeric_state
        entity_id: weather.home
        attribute: temperature
        below: 5
    action:
      - service: climate.turn_on
        target:
          entity_id: climate.audi_xxxxxx_climatisation
        data:
          temperature: 22
```

### Example: Alert if doors left unlocked

```yaml
automation:
  - alias: "Audi doors unlocked alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.audi_xxxxxx_doors_locked
        to: "on"
        for: "00:10:00"
    action:
      - service: notify.mobile_app
        data:
          title: "Audi unlocked!"
          message: "Your car has been unlocked for 10 minutes."
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                Home Assistant               │
│                                             │
│  ┌─────────────┐    ┌───────────────────┐   │
│  │ Config Flow  │───▶│    AudiAuth       │   │
│  │ (browser     │    │ (OAuth2 PKCE +    │   │
│  │  OAuth2)     │    │  token refresh)   │   │
│  └─────────────┘    └────────┬──────────┘   │
│                              │              │
│  ┌─────────────┐    ┌───────▼──────────┐    │
│  │ Coordinator  │◀──│    AudiAPI       │    │
│  │ (5 min poll) │    │ (BFF + MBB)     │    │
│  └──────┬──────┘    └─────────────────┘    │
│         │                                   │
│  ┌──────▼───────────────────────────────┐   │
│  │ Entities                              │   │
│  │ sensor │ binary_sensor │ lock │ ...   │   │
│  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │   Audi / CARIAD APIs  │
          │                       │
          │ ┌───────────────────┐ │
          │ │ IDK OAuth2        │ │
          │ │ identity.vwgroup  │ │
          │ └───────┬───────────┘ │
          │         │             │
          │ ┌───────▼───────────┐ │
          │ │ BFF REST API      │ │
          │ │ emea.bff.cariad   │ │
          │ │ vehicle status,   │ │
          │ │ climate, lock,    │ │
          │ │ parking position  │ │
          │ └───────────────────┘ │
          │                       │
          │ ┌───────────────────┐ │
          │ │ MBB Bridge        │ │
          │ │ vwg-connect.com   │ │
          │ │ (legacy fallback) │ │
          │ └───────────────────┘ │
          └───────────────────────┘
```

### API Layers

| Layer | Base URL | Purpose |
|-------|----------|---------|
| **IDK** (Identity Kit) | `identity.vwgroup.io` | User authentication (OAuth2 PKCE) |
| **BFF** (Backend for Frontend) | `emea.bff.cariad.digital` | Modern vehicle API — status, climate, lock, parking |
| **MBB** (Mobile Backend) | `mbboauth-1d.prd.ece.vwg-connect.com` | Legacy VW Group API bridge |

### Authentication Flow

```
User's Browser                    Home Assistant                 VW Group IDK
     │                                 │                              │
     │  1. Click authorize link        │                              │
     │◀────────────────────────────────│                              │
     │                                 │                              │
     │  2. Login with myAudi account   │                              │
     │────────────────────────────────────────────────────────────────▶│
     │                                 │                              │
     │  3. Redirect to myaudi:///...?code=XYZ                         │
     │◀───────────────────────────────────────────────────────────────│
     │                                 │                              │
     │  4. User pastes URL             │                              │
     │────────────────────────────────▶│                              │
     │                                 │  5. Exchange code for tokens │
     │                                 │─────────────────────────────▶│
     │                                 │  6. access + id + refresh    │
     │                                 │◀─────────────────────────────│
     │                                 │                              │
     │                                 │  7. Bridge to MBB (id_token) │
     │                                 │─────▶ MBB OAuth              │
     │                                 │◀───── MBB tokens             │
     │                                 │                              │
     │                                 │  All future refreshes        │
     │                                 │  use refresh_token (no       │
     │                                 │  browser needed)             │
```

---

## Troubleshooting

### "Token refresh failed — please re-authenticate"

Your refresh token has expired (typically after several months of inactivity). Delete the integration and add it again to re-authenticate via browser.

### Entities show "Unavailable"

- **Some entities are unavailable by design** — e.g. a petrol car won't have charging sensors, or a non-EV won't have electric range.
- If **all** entities are unavailable, check the Home Assistant logs for API errors.

### "Cannot connect to myAudi servers"

- Check your internet connection
- Audi's servers may be temporarily down — try again in a few minutes
- Make sure you selected the correct **region**

### Lock/unlock doesn't work

- Make sure you entered your **S-PIN** during setup
- The S-PIN is the 4-digit Security PIN you set in the myAudi app
- If you didn't enter it during setup, delete and re-add the integration

### The redirect URL doesn't contain a code

- Make sure you **completed** the login process in your browser
- The URL should look like `myaudi:///?code=...&state=...`
- If you see an error page after login, that's expected — just copy the URL from the address bar

### Rate limiting

The integration polls every 5 minutes. Audi may rate-limit excessive requests. If you see frequent errors, check that you don't have multiple instances running.

---

## Development

### Project Structure

```
custom_components/haudi/
├── __init__.py          # Integration setup, token persistence
├── manifest.json        # HA integration manifest
├── const.py             # API URLs, headers, constants
├── auth.py              # OAuth2 PKCE + MBB token bridge (no HTML parsing)
├── api.py               # Vehicle API client (status, climate, lock, wakeup)
├── coordinator.py       # DataUpdateCoordinator + vehicle data model
├── config_flow.py       # Browser-based OAuth2 config flow
├── entity.py            # Base entity with device info
├── sensor.py            # 13 sensor entities
├── binary_sensor.py     # 9 binary sensor entities
├── device_tracker.py    # GPS parking position
├── lock.py              # Remote lock/unlock
├── climate.py           # Pre-conditioning control
├── button.py            # Action buttons
├── strings.json         # UI strings
└── translations/
    └── en.json          # English translations
```

### Key Design Decisions

1. **Browser-based OAuth2** — No HTML scraping. The user authenticates in their own browser, so the integration never parses VW Group's login pages. This is resilient to any login page UI changes.

2. **Dual token layer** — IDK tokens (VW Group identity) are bridged to MBB tokens (vehicle API access) automatically. This matches what the myAudi app does internally.

3. **Flexible data parsing** — Vehicle status responses from Audi's API vary by vehicle model, API version, and region. The `HaudiVehicleData` class tries multiple JSON paths for each field to handle these variations gracefully.

4. **Token persistence** — Tokens are stored in the HA config entry and refreshed automatically. No credentials are stored.

### API Reference (from APK reverse engineering)

| Endpoint | Method | Path |
|----------|--------|------|
| Vehicle status | GET | `/vehicle/v1/vehicles/{vin}/selectivestatus?jobs=...` |
| Parking position | GET | `/vehicle/v1/vehicles/{vin}/parkingposition` |
| Start climate | POST | `/vehicle/v1/vehicles/{vin}/climatisation/start` |
| Stop climate | POST | `/vehicle/v1/vehicles/{vin}/climatisation/stop` |
| Climate settings | PUT | `/vehicle/v1/vehicles/{vin}/climatisation/settings` |
| Lock | POST | `/vehicle/v1/vehicles/{vin}/access/lock` |
| Unlock | POST | `/vehicle/v1/vehicles/{vin}/access/unlock` |
| Wakeup | POST | `/vehicle/v1/vehicles/{vin}/wakeup` |
| Trips | GET | `/vehicle/v1/trips/{vin}/{tripType}` |

### Status Jobs

The `selectivestatus` endpoint accepts a `jobs` parameter with these values:

`access`, `charging`, `climatisation`, `measurements`, `oilLevel`, `vehicleHealthInspection`, `vehicleHealthWarnings`, `lights`, `departureTimers`, `chargingProfiles`, `batteryChargingCare`

---

## License

MIT — see [LICENSE](LICENSE) for details.

## Credits

- API reverse-engineered from the **myAudi 5.2.2** Android app (CARIAD / VW Group)
- Inspired by [audiconnect/audi_connect_ha](https://github.com/audiconnect/audi_connect_ha) and [its-me-prash/vag-connect-ha](https://github.com/its-me-prash/vag-connect-ha)
