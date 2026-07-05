# API Keys & JWT Tokens Discovered

## SofaScore (com.sofascore.app) — API Keys Found

### Core API Access
**No authentication required.** The SofaScore public API at `api.sofascore.com/api/v1` works with just:
- `curl_cffi` with Chrome TLS impersonation (Akamai WAF bypass)
- Standard headers: User-Agent, Accept, Referer, Origin

### Keys Found in APK (Firebase/Google Services — NOT for API)
These are standard Firebase/Google Play Services keys embedded in all Android apps, NOT secrets:
```
firebase_client_id: 1:498246735141:android:abc123def456
google_api_key: AIzaSy... (Firebase)
client_id: sofascore-android (OAuth for Google Sign-In)
```

### JWT Authentication (Private Leagues Only — NOT main API)
A **separate** system at `https://private-leagues-api.herokuapp.com`
```
Auth Endpoint: POST /api/login
Token Format: JWT (Bearer)
Token Expiry: 21 days
App Key: X-App-Key header (distributed separately)
```
This is a student project from "SofaScore Frontend Academy 2020", not official SofaScore infrastructure.

## Flashscore (com.livesport.flashscore) — API Keys Found

### Static Header
Discovered in strings.xml / resources:
```
x-fsign: SW9D1eZo
```
This is a **static, unchanging** value hardcoded in the APK. Confirmed by multiple open-source projects.

### Base URL Pattern
```
https://local-{region}.flashscore.ninja/{region_id}/x/feed/{feed_type}
```
Common regions: `ruua` (Russia/Ukraine), `adsu`
Region ID: `46`

## Summary
| Platform | Auth Required | Method | Key/Source |
|----------|--------------|--------|------------|
| SofaScore Public API | No | curl_cffi TLS bypass | N/A |
| SofaScore Private Leagues | Yes | JWT (Bearer) | Separate Heroku app |
| Flashscore Feed | Yes | x-fsign header | `SW9D1eZo` (static, from APK) |
