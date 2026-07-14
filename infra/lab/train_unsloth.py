#!/usr/bin/env python3
"""Training Unsloth LoRA — subprocess isolato dal brain JANIS."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _format_alpaca(example: dict) -> str:
    inst = example.get("instruction") or ""
    inp = example.get("input") or ""
    out = example.get("output") or ""
    if inp.strip():
        return (
            f"### Istruzione:\n{inst}\n\n### Input:\n{inp}\n\n### Risposta:\n{out}"
        )
    return f"### Istruzione:\n{inst}\n\n### Risposta:\n{out}"


def main() -> int:
    parser = argparse.ArgumentParser(description="JANIS Unsloth LoRA training")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-model", default="unsloth/llama-3.2-3b-Instruct-bnb-4bit")
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--ollama-name", default="janis-custom")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "train_result.json"

    rows: list[dict] = []
    with open(args.dataset, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    if len(rows) < 10:
        result = {"ok": False, "error": f"Dataset troppo piccolo: {len(rows)} esempi (min 10)"}
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
        return 1

    try:
        import torch
        from datasets import Dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from unsloth import FastLanguageModel
    except ImportError as e:
        result = {"ok": False, "error": f"Dipendenze Unsloth mancanti: {e}"}
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
        return 1

    if not torch.cuda.is_available():
        result = {"ok": False, "error": "CUDA non disponibile — serve GPU NVIDIA"}
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
        return 1

    texts = [_format_alpaca(r) for r in rows]
    ds = Dataset.from_dict({"text": texts})

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.lora_r * 2,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        dataset_text_field="text",
        max_seq_length=2048,
        args=TrainingArguments(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            max_steps=args.max_steps,
            learning_rate=args.learning_rate,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=5,
            optim="adamw_8bit",
            output_dir=str(out_dir / "checkpoints"),
            report_to="none",
            seed=42,
        ),
    )
    train_info = trainer.train()

    adapter_dir = out_dir / "adapter"
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    merged_dir = out_dir / "merged"
    model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")

    # Export GGUF per Ollama (se llama.cpp disponibile via unsloth)
    gguf_path = out_dir / "model.gguf"
    export_info: dict = {}
    try:
        model.save_pretrained_gguf(str(out_dir), tokenizer, quantization_method="q4_k_m")
        ggufs = list(out_dir.glob("*.gguf"))
        if ggufs:
            gguf_path = ggufs[0]
            export_info["gguf"] = str(gguf_path)
    except Exception as e:
        export_info["gguf_error"] = str(e)[:200]

    # Modelfile + ollama create
    ollama_model = args.ollama_name
    modelfile = out_dir / "Modelfile"
    if gguf_path.exists():
        modelfile.write_text(
            f'FROM {gguf_path}\n'
            f'PARAMETER temperature 0.7\n'
            f'PARAMETER num_ctx 4096\n'
            f'SYSTEM """Sei JANIS — assistente AI locale addestrato su conversazioni reali. '
            f'Rispondi sempre in italiano, conciso e utile."""\n',
            encoding="utf-8",
        )
    else:
        modelfile.write_text(
            f'FROM {merged_dir}\n'
            f'PARAMETER temperature 0.7\n'
            f'PARAMETER num_ctx 4096\n'
            f'SYSTEM """Sei JANIS — assistente AI locale. Rispondi in italiano."""\n',
            encoding="utf-8",
        )

    ollama_imported = False
    try:
        import subprocess
        proc = subprocess.run(
            ["ollama", "create", ollama_model, "-f", str(modelfile)],
            capture_output=True,
            text=True,
            timeout=900,
        )
        ollama_imported = proc.returncode == 0
        export_info["ollama_stdout"] = (proc.stdout or "")[:500]
        export_info["ollama_stderr"] = (proc.stderr or "")[:300]
    except Exception as e:
        export_info["ollama_error"] = str(e)[:200]

    result = {
        "ok": True,
        "examples": len(rows),
        "base_model": args.base_model,
        "max_steps": args.max_steps,
        "adapter": str(adapter_dir),
        "merged": str(merged_dir),
        "train_loss": getattr(train_info, "training_loss", None),
        "ollama_model": ollama_model if ollama_imported else None,
        "ollama_imported": ollama_imported,
        **export_info,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out_dir / "export_result.json").write_text(json.dumps(export_info, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
