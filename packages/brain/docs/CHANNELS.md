# Canali JANIS — Telegram e WhatsApp

JANIS risponde su app di messaggistica con lo **stesso brain** della UI (terminal, memoria, tool).

## Stato rapido

| Canale | Pronto | Cosa serve |
|--------|--------|------------|
| **Telegram** | Sì | Token bot da @BotFather |
| **WhatsApp** | Bridge separato | Node.js + QR scan una tantum |

Verifica: `GET http://127.0.0.1:8001/api/channels/status`

---

## 1. Telegram (consigliato per iniziare)

1. Apri Telegram → @BotFather → `/newbot` → copia il **token**.
2. Aggiungi in `.env`:

```env
CHANNELS_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_POLLING=true
# Opzionale: solo le tue chat (id numerico). Vuoto = tutti.
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_GROUP_REQUIRE_MENTION=true
```

3. Riavvia JANIS (`python dev/start_backend.py`).
4. Scrivi al bot in privato — JANIS risponde ed esegue tool sul PC.

**Gruppi:** aggiungi il bot al gruppo, menzionalo (`@nome_bot`) se `TELEGRAM_GROUP_REQUIRE_MENTION=true`.

**Trova il tuo chat_id:** scrivi al bot, poi controlla i log backend o usa @userinfobot.

---

## 2. WhatsApp (bridge Node)

WhatsApp non si collega direttamente in Python: serve un **bridge** che parla con JANIS via HTTP.

### Config JANIS (`.env`)

```env
WHATSAPP_BRIDGE_URL=http://127.0.0.1:8787
WHATSAPP_BRIDGE_TOKEN=un-segreto-lungo
WHATSAPP_ALLOWED_FROM=
WHATSAPP_GROUP_REQUIRE_MENTION=true
```

### Avvio bridge

```powershell
cd "C:\APP IA\JANIS\bridge\whatsapp"
npm install
$env:JANIS_HUB_URL="http://127.0.0.1:8001"
$env:WHATSAPP_BRIDGE_TOKEN="un-segreto-lungo"
$env:WHATSAPP_BRIDGE_PORT="8787"
node bridge.mjs
```

1. Scansiona il **QR** con WhatsApp sul telefono (numero dedicato consigliato).
2. I messaggi in arrivo → JANIS → risposta automatica.
3. JANIS invia messaggi via `whatsapp_send` o tool UI.

**Gruppi:** il bridge segnala `is_group` e `mentioned`; configura allowlist se serve.

---

## Sicurezza

- Usa **allowlist** (`TELEGRAM_ALLOWED_CHAT_IDS`, `WHATSAPP_ALLOWED_FROM`) in produzione.
- In gruppo: tieni `*_GROUP_REQUIRE_MENTION=true`.
- `WHATSAPP_BRIDGE_TOKEN` obbligatorio se il bridge è esposto in LAN.

---

## Fleet + canali

- `fleet_execute` esegue comandi su Mac/nodi connessi (`GET /api/fleet/nodes`).
- Lo **scheduler** (`data/memory/scheduler_jobs.json`) può inviare briefing su un canale se imposti `channel` + `chat_id`.

---

## API

| Endpoint | Descrizione |
|----------|-------------|
| `GET /api/channels/status` | Stato Telegram/WhatsApp |
| `POST /api/channels/whatsapp/inbound` | Bridge → JANIS (Bearer token) |
