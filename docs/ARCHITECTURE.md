# Mimari — Noma Kişisel Asistan Sistemi

Kararlı tasarımın kalıcı kaydı. Mimari değişiklikler `type: decision` kayıtları
olarak wiki'ye işlenir (eski ADR-1..10 numaraları tarihsel referanstır); bu doküman
genel bakışı tutar.

## İlkeler
1. **Markdown source of truth** — index/graph/view'lar yeniden üretilebilir; kendi
   veritabanı formatına kilitlenme yok, Obsidian doğrudan okur.
2. **Runtime-bağımsız çekirdek** — herhangi bir agent'ın "Noma" olması için gereken
   her şey repoda: sözleşmeler (AGENTS/SCHEMA), bilgi hattı, kullanıcı profili
   (`wiki/kullanici-profili.md`), yetenekler.
3. **Git = kontrol mekanizması** — Agent'lar serbestçe çalışır; PR darboğazı yoktur.
   Commit ve conflict çözümü bugün **elle** yapılır: periyodik job henüz kurulmadı,
   tasarım niyeti B5'e bağlı ve kullanıcı onayı gerektirir (ADR-10 Güncellendi).
4. **Token optimizasyonu** — retrieval ucuzdan pahalıya; context bütçeli montaj. Sözleşmeler LLM-optimize edilmiştir.
5. **Local-first dostu, bulut esnek** — direkt çoklu provider + Ollama düğümü (ADR-8).
6. **Gereksiz complexity yok** — yeni katman/alan/dizin gerçek ihtiyaç ister
   (wiki/agent-mimarisi.md §44).

## Bilgi hattı ve retrieval
Üretim tarafı: `raw → wiki` (iki katman; atoms kaldırıldı — [[wiki/agent-yapisi]]).
Sorgu tarafı motor-bağımsızdır:

```text
index.md kök hub yolları (root --json) → şifreli index/hubs/ sayfaları (hub --json)
  → belirsizse metadata filtre + sıralı sözcüksel arama (tam yoksa kısmi aday)
  → seçilen notun frontmatter/Links/Summary'si → gereken gövde bölümü
  → gerektiğinde [[wikilink]] traversal (1-2 hop) → kaynaklı cevap
```

Sabit agent bağlamında yalnız rota bulunur; notlar ihtiyaç anında okunur. Zayıf
aramada hub içinde kısa terimlerle bir kez daha denenir; kısmi eşleşme kanıt
sayılmaz. Kararda `status`, `updated` ve açık supersede bilgisi denetlenir;
oturum/plan özeti yalnız ilgili devam görevine eklenir.

`index.md` yalnız kök hub'ları tutar; `index/hubs/<slug>/<sayfa>.md` dosyaları
wiki `## Links` yönünden yeniden üretilen, şifreli ve sınırlı boyutlu sayfalardır.
Agent `hub --json` ile yalnız istenen sayfayı görür (`next_page` varsa devam eder);
sayfalar en çok 32 yol/16 KiB, kök en çok 8 KiB'dir; dosyalar kanonik değildir.
Serbest metin araması/lint hâlen tüm wiki'yi
tarar; daha büyük ölçekte yerel indeks gereksinimi ayrı ölçülecektir.

Graph/search/embedding mimarisi henüz kararlaşmadı (`wiki/agent-talimati.md`
§45-8/9) — belirli motor varsayılmaz. Epistemik hijyen: her cevap kaynak path'iyle atıflı (`wiki/slug.md`,
`raw/...`); `unverified → established` yükseltmesi ikinci bağımsız kaynak ya da
insan onayı ister.

## Görünürlük ve güvenlik
Repo bilinçli public (ADR-7): kod/mimari/dokümantasyon açık; kişisel knowledge
git-crypt ile şifreli (`index.md`, `index/ raw/ wiki/ agent/prompts/ agent/sessions/ plans/
log/`; `tmp/` yerel/gitignore — şifrelenmez). Kabul edilen sızıntı şifreli blob metadata'sıdır; fact-düzeyi kişisel
veri yol adlarında bile yaşamaz. Hassas kapsam yalnız yerel model
(ADR-8); prompt injection savunması katmanlı (ADR-9).

