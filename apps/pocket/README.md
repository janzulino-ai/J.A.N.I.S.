# JANICE Pocket

App iOS nativa (SwiftUI) per note vocali e di testo con archivio locale, trascrizione in italiano e estetica e-ink.

## Requisiti

- macOS con **Xcode 15+**
- iOS **17.0+** (dispositivo fisico consigliato per microfono e Speech)
- Account Apple Developer (per firma e deploy su iPhone)

## Setup su Mac

1. Clona il repository:
   ```bash
   git clone https://github.com/janzulino-ai/JANICE-Pocket.git
   cd JANICE-Pocket
   ```
2. Apri il progetto:
   ```bash
   open JANICEPocket.xcodeproj
   ```
3. In Xcode → target **JANICEPocket** → **Signing & Capabilities**:
   - Seleziona il tuo **Team**
   - Verifica Bundle ID: `ai.janzulino.janice.pocket`
4. Collega un iPhone, selezionalo come destinazione e premi **Run** (⌘R).

## Permessi (Info.plist)

L'app richiede due permessi, con descrizioni in italiano già configurate in `Info.plist`:

| Chiave | Uso |
|--------|-----|
| `NSMicrophoneUsageDescription` | Registrazione note vocali (`.m4a`) |
| `NSSpeechRecognitionUsageDescription` | Trascrizione con Apple Speech (`it-IT`) |

Al primo avvio iOS mostrerà i dialoghi di consenso. Se negati, abilita **Microfono** e **Riconoscimento vocale** in *Impostazioni → JANICE Pocket*.

## Trascrizione

- **Predefinita**: Apple Speech (`SFSpeechRecognizer`, locale `it-IT`, punteggiatura)
- **Qualità alta**: OpenAI Whisper API (consigliato per note lunghe >55 s)
- **Fallback**: se un motore fallisce, l'app prova automaticamente l'altro (impostabile)
- **Retry**: fino a 3 tentativi Whisper / 2 Apple Speech
- **Ritrascrivere**: dall'archivio, dettaglio nota → pulsante *Ritrascrivere*
- L'**audio resta sempre** salvato anche se la trascrizione fallisce

### Configurare Whisper

1. Ottieni una API key da [OpenAI](https://platform.openai.com/api-keys)
2. Nell'app: **Impostazioni** → attiva *Usa OpenAI Whisper* → incolla la chiave → **Salva in Keychain**
3. La chiave **non** è nel repository: viene salvata nel Keychain del dispositivo

> **Nota**: Whisper invia l'audio a OpenAI. Usalo solo se accetti l'invio dei dati al servizio cloud.

## Architettura MVP

| Modulo | Descrizione |
|--------|-------------|
| `RecordView` | Registrazione `AVAudioRecorder`, salvataggio permanente |
| `ChatEntryView` | Note testuali stile chat |
| `ArchiveView` | Elenco searchable, raggruppato per data |
| `EntryDetailView` | Riproduzione audio + trascrizione/testo |
| `TranscriptionService` | Apple Speech + Whisper opzionale |
| `JournalEntry` | Modello SwiftData |
| `AudioStorageService` | File `.m4a` in Application Support |

## Icona app

Vedi `JANICEPocket/Resources/APP_ICON_INSTRUCTIONS.md` per PNG 1024×1024 e SVG sorgente.

## Struttura progetto

```
JANICE-Pocket/
├── README.md
├── .gitignore
├── JANICEPocket.xcodeproj/
└── JANICEPocket/
    ├── JANICEPocketApp.swift
    ├── ContentView.swift
    ├── Views/
    ├── Models/
    ├── Services/
    ├── Theme/
    └── Resources/
```

## Palette UI (e-ink)

- Sfondo carta: `#F4F1EA`, `#E8E4DC`
- Testo inchiostro: `#1A1A1A`, `#3D4F5F`
- Splash JANICE: cyan `#00D4FF`, gold `#FFCC00`, navy `#0A1628`

## Troubleshooting

- **Build fallisce per signing**: imposta il Team in Signing & Capabilities
- **Speech non funziona**: verifica connessione (primo download modelli) o prova su dispositivo reale
- **Whisper 401**: chiave API non valida o scaduta
- **Audio non si sente**: controlla che il file esista in Application Support (non viene eliminato dopo la trascrizione)

## Licenza

Progetto privato — © janzulino-ai
