# myAudi 5.2.2 APK Decompilation Analysis
## For Home Assistant Integration Development

---

## App Overview
- **Package:** `de.myaudi.mobile.assistant`
- **Version:** 5.2.2 (build 800343538)
- **Platform:** Android 12+ (SDK 31), Target SDK 36
- **Architecture:** Kotlin/Jetpack Compose, Ktor HTTP client, Koin DI

---

## Authentication Architecture

The app uses a **dual-layer OAuth2** system:

### Layer 1: IDK (Identity Kit) — User Authentication

**Flow:** Authorization Code + PKCE via WebView

| Step | Detail |
|------|--------|
| Discovery | `GET https://emea.bff.cariad.digital/auth/v1/idk/oidc/openid-configuration` |
| Authorize | Browser redirect with `response_type=code`, PKCE S256, random state/nonce |
| Token Exchange | `POST` to token endpoint with `grant_type=authorization_code`, code_verifier |
| Refresh | `POST` with `grant_type=refresh_token` |

**Identity Providers:**
| Region | Host |
|--------|------|
| EU (Production) | `identity.vwgroup.io` |
| EU (Sandbox) | `identity-sandbox.vwgroup.io` |
| Asia-Pacific | `identity.ap.vwgroup.io` |
| North America | `identity.na.vwgroup.io` |

**Scopes:** `openid address badge birthplace nationality email phone name mbb` (+ conditionally `navigation`)

**Client IDs:** Dynamically fetched at runtime (not hardcoded)

### Layer 2: MBB (Mobile Backend) — Vehicle API Authentication

**Bridges IDK → MBB** via `grant_type=id_token`

| Environment | URL |
|-------------|-----|
| Production | `https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth` |

**MBB OAuth Endpoints:**
- Token: `mobile/oauth2/v1/token`
- Revoke: `mobile/oauth2/v1/revoke`
- Auth Code: `mobile/oauth2/v1/requestAuthCode/authorize`

**Default Scope:** `sc2:fal`

**Bridge Flow:**
```
POST .../mobile/oauth2/v1/token
  grant_type = id_token
  token = <IDK_id_token>
  scope = sc2:fal
→ Returns: MBB access_token + refresh_token + client_id
```

### Security PIN (SPIN) — Two-Phase Challenge-Response

Required for lock/unlock operations:
1. **Prepare:** POST to get `challenge` + `securityToken`
2. **Complete:** POST with `hashPinV2(pin, challenge)` + `securityToken`

---

## API Endpoints

### BFF (Backend-For-Frontend) — Modern API

**Base URL:** `https://emea.bff.cariad.digital`

| Category | Method | Path | Notes |
|----------|--------|------|-------|
| **Vehicle Status** | GET | `vehicle/v1/vehicles/{vin}/selectivestatus?jobs=...` | Multi-job query, returns all status data |
| **Climate Start** | POST | `vehicle/v1/vehicles/{vin}/climatisation/start` | Optional settings body |
| **Climate Stop** | POST | `vehicle/v1/vehicles/{vin}/climatisation/stop` | |
| **Climate Settings** | PUT | `vehicle/v1/vehicles/{vin}/climatisation/settings` | Temperature, zones, modes |
| **Lock Vehicle** | POST | `vehicle/v1/vehicles/{vin}/access/lock` | Requires SPIN |
| **Unlock Vehicle** | POST | `vehicle/v1/vehicles/{vin}/access/unlock` | Requires SPIN |
| **Parking Position** | GET | `vehicle/v1/vehicles/{vin}/parkingposition` | Returns lat/lon or 204 |
| **Trip Statistics** | GET | `vehicle/v1/trips/{vin}/{tripType}` | With from/to params |
| **Latest Trip** | GET | `vehicle/v1/trips/{vin}/{tripType}/last` | |
| **Geofences** | GET/POST/PUT/DELETE | `vehicle/v2/alerts/{vin}/geofences` | CRUD geofences |
| **Departure Timers** | POST/PUT/DELETE | `vehicle/v2/departure/{vin}/climatisation/timers` | Create/update/delete |
| **User Info** | GET | `user/v1` | User profile |
| **Login** | GET | `login/v1/audi` | Initial login |

### MBB (Legacy VW Group API)

**MAL Base:** `https://mal-3a.prd.eu.dp.vwg-connect.com/api`
**FAL Base:** `https://fal-3a.prd.eu.dp.vwg-connect.com`

| Service | Path |
|---------|------|
| Vehicle Status | `bs/vsr/v1/{brand}/{country}/vehicles/{vin}/` |
| Lock/Unlock | `bs/rlu/v1/{brand}/{country}/vehicles/{vin}/` |
| Climatisation | `bs/climatisation/v1/{brand}/{country}/vehicles/{vin}/` |
| Trip Statistics | `bs/tripstatistics/v1/{brand}/{country}/vehicles/{vin}/` |

