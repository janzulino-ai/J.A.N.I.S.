# Handoff JANICE Pocket v3.1 → JANIS

Pocket è **corpo esterno** di JANIS: occhi, orecchie, bocca, naso, tatto, mente, braccia, agenda, rubrica, presenza push.

## Organi → bridge actions (26)

| Organo | Azioni |
|--------|--------|
| Occhi | `camera_snap`, `get_vision`, `scan_qr` |
| Orecchie | STT WhisperKit + `POST /api/stt` fallback |
| Bocca | `speak`, `stop_speak` (coda TTS) |
| Naso | `get_environment`, `get_altitude`, `get_heading` |
| Tatto | `vibrate` |
| Mente | `whoami`, `authenticate` |
| Braccia | `get_clipboard`, `set_clipboard`, `torch_on`, `torch_off`, `open_url` |
| Agenda | `get_calendar` (opt-in EventKit) |
| Rubrica | `search_contacts` (opt-in Contacts) |
| Presenza | `register_push`, `notify`, `body_manifest` |

## Telemetry (ogni 60s)

Campi aggiuntivi v3: `environment` (barometro, luminosità, orientamento, bussola), `body` (manifest organi + stato).

## Nuovi endpoint client

| Metodo | Path |
|--------|------|
| POST | `/api/pocket/push/register` — `{ device_id, token, platform, owner }` |

## Presenza

- `POST /api/presence/claim` include `body` manifest
- BG refresh ogni ~15 min (bridge + telemetry)
- Push APNs per svegliare Pocket da JANIS
- Siri: «Chiedi a JANICE» → `AskJANISIntent`

## Da implementare lato JANIS

1. Accettare `body` in presence/telemetry
2. `POST /api/pocket/push/register` + invio push verso device
3. Usare `get_calendar`, `search_contacts`, `scan_qr` da orchestrator
4. Leggere `identity` in chat per personalizzazione

## Versione / roadmap

**3.1.0 (9)** — roadmap client **completa**.

- Live Activity brain/job (Lock Screen + Dynamic Island)
- `docs/JANIS-API-CONTRACT.md` — contratto API
- `docs/WIREGUARD-VPN-SETUP.md` — VPN + template in Impostazioni
- Tab **Corpo** — 11 organi live