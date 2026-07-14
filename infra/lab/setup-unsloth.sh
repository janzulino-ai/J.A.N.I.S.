#!/usr/bin/env bash
# JANIS LLM Lab — venv Unsloth isolato (~/.janis-lab-venv)
set -euo pipefail

VENV="${JANIS_LAB_VENV:-${HOME}/.janis-lab-venv}"
PYTHON="${PYTHON:-python3}"

echo "[lab] Venv: $VENV"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "[lab] ATTENZIONE: nvidia-smi non trovato — training Unsloth richiede GPU NVIDIA + CUDA"
fi

if [[ ! -d "$VENV" ]]; then
  "$PYTHON" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --upgrade pip wheel

# PyTorch CUDA 12.1 (adatta se driver diverso)
if command -v nvidia-smi >/dev/null 2>&1; then
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
  echo "[lab] Installo PyTorch CPU (solo harvest/curate, no train)"
  pip install torch torchvision torchaudio
fi

pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install datasets trl transformers accelerate bitsandbytes peft

echo "[lab] Verifica import..."
python -c "import torch; print('cuda:', torch.cuda.is_available())"
python -c "import unsloth; print('unsloth OK')"

echo "[lab] Fatto. Imposta opzionale: LAB_VENV_PATH=$VENV nel .env brain"
