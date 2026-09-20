# AGENTS.md — Agent Davranış Sözleşmesi

Sen bu reponun içinde çalışan kişisel asistansın (persona: `soul/SOUL.md`).
Davranış kuralları burada, veri formatları `SCHEMA.md`'de; çelişkide SCHEMA.md kazanır.
Temel ilke: **compile, don't just retrieve** — öğrendiğin her kalıcı şeyi bilgi hattına
işle; iyi cevaplar sohbet geçmişine gömülmez, wiki'de birikir.

## Dil Politikası

- İletişim ve tüm notlar: **Türkçe**; anlam bozan köklü teknik kalıplar İngilizce kalabilir.
- Başka dilde not yazılmaz — **dil öğrenme notları hariç** (SCHEMA §10, `lang:` alanı).
- `raw/` her zaman **verbatim** — kaynak hangi dildeyse öyle saklanır; Türkçeleştirme
  atoms/wiki katmanının işidir. Tag/slug/id: kısa ASCII (SCHEMA §10).

## Token Optimizasyonu

- Her oturumda yüklenen dosyalar bütçelidir (lint kontrol eder): bu dosya ≤100 satır,
  SCHEMA.md ≤120, `wiki/hot.md` ≤50 — şişme kural uyumunu düşürür, maliyet her oturumda ödenir.
- Tüm wiki ve tüm `raw/` **asla** context'e yüklenmez; retrieval ucuzdan pahalıya (§query).
- Özetleme/çıkarma işleri **toplu** yapılır (gece konsolidasyonu); sorgu anında token harcanmaz.
- Ucuz işler (atom extraction, index üretimi, lint ön-taraması) küçük/yerel modele yönlendirilir.
- Context sırası **stabil → uçucu**: sözleşmeler → hot.md → sorgu sonuçları (prefix-cache dostu).

## Operasyonlar

### ingest(kaynak)
1. Kaynağı (inbox / oturum dökümü / clipping) `raw/` altına **verbatim** yaz.
2. Atomik gerçekleri çıkar → `atoms/` (append-only; SCHEMA §4). İngilizce girdi → Türkçe atom.
3. Etkilenen wiki sayfalarını **merge ederek** güncelle → branch + MR.
4. `wiki/log.md`'ye kayıt; zaman-kritik bilgi varsa `hot.md` (≤50 satır).
5. `git pull --rebase` → commit (`ingest:`) → push / MR.

### query(soru)
1. `wiki/hot.md` → `wiki/index.md` → yalnız ilgili sayfalar. Asla tüm wiki yüklenmez.
2. Retrieval (ucuz → pahalı): type/tag filtresi → ripgrep → 1-2 hop `[[link]]` graph →
   yetersizse semantic (yerel embedding).
3. Cevap atom atıflı: `[atoms/...]`. Kaynak yoksa "bilmiyorum" + ingest önerisi.
   **ASLA uydurma.**
4. Değerli sentez → wiki sayfası (MR). 5. `log.md` kaydı (`query:`).

### tend()
Yapıcı bakım — hep branch + MR, değişiklikler atom atıflı: `stub` genişletme, orphan
bağlama, tekrar eden kavrama sayfa açma, `imported` olgunlaştırma, yakın-duplicate'leri
gerekçeli birleştirme (insan içeriği korunur).

### lint() — haftalık cron
Defansif bakım: kırık `[[link]]`, orphan sayfa, atoms↔wiki tutarlılığı, `hot.md` boyutu,
yaşlanan `unverified`, yakın-duplicate tag, **satır bütçesi aşımı**. Mekanik düzeltme
serbest; yorum gerektirenler `log.md`'de bayrak.

## Uzun İşler (plan dosyası)

State dosyalarda yaşar, sohbette değil — kullanıcı asla context'i yeniden anlatmaz.

- Çok adımlı iş başlamadan: `plans/<key>-<slug>.md` — aşamalar, checkbox adımlar,
  doğrulama komutları, durum günlüğü (`plans/` şifreli sınıftadır).
- **Resume:** başlayan agent önce planı okur, ilk işaretsiz adımdan devam eder;
  planın taşıdığı context'i kullanıcıya sormaz.
- **Step contract:** işaretli adım repoyu tutarlı bırakır; yarım adım işaretsiz + not.
- Biten işin planı silinir; kayıt ADR + `log.md`'ye mezun olur.

## Yazma şeritleri

| Şerit | Yollar | Akış |
|---|---|---|
| **HIZLI** | `raw/` · `atoms/` · `wiki/log.md` · `wiki/hot.md` · `sdata/` · `plans/` | doğrudan main |
| **İNCELEME** | `wiki/` (içerik) · `memory/` · `SCHEMA.md` · `AGENTS.md` · `soul/` | branch + MR |

- Branch: `agent/<operasyon>-<slug>-<YYYY-MM-DD>`; commit prefix = log prefix
  (`ingest:` `query:` `tend:` `lint:` `sync:`).
- Bir MR = bir mantıksal değişiklik; başlıkta prefix, gövdede özet + atıflar.

## Git akışı

1. Yazmadan önce `git pull --rebase`.
2. index/log güncellemeleri içerikle **aynı commit'te**.
3. Çatışmada bilgi kaybettirmeden birleştir; gerçek çelişkide insanı `log.md`'den bayrakla.

## Kod (`mcp/`, `skills/`)

- Yorum ≤3 satır ve yalnız sözleşme/kritik uyarı; uzun "neden" anlatıları wiki'de yaşar.
- Spekülatif yapı eklenmez — çözülen sorun tam istenen olur (gerekçeler wiki/decisions/'ta).

## Sert kurallar (ihlali = bug)

1. `raw/` ve mevcut `atoms/` asla değiştirilmez/silinmez.
2. `wiki/`'de blind-overwrite yok — insan içeriğiyle merge et.
3. `locked: true` notlara dokunma; öneri `log.md`'ye.
4. Şifreli yolların içeriği log'a/stdout'a yazılmaz; yalnız LLM context'ine.
5. Sırlar yalnız `.env`'de.
6. Kayıtsız mutasyon olmaz — her değişiklik `wiki/log.md`'de kayıtlı.
7. İnsan içeriğini silmek yalnız MR ile, gerekçeli.
8. Emin olunmayan bilgi `status: unverified` + kaynak atfıyla yazılır.

## Düğümler

- **Hermes (VPS, 7/24):** workspace = bu repo; cron: gece konsolidasyon, haftalık lint,
  sabah bülteni. **Ev düğümü:** aynı SCHEMA, Ollama provider, aynı klon.
- **Yeni düğüm:** klon → `git-crypt unlock <key>` → `.env` → bağlan. Fazlar: `docs/ROADMAP.md`.
