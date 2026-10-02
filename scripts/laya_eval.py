#!/usr/bin/env python3
"""Laya System-1 pilot evaluation for Noma task-gate decisions.

Dataset: JSON with examples[].text and gold labels for four questions:
needs_web (noul), is_simple (noul), task_route (choice), complexity (score 0-3).

Usage (run with the pilot venv python):
  scripts/laya_eval.py build-split tmp/laya-pilot/eval_set.json --out tmp/laya-pilot/split.json
  scripts/laya_eval.py run tmp/laya-pilot/split.json --model auto --out tmp/laya-pilot/res-auto.json
  scripts/laya_eval.py run tmp/laya-pilot/split.json --model multilingual --lang tr --out ...
  scripts/laya_eval.py sweep-options tmp/laya-pilot/split.json --model multilingual --lang tr

Question/threshold contract lives in wiki/system-one-olcum-plani.md.
"""
import argparse
import json
import random
import statistics
import sys
import time

ROUTE_OPTIONS = {
    "wiki": "queries answered from the local encrypted wiki knowledge base",
    "code": "editing, refactoring, debugging or testing repository code",
    "research": "research requiring external web sources or current world knowledge",
    "plan": "designing, planning or restructuring a multistep piece of work",
    "ops": "deployments, infrastructure, board/log/index operational tasks",
    "chat": "greetings, status pings or conversational filler with no task",
}

SWEEP_EXTRA = [
    "database", "security", "networking", "data-pipeline", "mobile",
    "devops-tooling", "browser-ext", "cli-tool", "docs-gen", "analytics",
    "ml-training", "monitoring", "i18n", "packaging", "ci-cd",
    "access-control", "backup", "search-index", "notifications", "billing",
    "auth", "editor-config", "rendering", "streaming", "qa-manual",
    "compliance", "reporting", "integrations", "caching", "migration",
    "fuzzing", "profiling", "localization", "sandboxing", "secrets",
]


def questions_for(route_options=None):
    return {
        "needs_web": {
            "type": "noul",
            "instructions": "Does completing this task require fetching current external information from the web (search, docs, benchmarks, news)? Lookups limited to the local repository or local knowledge base do not count.",
        },
        "is_simple": {
            "type": "noul",
            "instructions": "Is this a simple task that a single direct action or a single local lookup can complete, without multistep reasoning?",
        },
        "task_route": {
            "type": "choice",
            "instructions": "Which category of work does this user task belong to?",
            "criteria": route_options or ROUTE_OPTIONS,
        },
        "complexity": {
            "type": "score",
            "instructions": "How complex is this task?",
            "criteria": [
                "0: conversational filler, greeting or a one-line status question",
                "1: single targeted action, single file edit or single lookup",
                "2: multistep work spanning several files, commands or checks",
                "3: architectural change, long research or a plan that outlives the session",
            ],
        },
    }


def stratified_split(examples, seed=42, train=0.5, calib=0.2):
    rng = random.Random(seed)
    buckets = {}
    for ex in examples:
        key = (ex["labels"]["task_route"], ex["lang"], ex["short"])
        buckets.setdefault(key, []).append(ex)
    split = {"train": [], "calib": [], "test": []}
    for key, items in sorted(buckets.items()):
        items = items[:]
        rng.shuffle(items)
        n = len(items)
        n_train = round(n * train)
        n_calib = round(n * calib)
        split["train"] += items[:n_train]
        split["calib"] += items[n_train:n_train + n_calib]
        split["test"] += items[n_train + n_calib:]
    return split


def ece(pairs, bins=10):
    """pairs: (correct_bool, confidence_float)"""
    if not pairs:
        return None
    bucketed = [[] for _ in range(bins)]
    for ok, conf in pairs:
        idx = min(int(conf * bins), bins - 1)
        bucketed[idx].append((ok, conf))
    total = len(pairs)
    e = 0.0
    for b in bucketed:
        if not b:
            continue
        acc = sum(1 for ok, _ in b if ok) / len(b)
        avg_conf = sum(c for _, c in b) / len(b)
        e += (len(b) / total) * abs(acc - avg_conf)
    return round(e, 4)


def hf_rate(pairs, conf_thr=0.8):
    """High-confidence failure rate: conf>thr and wrong."""
    if not pairs:
        return None
    hf = sum(1 for ok, c in pairs if c > conf_thr and not ok)
    return round(hf / len(pairs), 4)


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return round(s[k], 2)


def noul_conf(answer):
    """Confidence of the PREDICTED class: model's own probability, never gold-derived."""
    p = float(answer["noul"])
    return float(answer.get("answer_confidence", max(p, 1.0 - p)))


def score_conf(answer, pred_level):
    """Confidence of the predicted score level from the model distribution."""
    probs = answer.get("probabilities") or {}
    return float(probs.get(str(pred_level), answer.get("answer_confidence", 0.5)))


