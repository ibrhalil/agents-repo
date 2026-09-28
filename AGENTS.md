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
Repo-geneli davranış kuralları (veri bütünlüğü, güvenlik, atıf doğrulama, bakım, test fixture, ingest vb.) ihtiyaç halinde `wiki/agent-policy.md` register'ından bulunur.
