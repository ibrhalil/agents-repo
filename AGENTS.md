# AGENTS.md — LEAN Router (v2.2)
Runtime/model bağımsız küçük yönlendiricidir; kural deposu değildir. Otorite sırası: `SCHEMA.md` > `AGENTS.md` > wiki policy notları ([[agent-policy]]). Ayrıntılı davranış politikaları wiki policy notlarında yaşar.
## 1. Router Prensipleri
- CHEAP FIRST. ESCALATE ONLY ON EVIDENCE. LOAD ONLY THE DELTA CONTEXT. "Belki lazım olur" gerekçesiyle context yüklenmez.
- Sınıflar: CHAT, TRIVIAL_EDIT, LOCAL_CODE, FEATURE, RESEARCH, OPS. Belirsiz görevde en ucuz makul sınıfla başla; kanıt gelince TRIVIAL_EDIT → LOCAL_CODE → FEATURE şeklinde escalate et; escalation'da yüklenmiş context yeniden yüklenmez.
## 2. Context Acquisition
- Default: SEARCH → TARGETED READ → ACT. Önce grep/glob/symbol/path tespiti, sonra yalnız gerekli satır aralığı (offset+limit); yetmezse kademeli genişlet. Full-file read default değildir; yalnız dosya küçükse veya bütün dosya yapısı karar için gerekiyorsa.
- Gereksiz re-read yapma. Mevcut context yeterliyse tekrar okuma. Edit sonrası diff, değişen satırlar ve komşu context kullan. Dosya başka bir işlemle değişmişse, edit sonucu doğrulanamıyorsa veya eksik context karar vermeyi engelliyorsa yalnız gerekli bölümü yeniden oku; full-file re-read yine default değildir.
- Context bütçesi tool output'u da kapsar; `read`/`webfetch`/`task` pahalıdır — sorguyu daralt, hedefli çıktı tercih et.
- Subagent/explore default OFF; yalnız hedefli grep/read yetersiz kaldığında veya bağımsız geniş araştırma gerçekten gerektiğinde. Subagent sonrası aynı alanı primary tarafta sıfırdan yeniden araştırma.
## 3. Wiki (default OFF)
- Kanonik bilgi `wiki/` içindedir; `index/` yalnız türetilmiş gezinme haritasıdır. Kilitli klonda wiki içeriği okunmaz (kurulum: `README.md`).
- Wiki yalnız şu durumlarda açılır: kod cevabı vermiyorsa; domain/repo kararı wiki'ye bağlıysa; kullanıcı özellikle wiki bilgisini istiyorsa; görev gerçek wiki/ingest işiyse.
- Slug biliniyorsa `wiki/<slug>.md` doğrudan read ile açılır; root/hub traversal yapılmaz. Slug bilinmiyorsa: `python3 scripts/noma_wiki.py root --json` → `hub <slug> --json` (varsa `next_page`); belirsiz soru 2-4 kavrama damıtılır ve `s <kavramlar> --json` ile aranır — arama adayı kanıt değildir.
- Wiki dosya adı tahmin edilmez; tüm wiki context'e alınmaz; büyük note'larda da targeted read geçerlidir.
- Ayrıntılı sözleşme: `SCHEMA.md`; erişim/kilit durumu: `README.md`.
## 4. Gizlilik / Stdout Sınırı
- Şifreli dizinlerin (`wiki/ raw/ log/ plans/ index/` vb. — tam liste SCHEMA §1) içerik ve metadata'sı console/stdout'a DÖKÜLEMEZ (bash cat/echo/tee, yanıt metni, log çıktısı).
- CLI yalnız gezinme JSON sinyali üretir: path/slug, `next_page`, arama skoru/eşleşme işareti.
- Açık klonda seçili dosya read aracıyla bağlama açılabilir; yasak olan stdout'a dökmektir ([[r4-stdout-read-ayrimi]]).
## 5. Policy / Board (default OFF)
- `resolve agent-read-policy --json`: RESEARCH sınıfı tek başına tetikleyici DEĞİLDİR; yalnız görev gerçekten policy/izin/kapsam kararı, ingest kapsamı veya hangi kaynakların okunup yazılabileceği konusunda repo policy kararı gerektiriyorsa açılır. Normal mimari araştırma, kod açıklaması ve "bu sistem nasıl çalışıyor?" sorularında policy OFF; normal edit/bugfix öncesi çalıştırılmaz. Policy keşfi `resolve agent-policy --json` ile başlar; konu notu atfı üyelik değildir. Değişmemiş onaylı sürüm yeniden yüklenmez. Eksik/bozuk aktivasyonda worktree policy taslağı yürürlükte sayılmaz (kurulum/kurtarma: `scripts/README.md`).
- Board yalnız kullanıcı açıkça isterse veya uzun/çok aşamalı FEATURE için repo workflow'u zorunlu kılıyorsa ON olur; TRIVIAL_EDIT ve normal LOCAL_CODE'ta başlatılmaz. Board OFF iken write-policy resolve edilmez, `begin` yapılmaz, `scripts/README.md` okunmaz. Board ON'da: `resolve agent-write-policy --json` okunur, `python3 -B scripts/noma_board.py begin <task-key>` → `claim <run-id> <paths...>` → `finish <run-id>`; kullanımı biliniyorsa `scripts/README.md` tekrar okunmaz, yalnız davranış bilinmiyorsa veya komut hata verirse açılır.
- Kaynak ingest veya ilgili not/session'ın içeriksel yeniden ele alınmasında `resolve wiki-kapsam-butunlugu --json` sonucunu read ile aç; eksiksiz bilgi aktarımı/kapsam kontrolü ve eski notların aşamalı uyarlaması uygulanır.
- Salt-okuma/plan görevi kayıt açmaz. Diğer davranış kuralları yalnız ilgili tetikleyicide onaylı `agent-policy` register'ından bulunur ve `resolve <slug> --json` ile açılır; rutin teknik kararları agent verir, önemli ve kaynaktan çözülemeyen belirsizliği sorar.
## 6. Doğrulama (proportional)
- NONE: read-only/açıklama. MINIMAL: diff + syntax/local sanity. TARGETED: değişen alanın ilgili lint/test/typecheck'i. FULL: çok dosyalı/high-risk feature doğrulaması.
- Komutlar: `bash scripts/noma-run-lint.sh` (pre-commit aynı linter'dır); testler `python3 -B -m unittest discover -s scripts -p 'test_*.py'`. Doğrulama için gereksiz dokümantasyon yüklenmez; komut zaten biliniyorsa ek dosya açılmaz.
