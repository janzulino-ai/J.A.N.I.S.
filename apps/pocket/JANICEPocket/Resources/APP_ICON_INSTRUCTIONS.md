# App Icon — JANICE Pocket

## Asset attuale

- **PNG 1024×1024**: `Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png` (placeholder generato, stile JARVIS cyan/oro)
- **SVG sorgente**: `Resources/AppIcon-Placeholder.svg` (modificabile in Figma/Illustrator)

## Rigenerare l’icona su Mac

1. Apri `AppIcon-Placeholder.svg` in un editor vettoriale o esportalo a 1024×1024 PNG.
2. Sostituisci `AppIcon-1024.png` nell’appiconset.
3. In Xcode: **Assets.xcassets → AppIcon** — verifica che la preview sia corretta.
4. Per tutte le dimensioni legacy, Xcode 15+ usa l’icona universale 1024×1024; al build genera le varianti necessarie.

## Palette JANICE

| Colore | Hex       | Uso              |
|--------|-----------|------------------|
| Cyan   | `#00D4FF` | Neuroni, glow    |
| Gold   | `#FFCC00` | Nodi accent      |
| Navy   | `#0A1628` | Sfondo icona     |
