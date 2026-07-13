# Sviluppo JANIS dentro Cursor

Per vedere le modifiche **al volo** senza la finestra pywebview.

## Avvio rapido

1. **F5** → profilo **「JANIS in Cursor (consigliato)」**
   - Avvia backend con hot-reload (`backend/` + `frontend/`)
   - Apre il browser (o usa Simple Browser sotto)

2. **Simple Browser in Cursor** (affiancato al codice):
   - `Ctrl+Shift+P` → **Simple Browser: Show**
   - URL: `http://127.0.0.1:8001/?mode=browser`

3. Modifichi `frontend/*.js` o `*.css` → **F5** nella pagina (o Ctrl+Shift+R)  
   Modifichi `backend/` → uvicorn ricarica da solo.

## Script alternativo

```powershell
.\dev\run-cursor.ps1
```

Poi apri Simple Browser con l’URL sopra.

## Stop

```powershell
.\dev\stop-backend.ps1
```

(o chiudi il terminale del backend)

## Quando usare la finestra nativa

- Test overlay / pywebview / `open_url` Windows → `JANIS App — finestra pywebview` o `.\dev\run-debug.ps1`

## Layout consigliato in Cursor

| Sinistra | Destra |
|----------|--------|
| Codice `frontend/` / `backend/` | Simple Browser JANIS |
| Terminale backend (F5) | Chat JANIS live |
