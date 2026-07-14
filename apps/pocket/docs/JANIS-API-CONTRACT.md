# JANIS API Contract — Pocket v3.1

Contratto stabile tra **JANIS Pocket** e hub **JANIS**.

## Device ID (fleet)

| device_id | Dispositivo |
|-----------|-------------|
| `iphone-15-pro-max` | iPhone 15 Pro Max |
| `iphone-14-pro` | iPhone 14 Pro |
| `ipad-pro-2020` | iPad Pro 12.9" 4ª gen 2020 |

Legacy (deprecati): `pocket-iphone`, `pocket-ipad`

## Autenticazione

```
Header: X-JANIS-Token: <token opzionale>
```

## REST

### GET /api/status
**200**
```json
{
  "version": "1.0.0",
  "nodes": [
    { "id": "mac-node", "status": "online", "detail": "..." },
    { "id": "win-vm", "status": "busy", "detail": "..." }
  ],
  "jobs": ["job-abc"],
  "active_job": "job-abc"
}
```

### POST /api/stt
`multipart/form-data`: `file` (audio), `language=it`  
**200**: `{ "text": "...", "language": "it", "engine": "whisper" }`

### POST /api/presence/claim
```json
{
  "device_id": "iphone-15-pro-max",
  "surface": "mobile",
  "follow_user": true,
  "body": { "organs": {}, "bridge_actions": [], "version": "3.1.0" }
}
```

### POST /api/pocket/telemetry
Campi obbligatori: `device_id`, `timestamp`  
Campi v3: `battery`, `location`, `environment`, `network`, `health`, `owner`, `body`, `capabilities[]`  
**200**: `{}` o `{ "ok": true }`

### POST /api/pocket/vision
```json
{
  "device_id": "iphone-15-pro-max",
  "image_base64": "<jpeg>",
  "timestamp": "ISO8601",
  "owner": { "display_name": "...", "verified": true },
  "context": "optional"
}
```

### POST /api/pocket/push/register
```json
{
  "device_id": "iphone-15-pro-max",
  "token": "<apns_hex>",
  "platform": "ios",
  "owner": {}
}
```

### GET /api/devices/ios/pending?device=iphone-15-pro-max
**200**: `[]` oppure
```json
{
  "commands": [
    { "id": "cmd-1", "action": "speak", "params": { "text": "Ciao" } }
  ]
}
```

### POST /api/devices/ios/complete
```json
{
  "device": "iphone-15-pro-max",
  "command_id": "cmd-1",
  "result": { "ok": true }
}
```

## WebSocket

`ws://HOST/ws/janis?device_id=iphone-15-pro-max&session_id=<uuid>`

### Client → server
```json
{
  "type": "chat",
  "text": "messaggio",
  "device_id": "iphone-15-pro-max",
  "identity": {
    "display_name": "Nome",
    "verified": true,
    "device_id": "iphone-15-pro-max",
    "verified_at": "ISO8601"
  }
}
```

### Server → client
| type | campi |
|------|-------|
| chat_chunk | text / content / delta |
| chat_end | text opzionale |
| state | state: IDLE \| THINKING \| ACTING |
| knowledge_update | level, count |
| brain_node | count |
| brain_agent | agent, status |
| tool_* | name, tool |
| job_* | status, job_id |

## Bridge actions (26)

notify, speak, stop_speak, open_url, get_location, get_heading, get_battery, get_motion, get_network, get_environment, get_altitude, get_brightness, get_orientation, vibrate, camera_snap, get_vision, scan_qr, torch_on, torch_off, whoami, authenticate, get_clipboard, set_clipboard, get_calendar, search_contacts, register_push, body_manifest

## Codici errore attesi

| HTTP | Significato |
|------|-------------|
| 401 | Token invalido |
| 404 | Endpoint non implementato (Pocket accoda telemetry) |
| 422 | Payload malformato |
| 503 | Hub offline |

## Checklist server DoD

- [ ] Tutti gli endpoint rispondono 2xx in produzione
- [ ] WS rispetta session_id
- [ ] ios_bridge pending/complete funzionante
- [ ] push register + invio APNs verso iphone-15-pro-max, iphone-14-pro, ipad-pro-2020
- [ ] identity in chat usata per personalizzazione risposta
