> **Tarihsel belge (2026-09):** Bu rapor eski 3-katmanlı yapıyı (atoms katmanı,
> `soul/`, `sdata/`, `hot.md`) tarif eder — güncel mimariyle çelişir. Güncel durum:
> `docs/ARCHITECTURE.md` ve `plans/yeni-agent-yapisi.md`.

Bağ: [[index]] · [[wiki/yeni-agent-yapisi|Yeni Agent Yapısı]]

# agents-repo (Noma) — Kapsamlı Analiz ve Öneriler (2026-09)

## Genel Değerlendirme

Bu repo, "kişisel ikinci beyin" konseptinin oldukça olgun ve bilinçli bir tasarımı. Özellikle üç katmanlı bilgi hattı (`raw → atoms → wiki`), ADR kültürü, git-crypt güvenlik modeli, token optimizasyonu farkındalığı, plan dosyası protokolü ve prompt injection savunmaları çok güçlü yönler.

## Tespit Edilen Boşluklar ve Öneriler

### A. Mimari / Yapısal
- **Ö1:** `wiki/decisions/İki Şeritli Yazma ve MR.md` (ADR-2) tutarsızlığı. ADR-10 ADR-2'yi supersede ediyor ama işaretli değil. `superseded_by: 10` alanı eklenmeli.
- **Ö2:** `sdata/README.md` "hızlı şerit" referansı. ADR-10 HIZLI şeridi kaldırdı, ancak `sdata/` agent'ın programatik yazdığı tek yer. İstisna netleştirilmeli.
- **Ö3:** `wiki/issues/` ve `wiki/tasks/` boş ama index.md'de listelenmiyor. İskelet tutarlılığı için placeholder eklenebilir.
- **Ö4:** Atom ID üretim kuralı eksik. Düğüm prefixi (`a-H-0007`) tanımlanmalı, çakışmalar önlenmeli.
- **Ö5:** `wiki/people/` boş — profile.md ilişkisi netleştirilmeli.

### B. Güvenlik
- **Ö6:** `.gitattributes` `soul/` şifreleme + SOUL.md erişilebilirlik çelişkisi. Yeni bir düğüm unlock etmeden okuyamaz.
- **Ö7:** `.env.example` → `Z_AI_BASE_URL` veya `ANTHROPIC_BASE_URL` eklenmeli.
- **Ö8:** Branch protection hâlâ MANUEL. ADR-10'un güvencesi için hemen aktif edilmeli.

### C. Operasyonel
- **Ö9:** `log.md` ölçekleme sorunu. Aylık/çeyreklik rotasyon düşünülmeli.
- **Ö10:** `hot.md` → `cold.md` geçiş mekanizması yok. Taşma durumu için `tend()` operasyonuna kural eklenmeli.
- **Ö11:** `raw/conversations/` adlandırma çakışma riski. Saniye veya suffix (`YYYY-MM-DD-HHmmss.md`) eklenmeli.
- **Ö12:** Konsolidasyon (gece cron) operasyonu tanımsız. `tend()` ve `ingest()` birleşimi olarak açıklanmalı.

### D. Bilgi Hattı ve Retrieval
- **Ö13:** Atom → Wiki bağlantısı tek yönlü. Atom kullanım haritası çıkarılmalı.
- **Ö14:** `wiki/resources/` boş ama SCHEMA §10'da geçiyor. İskelet oluşturulmalı.
- **Ö15:** Frontmatter `scope:` alanı eski kararlarda eksik.

### E. Çok Düğüm ve Senkronizasyon
- **Ö16:** Çatışma çözüm stratejisi detaysız. Katman bazlı politika tanımlanmalı.
- **Ö17:** Düğüm kimliği (node identity) yok. `log.md` için `@hermes` gibi belirteçler konulmalı.

### F. Obsidian Entegrasyonu
- **Ö18:** `.obsidian/` gitignore'da ama vault ayarları paylaşılmıyor. `docs/obsidian-recommended.md` hazırlanabilir.
- **Ö19:** Wikilink `[[Başlık]]` ↔ Obsidian uyumu için ayarlar belgelenmeli.

### G. Token ve Maliyet
- **Ö20:** AGENTS.md + SCHEMA.md her oturumda yükleniyor. Büyüdükçe kompakt versiyon gerekecek.
- **Ö21:** `memory/profile.md` her oturumda yüklenmek yerine MCP'den çekilebilir.

### H. Eksik Ama Roadmap'te Olan
- **Ö22:** Kritik Faz 2 bağımlılıkları (MCP knowledge sunucusu) ertelenmemeli.
