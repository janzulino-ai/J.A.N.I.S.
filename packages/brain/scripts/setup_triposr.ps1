# Installa dipendenze TripoSR nel venv dedicato (senza torchmcubes — patch skimage)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$Venv = Join-Path $Root "tools\triposr-venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

if (-not (Test-Path $Python)) {
    Write-Host "[TripoSR] Creazione venv..."
    python -m venv $Venv
}

Write-Host "[TripoSR] Installazione dipendenze..."
& $Pip install --upgrade pip
& $Pip install `
    "omegaconf==2.3.0" `
    "einops==0.7.0" `
    "transformers==4.35.0" `
    "trimesh>=4.5" `
    "rembg" `
    "huggingface-hub" `
    "xatlas==0.0.9" `
    "moderngl==5.10.0" `
    "scikit-image" `
    "onnxruntime"

# PyTorch CUDA se non presente
$torchOk = & $Python -c "import torch; print(torch.cuda.is_available())" 2>$null
if (-not $torchOk) {
    Write-Host "[TripoSR] Installazione PyTorch CUDA..."
    & $Pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
}

Write-Host "[TripoSR] Verifica import..."
& $Python -c @"
import torch
from skimage.measure import marching_cubes
print('torch', torch.__version__, 'cuda', torch.cuda.is_available())
print('skimage marching_cubes OK')
"@

Write-Host ""
Write-Host "Setup completato. Genera mesh:"
Write-Host "  & `"$Python`" `"$Root\scripts\triposr_to_glb.py`""
