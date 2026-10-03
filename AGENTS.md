# AGENTS.md — Bootstrap Router
Runtime/model bağımsız küçük yönlendiricidir; kural deposu değildir. Otorite sırası: `SCHEMA.md` > `AGENTS.md` > wiki policy notları ([[agent-policy]]). Ayrıntılı davranış politikaları wiki policy notlarında yaşar.
## 1. Bilgi Bootstrap
- Kanonik bilgi `wiki/` içindedir; `index/` yalnız türetilmiş gezinme haritasıdır. Her bilgi sorusu önce wiki'ye sorulur.
- Açık klonda keşif `index.md` kökünden başlar; kilitli klonda wiki içeriği okunmaz (kurulum: `README.md`).
- Rota: `python3 scripts/noma_wiki.py root --json` → `hub <slug> --json` (varsa `next_page`) → seçilen `wiki/<slug>.md` notu read aracıyla açılır. Belirsiz soru 2-4 kavrama damıtılır ve `s <kavramlar> --json` ile aranır; arama adayı kanıt değildir.
- Wiki dosya adı tahmin edilmez; tüm wiki context'e alınmaz.
- Ayrıntılı sözleşme: `SCHEMA.md`; erişim/kilit durumu: `README.md`.
## 2. Gizlilik / Stdout Sınırı
- Şifreli dizinlerin (`wiki/ raw/ log/ plans/ index/` vb. — tam liste SCHEMA §1) içerik ve metadata'sı console/stdout'a DÖKÜLEMEZ (bash cat/echo/tee, yanıt metni, log çıktısı).
- CLI yalnız gezinme JSON sinyali üretir: path/slug, `next_page`, arama skoru/eşleşme işareti.
- Açık klonda seçili dosya read aracıyla bağlama açılabilir; yasak olan stdout'a dökmektir ([[r4-stdout-read-ayrimi]]).
## 3. Politikalar
- Görevi araştırmadan önce `python3 -B scripts/noma_policy.py resolve agent-read-policy --json` sonucunu read ile aç; değişmemiş onaylı sürümü yeniden yükleme. Policy keşfi `resolve agent-policy --json` ile başlar; konu notu atfı üyelik değildir. Eksik/bozuk aktivasyonda worktree policy taslağı yürürlükte sayılmaz (kurulum/kurtarma: `scripts/README.md`).
- İlk kalıcı değişiklikten önce `resolve agent-write-policy --json` sonucunu oku ve `python3 -B scripts/noma_board.py begin <task-key>` çalıştır. Düzenleme öncesi `claim <run-id> <paths...>`, teslim öncesi `finish <run-id>`; kullanım `scripts/README.md`.
- Doğrulama: `bash scripts/noma-run-lint.sh` (pre-commit aynı linter'dır); testler `python3 -B -m unittest discover -s scripts -p 'test_*.py'`.
- Kaynak ingest veya ilgili not/session'ın içeriksel yeniden ele alınmasında `resolve wiki-kapsam-butunlugu --json` sonucunu read ile aç; eksiksiz bilgi aktarımı/kapsam kontrolü ve eski notların aşamalı uyarlaması uygulanır.
- Salt-okuma/plan görevi kayıt açmaz. Diğer davranış kuralları yalnız ilgili tetikleyicide onaylı `agent-policy` register'ından bulunur ve `resolve <slug> --json` ile açılır; rutin teknik kararları agent verir, önemli ve kaynaktan çözülemeyen belirsizliği sorar.