### Other Services

| Service | URL |
|---------|-----|
| App API | `https://app-api.my.audi.com` |
| GraphQL (non-vehicle) | `https://onegraph.audi.com/graphql` |
| Charging | `https://prod.emea.mobile.charging.cariad.digital/` |
| Navigation | `https://prod.emea.naviback.cariad.digital/api/` |
| Push | `https://eu.mobilepush.cariad.digital` |
| Smart Charging | `https://audi.smart-charging-connect.com` |
| Home Charging | `https://mobile-audi.emea.home.charging.cariad.digital` |

---

## Vehicle Status Data Model

The `SelectiveVehicleStatus` response contains 13 data categories:

| Field | Data Available |
|-------|---------------|
| `accessData` | Door lock status, open/close state per door |
| `batteryChargingCareData` | Battery health/care info |
| `chargingData` | Charging state, power (kW), charge rate (km/h), charge type (AC/DC), remaining time |
| `chargingProfilesData` | Configured charging profiles |
| `chargingTimersData` | Charging timer schedules |
| `climatisationData` | Climate state (OFF/COOLING/HEATING/VENTILATION), remaining time |
| `climatisationTimersData` | Climate timer schedules |
| `departureTimersData` | Departure timer settings |
| `lightsData` | Vehicle light status |
| `measurementsData` | Odometer, range, fuel level, state of charge |
| `oilLevelData` | Oil level status |
| `vehicleHealthInspectionData` | Service inspection due dates |
| `vehicleHealthWarningsData` | Active vehicle warnings |

### Charging Status Fields
- `chargingState`: CHARGING, READY_FOR_CHARGING, NOT_READY_FOR_CHARGING, etc.
- `chargePower`: kW
- `chargeRate`: km/h
- `chargeType`: AC, DC, OFF
- `remainingChargingTimeToComplete`: minutes
- `remainingChargingTimeNavigation`: minutes
- `currentMaxChargingPower`: kW
- `carCapturedTimestamp`: UTC timestamp

### Climatisation Settings
- `targetTemperature`
- `climatisationMode`
- `isClimatisationWithoutExternalPower`
- `isClimatisationAtUnlock`
- `isWindowHeatingEnabled`
- Zone controls: front left/right, rear left/right

### Trip Statistics Fields
- `averageSpeed`, `mileage`, `overallMileage`, `travelTime`
- `averageFuelConsumption`, `averageElectricConsumption`
- `totalFuelConsumption`, `totalElectricConsumption`
- `averageRecuperation`, `vehicleType`

---

## HTTP Headers

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <access_token>` |
| `X-Client-ID` | Client/device identifier (MBB) |
| `X-Device-ID` | Device identifier (BFF) |
| `X-Brand` | `audi` |
| `X-Platform` | `android` |
| `X-Device-Timezone` | System timezone ID |
| `X-Sdk-Version` | `4.12.4` |
| `X-Use-BffError-V2` | `true` |
| `Content-Type` | `application/json` |
| `Accept-Language` | Device locale |

---

## Additional Vehicle Capabilities

| Capability | Description |
|------------|-------------|
| Honk & Flash | Remote horn/lights activation |
| Vehicle Wakeup | Wake vehicle from sleep |
| Smart Lock/Unlock | Bluetooth proximity-based lock |
| Mobile Key | Digital car key (NFC/BLE) |
| Child Presence Detection | In-cabin detection alerts |
| Geofence Alerts | Location boundary notifications |
| Valet Alert | Valet mode monitoring |
| Vehicle Data Transfer | Export data from vehicle |

---

## Existing Reference Projects

| Project | URL | Notes |
|---------|-----|-------|
| audiconnect/audi_connect_ha | github.com/audiconnect/audi_connect_ha | Main HA integration (HACS) |
| its-me-prash/vag-connect-ha | github.com/its-me-prash/vag-connect-ha | Multi-brand VAG HA integration |
| John6810/myaudi-api | github.com/John6810/myaudi-api | Python API client, 13-step OAuth2, FastAPI |
| TA2k/ioBroker.vw-connect | github.com/TA2k/ioBroker.vw-connect | ioBroker adapter (JavaScript) |

---

## Decompiled Files Location

- **Manifest:** `decompiled/AndroidManifest.xml`
- **URLs extracted:** `decompiled/urls.txt` (364 URLs)
- **API strings:** `decompiled/api_strings.txt` (15,337 strings)
- **Class list:** `decompiled/classes.txt` (30,372 classes)
- **Decompiled source:** `decompiled/source/` (1,678 targeted Java files)
  - `de/audi/onetouch/` — Main app code (11,708 classes total)
  - `technology/cariad/cat/` — CARIAD platform libraries (15,248 classes total)
  - `cariad/charging/` — Charging subsystem (3,416 classes total)