def evaluate_split(router, examples, args, model_kwargs):
    qs = questions_for()
    per_q = {"needs_web": [], "is_simple": [], "task_route": [], "complexity": []}
    latencies = []
    for ex in examples:
        t0 = time.perf_counter()
        r = router.predict(ex["text"], qs, **model_kwargs)
        latencies.append((time.perf_counter() - t0) * 1000)
        a = r["answers"]
        gold = ex["labels"]
        nw = a["needs_web"]["noul"]
        per_q["needs_web"].append(((nw >= 0.5) == bool(gold["needs_web"]), round(noul_conf(a["needs_web"]), 4)))
        sm = a["is_simple"]["noul"]
        per_q["is_simple"].append(((sm >= 0.5) == bool(gold["is_simple"]), round(noul_conf(a["is_simple"]), 4)))
        ch = a["task_route"]["choice"]
        probs = a["task_route"].get("probabilities", {})
        conf = probs.get(ch, a["task_route"].get("answer_confidence", a["task_route"].get("confidence", 0.5)))
        per_q["task_route"].append((ch == gold["task_route"], round(float(conf), 4)))
        sc = a["complexity"]["score"]
        pred_level = int(round(float(sc)))
        per_q["complexity"].append((pred_level == int(gold["complexity"]), round(score_conf(a["complexity"], pred_level), 4), pred_level, int(gold["complexity"])))
    out = {}
    for q, pairs in per_q.items():
        if q == "complexity":
            ok_pairs = [(p[0], p[1]) for p in pairs]
            exact = sum(1 for p in pairs if p[0]) / len(pairs)
            within1 = sum(1 for p in pairs if abs(p[2] - p[3]) <= 1) / len(pairs)
            out[q] = {
                "exact_acc": round(exact, 4),
                "within1_acc": round(within1, 4),
                "high_conf_failure": hf_rate(ok_pairs),
                "ece": ece(ok_pairs),
                "n": len(pairs),
            }
        else:
            acc = sum(1 for p in pairs if p[0]) / len(pairs)
            out[q] = {
                "acc": round(acc, 4),
                "high_conf_failure": hf_rate(pairs),
                "ece": ece(pairs),
                "n": len(pairs),
            }
    return {
        "metrics": out,
        "latency_ms": {"p50": pct(latencies, 50), "p95": pct(latencies, 95), "mean": round(statistics.mean(latencies), 2), "n": len(latencies)},
    }


def pick_sweep_options(gold_route, size, rng):
    """Option set of exactly `size` entries that contains the gold route at a
    seed-shuffled position — never systematically first (position leak)."""
    opts = {gold_route: ROUTE_OPTIONS[gold_route]}
    for key, desc in ROUTE_OPTIONS.items():
        if len(opts) >= size:
            break
        if key != gold_route:
            opts[key] = desc
    while len(opts) < size:
        extra = rng.choice(SWEEP_EXTRA)
        if extra not in opts:
            opts[extra] = f"{extra.replace('-', ' ')} related work"
    items = list(opts.items())
    rng.shuffle(items)
    return dict(items)


def sweep_options(router, examples, model_kwargs, sizes=(5, 10, 20, 40)):
    rng = random.Random(7)
    results = {}
    for size in sizes:
        correct = 0
        total = 0
        for ex in examples:
            opts = pick_sweep_options(ex["labels"]["task_route"], size, rng)
            qs = {"task_route": dict(questions_for({"dummy": "x"})["task_route"], criteria=opts)}
            r = router.predict(ex["text"], qs, **model_kwargs)
            ok = r["answers"]["task_route"]["choice"] == ex["labels"]["task_route"]
            correct += ok
            total += 1
        results[str(size)] = {"acc": round(correct / max(total, 1), 4), "n": total}
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build-split", "run", "sweep-options"])
    ap.add_argument("dataset")
    ap.add_argument("--out")
    ap.add_argument("--model", default="auto", help="auto | english | multilingual | typed-decisions")
    ap.add_argument("--lang", help="pin language code, e.g. tr")
    ap.add_argument("--split", default="test", choices=["train", "calib", "test", "all"])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        data = json.load(f)
    examples = data["examples"] if "examples" in data else data

    if args.mode == "build-split":
        split = stratified_split(examples, seed=args.seed)
        counts = {k: len(v) for k, v in split.items()}
        print(json.dumps({"split_sizes": counts, "seed": args.seed}, indent=1))
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(split, f, ensure_ascii=False, indent=1)
        return

    from laya import Router
    t0 = time.perf_counter()
    if args.model not in ("auto", "english", "multilingual", "typed-decisions"):
        import os
        model_path = args.model if os.path.isabs(args.model) else os.path.abspath(args.model)
        router = Router(models={"multilingual": model_path}, preload=["multilingual"], max_loaded=1)
        model_kwargs = {"model": "multilingual"}
        args.model = "ft:" + model_path
    else:
        router = Router(preload=True) if args.model == "auto" else Router()
        model_kwargs = {}
        if args.model != "auto":
            model_kwargs["model"] = args.model
    load_s = round(time.perf_counter() - t0, 1)
    if args.lang:
        model_kwargs["lang"] = args.lang

    split = None
    if args.split != "all":
        with open(args.dataset, encoding="utf-8") as f:
            split = json.load(f)
        examples = split[args.split]

    cold = router.predict(examples[0]["text"], questions_for(), **model_kwargs)
    cold_ms = None  # first predict after load; latency loop below is warm

    if args.mode == "sweep-options":
        print(json.dumps({"options_sweep": sweep_options(router, examples, model_kwargs), "load_s": load_s}, indent=1))
        return

    res = evaluate_split(router, examples, args, model_kwargs)
    res.update({"model": args.model, "lang": args.lang, "split": args.split, "load_s": load_s, "cold_first_model": cold["routing"]["model"]})
    print(json.dumps(res, indent=1))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
