# Prompt Cursor Mac — abilita SSH da Windows

Copia il blocco **PROMPT** in Cursor Agent sul Mac (terminale o chat).

---

## PROMPT

```
Sei Cursor Agent sul Mac Mini M4 (utente janzu, hostname mac-mini-di-janzu.local).

Obiettivo: permettere a Windows (utente agenz, PC JN-PC) di connettersi via SSH senza password, usando chiave pubblica.

Chiave pubblica Windows da autorizzare (authorized_keys):
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ0XI0zzgJAU1Swjntbrg/AsIj1s4uPtBBLF/i/KgESM agenz@JN-PC

Esegui questi passi in ordine, spiegando brevemente cosa fai:

1. Verifica utente: whoami (deve essere janzu) e hostname.

2. Crea ~/.ssh se manca:
   mkdir -p ~/.ssh && chmod 700 ~/.ssh

3. Aggiungi la chiave Windows a ~/.ssh/authorized_keys SOLO se non c'è già (grep prima).
   chmod 600 ~/.ssh/authorized_keys
   chown janzu:staff ~/.ssh ~/.ssh/authorized_keys

4. Attiva Accesso remoto (SSH):
   - Se possibile: sudo systemsetup -setremotelogin on
   - Altrimenti indica: Impostazioni → Generali → Condivisione → Accesso remoto → ON per janzu

5. Verifica:
   - ls -la ~/.ssh
   - cat ~/.ssh/authorized_keys (mostra solo fingerprint, non ripetere tutta la chiave)
   - ipconfig getifaddr en0 (IP LAN)
   - systemsetup -getremotelogin

6. Se esiste nel repo, esegui anche: bash scripts/setup-mac-ssh.sh

7. Output finale per l'utente Windows:
   ssh janzu@mac-mini-di-janzu.local
   oppure ssh janzu@IP_LAN

Non modificare altro nel sistema. Non toccare firewall se SSH locale risponde. Se qualcosa fallisce, spiega cosa fare manualmente in italiano.
```

---

## Dopo il prompt

Su Windows PowerShell:
```powershell
ssh janzu@mac-mini-di-janzu.local
```

Cursor Windows → Remote SSH → `janzu@mac-mini-di-janzu.local`
