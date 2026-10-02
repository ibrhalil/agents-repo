#!/usr/bin/env python3
"""Fine-tune Laya (multilingual base) on the Noma task-gate dataset (RLCD + CE).

Adapted from laya's notebooks/laya_finetune_typed_decisions_mps.py (Apache-2.0):
same training loop; dataset comes from the pilot split instead of
LocalLLaMA/typed-decisions, and calibration uses the pilot calib split.

Usage:
  tmp/laya-pilot/venv/bin/python tmp/laya-pilot/finetune_noma.py \
    --split tmp/laya-pilot/split.json --out tmp/laya-pilot/laya_ft \
    --epochs 6 --device mps
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import torch
from safetensors.torch import load_file, save_file
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from laya_eval import questions_for  # noqa: E402

from laya.agent import _fix_tokenizer_config  # noqa: E402
from laya.common import QTYPES, build_model, build_sequence, proper_reward, render_options  # noqa: E402

MODEL_ID = "convaiinnovations/laya-multilingual"


def gold_for(labels):
    return {
        "needs_web": {"probabilities": {"true": 1.0, "false": 0.0} if labels["needs_web"] else {"true": 0.0, "false": 1.0}},
        "is_simple": {"probabilities": {"true": 1.0, "false": 0.0} if labels["is_simple"] else {"true": 0.0, "false": 1.0}},
        "task_route": {"probabilities": {labels["task_route"]: 1.0}},
        "complexity": {"probabilities": {str(labels["complexity"]): 1.0}},
    }


def build_training_item(tokenizer, cfg, state, question, gold_question):
    qtype = question["type"]
    criteria = question.get("criteria", {})
    if qtype == "choice":
        keys = list(criteria.keys())
        target = [gold_question["probabilities"].get(k, 0.0) for k in keys]
    elif qtype == "noul":
        target = [
            gold_question["probabilities"].get("false", 0.5),
            gold_question["probabilities"].get("true", 0.5),
        ]
    elif qtype == "score":
        n_levels = len(criteria) if isinstance(criteria, list) else 4
        target = [gold_question["probabilities"].get(str(i), 0.0) for i in range(n_levels)]
    else:
        return None
    total = sum(target)
    if total > 0:
        target = [float(x) / total for x in target]
    else:
        target = [1.0 / len(target)] * len(target)
    label = target.index(max(target))
    n_options = len(render_options({"t": qtype, "crit": criteria}))
    sequence, markers = build_sequence(
        tokenizer, state,
        {"t": qtype, "ins": question["instructions"], "crit": criteria},
        cfg["max_len"], cfg["head_max_len"],
    )
    if len(markers) != n_options:
        return None
    return {"ids": sequence, "markers": markers, "qtype": QTYPES[qtype], "target": target, "label": label}


def prepare_items(model_dir, examples):
    with open(Path(model_dir) / "rl_agent_config.json") as f:
        cfg = json.load(f)
    cfg.setdefault("max_len", 1024)
    cfg.setdefault("head_max_len", 256)
    tokenizer = AutoTokenizer.from_pretrained(Path(model_dir) / "tokenizer")
    items = []
    skipped = 0
    questions = questions_for()
    for ex in examples:
        gold = gold_for(ex["labels"])
        for qid, question in questions.items():
            item = build_training_item(tokenizer, cfg, ex["text"], question, gold[qid])
            if item is None:
                skipped += 1
            else:
                items.append(item)
    return items, skipped


def collate(items, pad_id):
    batch_size = len(items)
    seq_len = max(len(item["ids"]) for item in items)
    kmax = max(len(item["markers"]) for item in items)
    input_ids = torch.full((batch_size, seq_len), pad_id, dtype=torch.long)
    attention = torch.zeros((batch_size, seq_len), dtype=torch.long)
    marker_pos = torch.zeros((batch_size, kmax), dtype=torch.long)
    marker_mask = torch.zeros((batch_size, kmax), dtype=torch.bool)
    target = torch.zeros((batch_size, kmax), dtype=torch.float32)
    for i, item in enumerate(items):
        length = len(item["ids"])
        input_ids[i, :length] = torch.tensor(item["ids"], dtype=torch.long)
        attention[i, :length] = 1
        k = len(item["markers"])
        marker_pos[i, :k] = torch.tensor(item["markers"], dtype=torch.long)
        marker_mask[i, :k] = True
        target[i, :len(item["target"])] = torch.tensor(item["target"], dtype=torch.float32)
    return (input_ids, attention, marker_pos, marker_mask, target,
            torch.tensor([item["qtype"] for item in items], dtype=torch.long))


def fit_temperature(samples):
    if len(samples) < 10:
        return 1.0
    kmax = max(len(logits) for logits, _ in samples)
    logits = torch.full((len(samples), kmax), -1e4)
    targets = torch.zeros((len(samples), kmax))
    for i, (values, target) in enumerate(samples):
        logits[i, :len(values)] = torch.as_tensor(values)
        targets[i, :len(target)] = torch.as_tensor(target, dtype=torch.float32)
    log_temperature = torch.zeros(1, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.1, max_iter=100)

    def closure():
        optimizer.zero_grad()
        loss = -(targets * torch.log_softmax(logits / log_temperature.exp(), -1)).sum(-1).mean()
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(torch.clamp(log_temperature.exp(), 0.1, 10.0).item())


def save_checkpoint(model, tokenizer, cfg, output_dir, final=False):
    path = Path(output_dir) if final else Path(output_dir) / "checkpoint_latest"
    path.mkdir(parents=True, exist_ok=True)
    weights = {name: value.detach().half().cpu().contiguous() for name, value in model.state_dict().items()}
    save_file(weights, str(path / "model.safetensors"))
    model.encoder.config.save_pretrained(path / "encoder")
    tokenizer.save_pretrained(path / "tokenizer")
    with open(path / "rl_agent_config.json", "w") as f:
        json.dump(cfg, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="tmp/laya-pilot/split.json")
    ap.add_argument("--out", default="tmp/laya-pilot/laya_ft")
    ap.add_argument("--base", default="tmp/laya-pilot/laya_ml_base")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--micro-batch", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--device", choices=["auto", "mps", "cpu"], default="auto")
    args = ap.parse_args()

    base = Path(args.base)
    if not (base / "model.safetensors").exists():
        from huggingface_hub import snapshot_download
        print(f"Downloading {MODEL_ID} ...")
        snapshot_download(MODEL_ID, local_dir=str(base))
    _fix_tokenizer_config(str(base))

    device = torch.device("mps") if args.device == "auto" and torch.backends.mps.is_available() else torch.device(
        "mps" if args.device == "mps" else "cpu")

    with open(base / "rl_agent_config.json") as f:
        cfg = json.load(f)
    cfg.update({"max_tokens_per_batch": 2048, "max_len": 1024, "head_max_len": 256,
                "gradient_checkpointing": True, "fine_tuned": True, "model_name": "noma-task-gates"})

    tokenizer = AutoTokenizer.from_pretrained(base / "tokenizer")
    model = build_model(cfg, encoder_dir=base / "encoder")
    model.load_state_dict(load_file(str(base / "model.safetensors")), strict=True)
    model.float()
    model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.head_checkpointing = True
    model.to(device).train()

    with open(args.split) as f:
        split = json.load(f)
    train_items, skip_t = prepare_items(str(base), split["train"])
    calib_items, skip_c = prepare_items(str(base), split["calib"])
    print(f"train items={len(train_items)} (skipped {skip_t}); calib items={len(calib_items)} (skipped {skip_c})")

    encoder_params = [p for n, p in model.named_parameters() if "encoder." in n]
    head_params = [p for n, p in model.named_parameters() if "encoder." not in n]
    optimizer = torch.optim.AdamW(
        [{"params": encoder_params, "lr": 2.5e-5}, {"params": head_params, "lr": 1e-4}],
        weight_decay=0.01,
    )
    updates = max(1, math.ceil(len(train_items) / args.micro_batch / args.grad_accum) * args.epochs)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=updates, eta_min=1e-6)
    print(f"device={device}; items={len(train_items)}; updates={updates}")

    for epoch in range(args.epochs):
        random.Random(42 + epoch).shuffle(train_items)
        optimizer.zero_grad(set_to_none=True)
        total_loss, n_batches = 0.0, 0
        sigma = 0.4 + (0.1 - 0.4) * epoch / max(1, args.epochs - 1)
        for start in range(0, len(train_items), args.micro_batch):
            chunk = train_items[start:start + args.micro_batch]
            ids, attention, positions, mask, target, qtype = collate(chunk, tokenizer.pad_token_id)
            ids, attention, positions, mask, target, qtype = (
                ids.to(device), attention.to(device), positions.to(device), mask.to(device), target.to(device), qtype.to(device))
            logits, activation = model(ids, attention, positions, mask, qtype)
            logits = logits.float()
            k = mask.sum(-1, keepdim=True).float()
            eps = torch.randn((4,) + logits.shape, device=device) * sigma * mask
            eps = (eps - eps.sum(-1, keepdim=True) / k) * mask
            noisy_logits = logits.detach().unsqueeze(0) + eps
            probabilities = torch.softmax(noisy_logits.masked_fill(~mask, -1e4), -1)
            with torch.no_grad():
                reward = proper_reward(probabilities, target.unsqueeze(0), qtype, mask, w_sph=0.75, w_rps=1.0)
                advantage = reward - reward.mean(0, keepdim=True)
                advantage = advantage / (advantage.std() + 1e-6)
            logp = -(((noisy_logits - logits.unsqueeze(0)) ** 2) * mask).sum(-1) / (2 * sigma**2)
            loss_rl = -(advantage * logp).mean()
            loss_ce = -(target * torch.log_softmax(logits.masked_fill(~mask, -1e4), -1)).sum(-1).mean()
            loss = (loss_rl + loss_ce + 0.0 * activation.sum()) / args.grad_accum
            loss.backward()
            n_batches += 1
            if n_batches % args.grad_accum == 0 or start + args.micro_batch >= len(train_items):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
            total_loss += loss.item() * args.grad_accum
        print(f"epoch {epoch + 1}/{args.epochs} avg_loss={total_loss / max(1, n_batches):.4f}")

    print("Temperature calibration (calib split) ...")
    model.eval()
    samples = [[] for _ in range(3)]
    with torch.no_grad():
        for start in range(0, len(calib_items), args.micro_batch):
            chunk = calib_items[start:start + args.micro_batch]
            ids, attention, positions, mask, target, qtype = collate(chunk, tokenizer.pad_token_id)
            logits, _ = model(ids.to(device), attention.to(device), positions.to(device), mask.to(device), qtype.to(device))
            for i, item in enumerate(chunk):
                samples[item["qtype"]].append((logits[i, :len(item["markers"])].cpu(), item["target"]))
    temperatures = [fit_temperature(g) if g else 1.2 for g in samples]
    cfg["temperature"] = temperatures
    cfg.pop("temperature_by_options", None)
    save_checkpoint(model, tokenizer, cfg, args.out, final=True)
    print(f"saved {args.out}; temperatures={temperatures}")


if __name__ == "__main__":
    main()
