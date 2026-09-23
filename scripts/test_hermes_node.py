#!/usr/bin/env python3
"""Hermes düğüm smoke testi: altyapı (LLM'siz) + agent (LLM'li) testleri.

Kullanım:
  python3 scripts/test_hermes_node.py [--no-llm] [--keep-note]
Çıkış: 0 = core testlerin hepsi PASS, 1 = en az bir core FAIL (WARN hariç).
Ortam: CONTAINER (varsayılan hermes-dashboard), MODELLER: zai glm-5.3 / glm-5.3-flash.
"""

import argparse
import json
import pathlib
import shlex
import subprocess
import sys
import time
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
CONTAINER = "hermes-dashboard"
FLASH = "glm-5.3-flash"
MAIN = "glm-5.3"
LLM_TIMEOUT = 300
HOOK = "scripts/hermes_wiki_context.py"
TEST_NOTE = "test-hermes-smoke"


def run(cmd, cwd=None, timeout=120):
    p = subprocess.run(
        shlex.split(cmd) if isinstance(cmd, str) else cmd,
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return p.returncode, p.stdout + p.stderr


def dexec(args, timeout=120):
    return run(["docker", "exec", CONTAINER] + args, timeout=timeout)


def llm(question, model):
    t0 = time.time()
    rc, out = dexec(
        ["hermes", "chat", "--provider", "zai", "--model", model, "-q", question],
        timeout=LLM_TIMEOUT,
    )
    return rc, out, time.time() - t0


def t_compose():
    rc, out = run("docker compose -f scripts/docker-compose.hermes.yml --env-file .env config --quiet")
    return ("PASS", "config geçerli") if rc == 0 else ("FAIL", out.strip()[:160])


def t_dashboard():
    try:
        with urllib.request.urlopen("http://127.0.0.1:9119", timeout=10) as r:
            return ("PASS", f"HTTP {r.status}") if r.status == 200 else ("FAIL", f"HTTP {r.status}")
    except Exception as e:
        return ("FAIL", str(e)[:160])


def t_hook_reg():
    rc, out = dexec(["hermes", "hooks", "list"])
    ok = rc == 0 and "pre_llm_call" in out and "allowed" in out
    return ("PASS", "pre_llm_call kayıtlı + allowlist") if ok else ("FAIL", out.strip()[:160])


def t_hook_contract():
    payload = json.dumps({"cwd": str(REPO), "extra": {"user_message": "test"}})
    p = subprocess.run(
        [sys.executable, str(REPO / HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        ctx = json.loads(p.stdout)["context"]
    except Exception:
        return ("FAIL", f"stdout JSON değil: {p.stdout[:100]!r}")
    if "kullanici-profili" in ctx and "[[" in ctx:
        return ("PASS", f"context {len(ctx)} karakter, ağaç mevcut")
    return ("FAIL", "context ağaç içermiyor")


def t_script_search():
    rc, out = dexec(["python3", "/workspace/scripts/wiki.py", "s", "hafiza", "--json"])
    ok = rc == 0 and out.strip().startswith(("[", "{"))
    return ("PASS", "wiki.py s --json çalıştı") if ok else ("FAIL", out.strip()[:160])


def t_script_find():
    rc, out = dexec(["python3", "/workspace/scripts/find.py", "hafiza", "--limit", "3"])
    return ("PASS", "find.py çalıştı") if rc == 0 else ("FAIL", out.strip()[:160])


def t_script_lint():
    rc, out = dexec(["python3", "/workspace/scripts/lint_repo.py"])
    return ("PASS", "lint_repo.py ERR=0") if rc == 0 else ("FAIL", out.strip()[-200:])


def t_query_flash():
    rc, out, dt = llm("kimim ben", FLASH)
    ok = rc == 0 and "wiki/kullanici-profili.md" in out
    return (("PASS", f"path atıflı cevap ({dt:.0f}s)") if ok
            else ("FAIL", out.strip()[-200:]))


def t_query_main():
    rc, out, dt = llm("Noma'da cron işleri teslimatı için hangi seçenekler var?", MAIN)
    ok = rc == 0 and ("wiki/" in out or "hermes-agent-rehber" in out)
    return (("PASS", f"path atıflı cevap ({dt:.0f}s)") if ok
            else ("FAIL", out.strip()[-200:]))


def t_script_call():
    rc, out, dt = llm(
        "Terminal aracıyla şunu çalıştır: python3 /workspace/scripts/wiki.py s hafiza --json "
        "— çıktıdaki ilk 3 sonucun slug'unu listele. Başka işlem yapma.",
        FLASH,
    )
    ok = rc == 0 and "hafiza-ve-karar-yonetimi" in out
    return (("PASS", f"agent repo scriptini çalıştırdı ({dt:.0f}s)") if ok
            else ("FAIL", out.strip()[-250:]))


def t_note_create(keep):
    q = (
        f"Bu repoda yeni wiki notu oluştur: `python3 scripts/new_note.py {TEST_NOTE} "
        "--title 'Hermes Smoke Test' --type resource --tags test` çalıştır "
        "(--log-op VERME). Sonra wiki/" + TEST_NOTE + ".md dosyasında ## Links bölümüne "
        "[[noma]] bağlantısını ekle. Dosyanın son halini kontrol et ve bitince 'NOT_HAZIR' yaz."
    )
    rc, out, dt = llm(q, FLASH)
    note = REPO / "wiki" / f"{TEST_NOTE}.md"
    if not note.exists():
        return ("FAIL", f"not oluşmadı ({dt:.0f}s): {out.strip()[-200:]}")
    text = note.read_text(encoding="utf-8")
    checks = {
        "frontmatter-title": "title:" in text,
        "template-stage": "stage:" in text,
        "links-noma": "[[noma]]" in text,
    }
    missing = [k for k, v in checks.items() if not v]
    status = "PASS" if not missing else "FAIL"
    detail = f"not oluştu + {sum(checks.values())}/3 yapı ({dt:.0f}s)"
    if missing:
        detail += f" — eksik: {','.join(missing)}"
    if not keep:
        note.unlink()
        detail += "; test notu temizlendi"
    return (status, detail)


def t_web_search():
    rc, out, dt = llm(
        "Bu bilgi repoda yok, web_search aracını KULLANARAK ara: 'sqlite 3.53.4 release "
        "date'. Araç hata verirse hata satırını aynen yaz ve cevabının SONUNA 'WEB_YOK' "
        "ekle. Çalışırsa yayın tarihini belirt.",
        MAIN,
    )
    has_trace = "🔍" in out or "web_search" in out
    if "WEB_YOK" in out:
        return ("WARN", f"web_search kullanılamadı ({dt:.0f}s)")
    if not has_trace:
        return ("WARN", f"araç izi yok ({dt:.0f}s)")
    if rc == 0:
        return ("PASS", f"web_search araç izi + sonuç ({dt:.0f}s)")
    return ("WARN", f"araç izi var, rc={rc} ({dt:.0f}s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-llm", action="store_true", help="yalnız altyapı testleri")
    ap.add_argument("--keep-note", action="store_true", help="test notunu silme")
    a = ap.parse_args()

    infra = [
        ("A1 compose_config", True, t_compose),
        ("A2 dashboard_http", True, t_dashboard),
        ("A3 hook_kayitli", True, t_hook_reg),
        ("A4 hook_sozlesme", True, t_hook_contract),
        ("A5 script_wiki_search", True, t_script_search),
        ("A6 script_find", True, t_script_find),
        ("A7 script_lint", True, t_script_lint),
    ]
    agent = [
        ("B1 query_kimlik_flash", True, t_query_flash),
        ("B2 query_cron_main", True, t_query_main),
        ("B3 script_cagirma_flash", True, t_script_call),
        ("B4 not_olusturma_flash", True, lambda: t_note_create(a.keep_note)),
        ("B5 web_arama", False, t_web_search),
    ]
    tests = infra if a.no_llm else infra + agent

    counts = {"PASS": 0, "FAIL": 0, "WARN": 0}
    for name, core, fn in tests:
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "FAIL", f"istisna: {e}"
        counts[status] += 1
        print(f"{status:4} {name:24} {detail}")

    core_fail = counts["FAIL"]
    print(f"\n== {counts['PASS']} PASS · {counts['WARN']} WARN · {counts['FAIL']} FAIL ==")
    sys.exit(1 if core_fail else 0)


if __name__ == "__main__":
    main()
