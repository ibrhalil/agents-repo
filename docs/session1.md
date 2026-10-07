# Agent Context Yapısı: İkinci Beyin Kurulum Rehberi

Önerim, **düz markdown dosyalarından oluşan, git ile versiyonlanan bir "vault"** kurmak. Agent'ın tek işi bu dosyaları okumak ve yazmak olursa hangi modelle çalışırsa çalışsın aynı hafızayı kullanır. Notları da sen okuyup düzeltebilirsin.

## Temel prensipler

1. **Düz markdown + YAML frontmatter.** Hiçbir modele veya araca bağımlı değil.
2. **Tek kaynak, ince adaptörler.** Asıl talimatlar `AGENTS.md` içinde durur. `CLAUDE.md`, `GEMINI.md` gibi dosyalar sadece "AGENTS.md'yi oku" der.
3. **Kademeli yükleme.** Her oturumda yalnızca küçük bir çekirdek okunur. Gerisi `index.md` üzerinden gerektiğinde açılır.
4. **Katmanları ayır.** Kurallar nadiren değişir, hafıza sık güncellenir, oturum logları sadece eklenir, ham kaynaklar ayrı durur.
5. **Önce ham, sonra işlenmiş.** Agent oturum sırasında log tutar, kalıcı notlara aktarma ise oturum sonunda veya periyodik konsolidasyonla olur.

## Klasör yapısı

```
brain/
├── AGENTS.md                  # giriş noktası: açılış/kapanış protokolü
├── CLAUDE.md, GEMINI.md       # sadece "AGENTS.md'yi oku" adaptörleri
├── core/                      # nadir değişir, onay gerektirir
│   ├── identity.md            # agent'ın rolü, tonu, dili
│   ├── rules.md               # yapılacaklar / yapılmayacaklar, yetkiler
│   ├── user-profile.md        # senin hakkında kalıcı bilgiler, tercihler
│   └── note-format.md         # not şablonları ve yazma kuralları
├── memory/                    # agent'ın serbestçe güncellediği hafıza
│   ├── index.md               # her şeyin haritası (agent bakımını yapar)
│   ├── projects/
│   │   └── proje-adi/
│   │       ├── _index.md      # durum, sıradaki adımlar, açık sorular
│   │       ├── decisions.md
│   │       └── alt-konu.md    # alt notlar
│   ├── areas/                 # sağlık, finans, iş, öğrenme...
│   ├── people/
│   └── topics/                # genel bilgi notları
├── sessions/
│   └── 2026-10-06-1958-konu.md   # her oturum için bir log
├── sources/                   # ham kaynaklar: link, alıntı, dosya + metadata
├── inbox.md                   # sınıflandırılmamış notlar, core değişiklik önerileri
└── archive/                   # silinmez, buraya taşınır
```

## AGENTS.md iskeleti

```markdown
# Açılış protokolü (her oturumda)
1. core/identity.md, rules.md, user-profile.md dosyalarını oku.
2. memory/index.md'yi oku.
3. Konu belliyse ilgili proje/alan notunun _index.md dosyasını
   ve sessions/ altındaki son 2 logu oku.
4. Neyi okuduğunu tek cümleyle belirt, sonra göreve geç.

# Oturum sırasında
- Yeni bilgi, karar ve kaynakları aklında tut, tahmin etme.
- Emin olmadığın bir şeyi "doğrulanmadı" diye işaretle.

# Kapanış protokolü (oturum bitince veya "kaydet" denince)
1. sessions/ altına log yaz (şablon: note-format.md).
2. Etkilenen notları güncelle. Silme, archive/ altına taşı.
3. Büyüyen notu alt notlara böl (aşağıdaki kurala bak).
4. memory/index.md'yi güncelle.
5. Sonraki oturum için "Devam noktası" bölümünü yaz.

# Yetkiler
- sessions/, memory/, sources/, inbox.md: serbestçe yaz.
- core/: doğrudan değiştirme, inbox.md'ye öneri olarak yaz.
```

## Not formatı ve alt notlar

```markdown
---
id: proje-x
type: project        # project | area | person | topic | decision | session
status: active       # active | paused | done | archived
created: 2026-10-06
updated: 2026-10-06
parent: memory/projects/_index.md
tags: [ai, agent]
sources: [sources/2026-10-06-makale.md]
confidence: high     # kullanıcı belirtti = high, çıkarım = low
---

## Özet
## Güncel durum
## Kararlar
## Açık sorular
## Alt notlar
- [[proje-x/mimari]]
```

**Alt not kuralı (agent'a yazdır):**

- Bir not yaklaşık 300 satırı aşarsa veya içinde bağımsız bir alt konu oluşursa, notu klasöre dönüştür: `proje-x.md` → `proje-x/_index.md`.
- Alt konuyu ayrı dosyaya taşı, ana nota sadece özet ve link bırak.
- Taşıdığın her şeyi `index.md` içine ekle.

### Oturum logu şablonu

```markdown
---
type: session
date: 2026-10-06
model: claude-sonnet-5-5   # hangi model yazdı
topic: ...
---
## Hedef
## Yapılanlar
## Kararlar
## Güncellenen notlar
## Kaynaklar
## Devam noktası (bir sonraki oturum buradan başlasın)
```

## Farklı modeller ve versiyonlarla çalışma

- **Çekirdeği küçük tut.** `core/` toplamı yaklaşık 2-3 bin token'ı geçmesin. Böylece bağlam penceresi küçük bir model de çalışabilir.
- **Kuralları kısa ve emir kipinde yaz.** Zayıf modeller de uygulayabilir. Örnek verirken tek bir net örnek yeterli.
- **Her oturum logunda `model:` alanını tut.** Bir modelin yazdığı notlarda tutarsızlık görürsen kaynağını bulabilirsin.
- **"Devam noktası" bölümü model geçişinin köprüsüdür.** Yeni model tüm geçmişi okumak zorunda kalmaz.
- **Modele özgü ayarları ayrı tut.** Gerekirse `core/adapters/claude.md` gibi dosyalarda "bu model şunu fazla yapıyor, şuna dikkat et" notları yaz. Ana kurallara karıştırma.
- **Araca özgü özelliklere bağımlı olma.** Hiçbir model özel bir hafıza özelliğine ihtiyaç duymasın. Gereken tek yetenek dosya okuma ve yazma. Bunu Claude Code gibi bir agent ortamı, bir MCP filesystem sunucusu veya kendi yazacağın ince bir sarmalayıcı sağlayabilir.
- **Yeni model çıkınca küçük bir test yap.** Aynı oturumu açıp protokolü doğru uygulayıp uygulamadığına bak.

## Hafıza hijyeni

- **Silme, arşivle.** Yanlış bilgi yazılırsa geri dönebilirsin. Git bunun için ayrıca emniyet sağlar.
- **Kişisel bilgiye kaynak ve tarih ekle.** "Kullanıcı X'i tercih ediyor (2026-10, kullanıcı söyledi)." Çıkarımları `confidence: low` yap.
- **Çelişkide yeni bilgi kazanır, eskisi değişiklik geçmişinde kalır.**
- **Haftalık konsolidasyon oturumu yap.** Agent'a "inbox'ı sınıflandır, tekrarları birleştir, bayat notları arşivle, index'i yenile" görevini ver.
- **Sır koyma.** Şifre, API anahtarı, kimlik bilgisi vault'a girmesin. Vault'u bulutta tutuyorsan hassas alanları (`sağlık`, `finans`) ayrı ve şifreli tut.