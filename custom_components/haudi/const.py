"""Constants for the Haudi (myAudi Connect) integration."""

DOMAIN = "haudi"

# --- Platforms ---
PLATFORMS = [
    "sensor",
    "binary_sensor",
    "device_tracker",
    "lock",
    "climate",
    "button",
]

# --- Config keys ---
CONF_VIN = "vin"
CONF_SPIN = "spin"
CONF_REGION = "region"

# --- Regions ---
REGION_EMEA = "emea"
REGION_NA = "na"
REGION_APAC = "apac"

REGIONS = {
    REGION_EMEA: "Europe / Middle East / Africa",
    REGION_NA: "North America",
    REGION_APAC: "Asia-Pacific",
}

# --- BFF base URLs ---
BFF_BASE_URLS = {
    REGION_EMEA: "https://emea.bff.cariad.digital",
    REGION_NA: "https://emea.bff.cariad.digital",  # NA currently same BFF
    REGION_APAC: "https://emea.bff.cariad.digital",
}

# --- IDK (Identity Kit) ---
OIDC_CONFIG_PATH = "/auth/v1/idk/oidc/openid-configuration"
IDK_LOGIN_PATH = "/login/v1/audi"

IDK_SCOPES = "openid address badge birthplace nationality email phone name mbb"
IDK_REDIRECT_URI = "myaudi:///"
IDK_RESPONSE_TYPE_AUTH = "code"
IDK_RESPONSE_TYPE_TOKEN = "token id_token"
IDK_CODE_CHALLENGE_METHOD = "S256"

IDENTITY_PROVIDERS = {
    REGION_EMEA: "https://identity.vwgroup.io",
    REGION_NA: "https://identity.na.vwgroup.io",
    REGION_APAC: "https://identity.ap.vwgroup.io",
}

# --- MBB (Mobile Backend) ---
MBB_OAUTH_BASE_URL = "https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth"
MBB_TOKEN_PATH = "/mobile/oauth2/v1/token"
MBB_REVOKE_PATH = "/mobile/oauth2/v1/revoke"
MBB_SCOPE = "sc2:fal"

# --- Vehicle API (BFF) ---
VEHICLE_STATUS_PATH = "/vehicle/v1/vehicles/{vin}/selectivestatus"
VEHICLE_PARKING_PATH = "/vehicle/v1/vehicles/{vin}/parkingposition"
VEHICLE_CLIMATE_START_PATH = "/vehicle/v1/vehicles/{vin}/climatisation/start"
VEHICLE_CLIMATE_STOP_PATH = "/vehicle/v1/vehicles/{vin}/climatisation/stop"
VEHICLE_CLIMATE_SETTINGS_PATH = "/vehicle/v1/vehicles/{vin}/climatisation/settings"
VEHICLE_LOCK_PATH = "/vehicle/v1/vehicles/{vin}/access/lock"
VEHICLE_UNLOCK_PATH = "/vehicle/v1/vehicles/{vin}/access/unlock"
VEHICLE_TRIPS_PATH = "/vehicle/v1/trips/{vin}/{trip_type}"
VEHICLE_WAKEUP_PATH = "/vehicle/v1/vehicles/{vin}/wakeup"

# --- Status jobs ---
STATUS_JOBS = [
    "access",
    "charging",
    "climatisation",
    "measurements",
    "oilLevel",
    "vehicleHealthInspection",
    "vehicleHealthWarnings",
    "lights",
    "departureTimers",
    "chargingProfiles",
    "batteryChargingCare",
]

# --- MBB Legacy endpoints ---
MBB_MAL_BASE_URL = "https://mal-3a.prd.eu.dp.vwg-connect.com/api"

# --- SPIN (Security PIN) ---
SPIN_PREPARE_PATH = "/rolesrights/authorization/v2/security-pin-auth-requested"
SPIN_COMPLETE_PATH = "/rolesrights/authorization/v2/security-pin-auth-completed"

# --- HTTP headers ---
HEADER_USER_AGENT = "myAudi/5.2.2 (Android)"
HEADER_ACCEPT = "application/json"
HEADER_CONTENT_TYPE = "application/json"

# --- Update interval ---
DEFAULT_UPDATE_INTERVAL = 300  # 5 minutes

# --- Token keys ---
TOKEN_ACCESS = "access_token"
TOKEN_REFRESH = "refresh_token"
TOKEN_ID = "id_token"
TOKEN_EXPIRES_IN = "expires_in"
TOKEN_EXPIRES_AT = "expires_at"
TOKEN_MBB_ACCESS = "mbb_access_token"
TOKEN_MBB_REFRESH = "mbb_refresh_token"
TOKEN_MBB_CLIENT_ID = "mbb_client_id"