## Düğümler
Düğüm = bu repoyu sözleşmeye bağlı kullanan her agent/model (kayıt dizini
`docs/nodes/` 2026-09-23'te kaldırıldı; düğüm envanteri bu bölümde yaşar).
- **Laptop (aktif):** opencode — etkileşimli geliştirme düğümü.
- **Noma düğümü (home Proxmox QEMU VM — mevcut plan, henüz kurulmadı):**
  canlı ajan runtime'ı. VPS düğümünden bu plana döndü; kanonik yol
  `wiki/proxmox-noma-kurulum.md` ve `wiki/noma-hermes-vm-docker.md`.
- **Bulut Hermes (public-only/read-only mount, devam eden kısıt):** yalnız public
  `AGENTS/SCHEMA/README/docs/scripts` okur; şifreli wiki, indeks, `.env` ve Git
  kimliği bu konteynerde bulunmaz. Özel bilgi işi yerel düğümü bekler. Önceki
  tam-klon Hermes mount'u güvenlik nedeniyle kaldırıldı.
- **Ev Ollama provider (planlı):** aynı repo klonu, aynı SCHEMA.
- **İnsan düğümü:** Obsidian ile `wiki/` doğrudan düzenleme (kurulum:
  `docs/obsidian-recommended.md`).
- **Senkron:** git; yetkili yerel düğümler serbest yazar. Commit ve conflict
  çözümü bugün elle yapılır — periyodik job **yok**; hedef `docs/ROADMAP.md` B5
  (karar: `wiki/git-akisi-ve-conflict.md`, 2026-09-23). Append-only tasarım
  çoklu yazıcıda çatışmaları seyrekleştirir; lint `log/` append-only kuralını
  HEAD'e ve **staged içeriğe** karşı denetler, silinmesi stage edilen yolları
  yakalar ve commit edilecek tüm özel blob'ların gerçekten şifreli olduğunu
  doğrular (linter aynı zamanda pre-commit kancasıdır).

Bulut Hermes home'u `~/.hermes-cloud` ile eskisinden ayrıdır;
eski `~/.hermes` hafızası/cron'u otomatik olarak taşınmaz. `pre_llm_call` hook'u
yalnız statik gezinme talimatı verir; yerel model ilgili hub'ı ihtiyaç anında
dosyadan okur. Sağlayıcı API anahtarı Hermes işlem ortamında kalır; tool
işlemlerinden ayrıca izole edilmesi için provider proxy/araç sınırı gerekir.

## Faz durumu
Canlı yol haritası (kalan işler + tamamlanan fazlar): `docs/ROADMAP.md`.

## Teknoloji gerekçeleri (özet)
- **Hermes (Noma düğümü runtime adayı):** agent loop / zamanlanmış iş / gateway / model
  yönetimi yeniden yazılmaz; özel geliştirme bilgi sistemine odaklanır. Sıfırdan
  runtime değerlendirildi ve reddedildi (aylarca sürecek, tek kişi için bakımsız).
- **MCP:** taşınabilirlik katmanı adayı; nihai kullanımı/sınırları henüz kararlaşmadı
  (§45-11) — ihtiyaç yokken katman eklenmez.
- **git-crypt:** kişisel veri için; retrofit git history yeniden yazma gerektirdiğinden
  günden bir kuruldu.
- **graph/index üretimi:** küçük `index.md` kökü ve sayfalı `index/hubs/` haritaları
  `scripts/noma_build_index.py` ile wiki `## Links` yönünden deterministik üretilir;
  graph ile genel/semantik arama motoru hâlâ ayrı tasarım konusudur.
- **Kanonik profil wiki'de:** Hermes yerleşik hafızası düğüm-lokal olduğundan çok
  düğümlü senaryoda kanonik profil repoda taşınır; `memories/` dizini 2026-09-23'te
  kaldırıldı — profil `wiki/kullanici-profili.md` olarak yaşar, tüm düğümlere
  şifreli sync olur.
- **forgesys aktarımları:** plan dosyası protokolü (resume + step contract), ROADMAP,
  dondurulmuş karar kuralı, dokümantasyon satır bütçeleri ve dil politikasının token
  optimizasyonu gerekçesi — olgun bir çok-agent deposundan (forgesys) devralındı.

Kök: [[index]]
