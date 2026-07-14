# Cartelle scrivibili da JANIS (auto-evoluzione monorepo)

JANIS può proporre patch, note e esperimenti qui senza toccare `packages/` direttamente.

| Cartella | Uso |
|----------|-----|
| `evolve/proposals/` | Proposte di modifica (markdown/JSON) |
| `evolve/patches/` | Diff o snippet da applicare |
| `evolve/notes/` | Appunti di sessione |
| `sandbox/` | Prove isolate |
| `runtime/` | Artefatti temporanei |

API brain: `GET /api/evolve/paths`, `GET /api/evolve/files`, `POST /api/evolve/write`

Dopo revisione umana o `autodev`, il contenuto può essere promosso in `packages/`.
