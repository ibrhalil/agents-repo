---
name: llm-wiki
description: LLM tarafından sürekli inşa edilen ve güncellenen kalıcı, birikimli bir bilgi arşivi (persistent wiki) deseni. Standart RAG'ın aksine her sorguda bilgi yeniden keşfedilmez — ajan yeni kaynakları okur, mevcut wiki'ye entegre eder, varlık/kavram sayfalarını günceller, çelişkileri işaretler, çapraz-referansları korur. Herhangi bir alan için kullanılır: araştırma, kitap okuma, ürün geliştirme, takım bilgisi, kişisel gelişim, rekabet analizi, ders notları. Obsidian + LLM ajanı (Claude Code, Codex, vb.) ile çalışır. Kullanıcı kaynakları bulur, ajan tüm bookkeeping'i yapar.
---

# LLM Wiki — Kalıcı Bilgi Arşivi Deseni

## Çekirdek fikir

LLM'lerle belge çalışmanın standart yolu **RAG**'tir: belgeleri yüklersin, sorduğunda ilgili parçalar çekilir, cevap üretilir. Çalışır ama her sorguda bilgi sıfırdan yeniden keşfedilir. Hiçbir şey birikmez. İncelikli bir soru sorduğunda — beş kaynağı sentezlemen gereken bir soru — LLM her seferinde parçaları yeniden bulup birleştirmek zorunda kalır.

Bu skill **farklı bir yaklaşım** uygular. Ham kaynaklardan sorgu zamanında çekmek yerine, LLM seninle ham kaynaklar arasında **kalıcı bir wiki**'yi artımlı olarak inşa eder ve bakımını yapar. Yeni bir kaynak eklediğinde ajan onu sadece indekslemez — okur, çıkarımları konuşur, mevcut wiki'ye entegre eder, varlık sayfalarını günceller, yeni veri eski iddialarla çeliştiğinde işaretler, sentezi güçlendirir.

**Kritik fark**: wiki, derlenmiş ve güncel tutulan **kalıcı, birikimli bir artefakt**tır. Çapraz-referanslar zaten oradadır. Çelişkiler zaten işaretlenmiştir. Sentez, okuduğun her şeyi zaten yansıtır. Her yeni kaynak ve her yeni soruyla wiki daha da zenginleşir.

## Rol dağılımı

| Sen | LLM |
|---|---|
| Kaynakları bulur ve toplar | Okur, özetler, dosyalar |
| Hangi soruları soracağını belirler | Çapraz-referansları korur |
| Analizi yönlendirir | Çelişkileri işaretler |
| Sonuçları okur, eleştirel düşünür | Bookkeeping (asla unutmaz, sıkılmaz) |
| Şemayı evriltir | Şemaya uyar |

Pratikte: bir tarafta Obsidian açık, diğer tarafta LLM ajanı. Sen sohbet ederken o vault'u düzenler, sen Obsidian'da graph view ile sonuçları takip edersin. **Obsidian = IDE, LLM = programmer, wiki = kod tabanı.**

## Üç katman mimari

### 1. Ham kaynaklar (`raw/`)
Makaleler, PDF'ler, podcast notları, toplantı transkriptleri, resimler, veri dosyaları, JSONL transkriptleri. **Asla değiştirilmez.** Ajan sadece okur, yazmaz. Gerçeğin kaynağı budur.

### 2. Wiki (vault root)
LLM'in tamamen sahiplendiği markdown dosyaları. Özetler, varlık sayfaları, kavram sayfaları, karşılaştırmalar, kararlar, sentez. Sayfalar `[[bağlantı]]`larla birbirine bağlanır. LLM bu katmanı tamamen yönetir — sayfa oluşturur, günceller, çapraz-referansları tutarlı tutar. Sen okursun, LLM yazar.

### 3. Şema (`CLAUDE.md` veya `AGENTS.md`)
Ajana wiki'nin nasıl yapılandırıldığını, hangi konvansiyonlara uyacağını, her operasyonda hangi iş akışını izleyeceğini söyleyen doküman. **En kritik dosya budur** — ajanı disiplinli bir wiki bakımcısına dönüştürür, genel amaçlı bir chatbot olmaktan çıkarır. Sen ve ajan birlikte zamanla evriltirsiniz.

## Üç operasyon

### INGEST — kaynak emme

Ham klasöre yeni bir kaynak koyarsın ve "bunu işle" dersin. Ajan adımları:
1. Kaynağı okur
2. Anahtar çıkarımları seninle tartışır
3. `sources/` altında bir özet sayfası yazar
4. `index.md`'yi günceller
5. İlgili `entities/` ve `concepts/` sayfalarını çapraz-günceller
6. Tutarsızlık varsa işaretler
7. `log.md`'ye zaman damgalı bir giriş ekler

Tek bir kaynak 10-15 wiki sayfasına dokunabilir. **Tercih meselesi**: kaynakları tek tek yakın gözetimle mi, yoksa toplu halde daha az gözetimle mi ingest edersin. İkisi de geçerli — şemana yaz.

### QUERY — sorgu

Wiki'ye soru sorarsın. Ajan:
1. `index.md`'yi okur
2. İlgili sayfaları bulur ve içlerini okur
3. Cevabı sentezler — cümle, tablo, slayt, grafik, canvas, ne uygunsa
4. Cevapta her iddia için kaynak referansı verir

**Kritik içgörü**: İyi cevaplar wiki'ye **yeni sayfa olarak geri dosyalanır**. İstediğin bir karşılaştırma, keşfettiğin bir bağlantı, yaptığın bir analiz — bunlar değerlidir ve sohbet geçmişinde kaybolmamalı. Böylece keşiflerin de bilgi birikimini büyütür, tıpkı ham kaynaklar gibi.

### LINT — sağlık kontrolü

Periyodik olarak ajana wiki sağlık kontrolü yaptırırsın. Kontrol edilenler:
- Sayfalar arası **çelişkiler**
- Yeni kaynaklarla geçersiz kalmış **stale claim**'ler
- Hiçbir yerden link almayan **orphan** sayfalar
- Wiki'de geçen ama kendi sayfası olmayan kavramlar
- Eksik veya tek yönlü çapraz-referanslar
- Web araması ile doldurulabilecek **veri boşlukları**

LLM bu pass sırasında **araştırılacak yeni sorular ve yeni kaynaklar da önerir**. Wiki'yi büyürken sağlıklı tutar.

## index.md ve log.md

Wiki büyüdükçe iki özel dosya hayati hale gelir.

### `index.md` — içerik odaklı
Wiki'deki her şeyin kataloğu. Her sayfa için: link, tek satır özet, opsiyonel metadata (tarih, kaynak sayısı, durum). Kategoriye göre organize: varlıklar, kavramlar, kaynaklar, kararlar. Ajan **her ingest'te günceller**. Sorgu zamanında ajan önce index'i okur, sonra ilgili sayfalara iner.

**Önemli**: orta ölçekte (~100 kaynak, ~birkaç yüz sayfa) bu yaklaşım embedding tabanlı RAG altyapısına olan ihtiyacı **ortadan kaldırır**. Büyürse `qmd` gibi yerel arama motorları eklenebilir.

### `log.md` — zamansal
Append-only olay kaydı. Her ingest, query (özellikle filed-back olanlar) ve lint pass buraya zaman damgalı yazılır.

**İpucu**: Her giriş tutarlı bir prefix ile başlasın:
```
## [2026-04-13] ingest | Makale Başlığı
## [2026-04-13] query | "X nasıl çalışıyor?" → filed: comparisons/x-vs-y.md
## [2026-04-14] lint | 3 stale claim, 2 orphan
```
Böylece basit unix araçlarıyla parse edilir:
```bash
grep "^## \[" log.md | tail -10
```

## Örnek vault yapısı

```
vault/
├── CLAUDE.md           # şema (anayasa)
├── index.md            # içerik kataloğu
├── log.md              # zamansal kayıt
├── raw/                # ham kaynaklar (DOKUNULMAZ)
│   ├── articles/
│   ├── papers/
│   ├── transcripts/
│   └── assets/         # resimler, PDF'ler
├── sources/            # her ham kaynak için bir özet sayfası
├── entities/           # kişiler, ürünler, yerler, organizasyonlar
├── concepts/           # soyut kavramlar, terimler, fikirler
├── decisions/          # kararlar ve gerekçeleri
└── syntheses/          # üst düzey sentez sayfaları
```

Bu yapı **zorunlu değil**. Alanına göre uyarlanır:
- **Kişisel günlük**: `entries/`, `themes/`, `people/`
- **Kitap okuma**: `chapters/`, `characters/`, `themes/`, `quotes/`
- **Araştırma**: `papers/`, `theories/`, `methods/`, `experiments/`
- **Ürün**: `features/`, `bugs/`, `decisions/`, `users/`

## Kullanım alanları

- **Kişisel**: hedefler, sağlık, psikoloji, öz gelişim. Günlük girişleri, makaleler, podcast notları → zamanla kendin hakkında yapılandırılmış bir resim.
- **Araştırma**: bir konuda haftalar veya aylar boyunca derinlemesine — makaleler, raporlar, evrilen bir tez.
- **Kitap okuma**: bölüm bölüm dosyala, sonunda kişisel bir Tolkien Gateway. Karakterler, temalar, olay örgüsü, bağlantılar.
- **İş / takım**: Slack thread'leri, toplantı transkriptleri, müşteri görüşmeleri. LLM bakımı yapar, takımda kimsenin yapmak istemediği bookkeeping'i halleder.
- **Rekabet analizi, due diligence, seyahat planlama, ders notları, hobi araştırması** — zamanla bilgi biriktirmek istediğin her şey.

## Şema dosyası (CLAUDE.md) nasıl yazılır

Şema dosyası wiki'nin **anayasasıdır**. En az şunları içermeli:

1. **Amaç**: Bu wiki hangi alanda? Hangi sorulara cevap arıyor?
2. **Klasör yapısı**: Her klasörün ne içerdiği ve ne içermediği.
3. **Sayfa formatı**: Frontmatter alanları (tags, source, date, status), başlık sırası, link konvansiyonları.
4. **Naming convention**: Sayfa isimleri kebab-case mi snake_case mi? Varlık isimleri nasıl kanonikleştirilir?
5. **Ingest workflow**: Yeni kaynak geldiğinde adım adım ne yapılır, hangi sayfalar otomatik güncellenir.
6. **Query workflow**: Soru geldiğinde önce hangi dosyalar okunur? Cevap nereye filed-back olur?
7. **Lint workflow**: Hangi sağlık kontrolleri ne sıklıkta? Ne otomatik düzeltilir, ne sadece raporlanır?
8. **Yasaklar**: Ajanın **asla** yapmaması gerekenler — `raw/`'a yazmak, kaynaksız iddia yaratmak, mevcut linkleri çözmeden kullanmak, sayfa silmek (sadece archive).
9. **Evrim notu**: Bu şema zamanla değişir — değişiklik geldiğinde önceki sayfalara nasıl uyarlanır.

## Pratik ipuçları

- **Obsidian Web Clipper**: Tarayıcı eklentisi, web sayfalarını markdown'a çevirir → `raw/articles/`'a koy → ajana ingest ettir.
- **Resimleri yerele indir**: Obsidian Settings → Files & links → "Attachment folder" = `raw/assets/`. Hotkey ata ("Download attachments for current file"). LLM sonra resimlere de bakabilir.
- **Graph view**: Obsidian'ın en değerli özelliği. Wiki'nin şeklini görsel olarak görürsün — hub'lar, yetim sayfalar, kümeler. Sağlık kontrolü için vazgeçilmez.
- **Marp plugin**: Wiki sayfalarından doğrudan slayt deck'i üret. Sunum için.
- **Dataview plugin**: Frontmatter üzerinde sorgu çalıştır. Dinamik tablolar, listeler.
- **Git**: Wiki bir git repo. Versiyon tarihi, branch'leme, çakışmasız işbirliği bedava.
- **Arama**: `index.md` orta ölçekte yeter. Büyürse `qmd` gibi yerel BM25+vektör arama motorları eklenebilir.

## Neden çalışır

Bir bilgi arşivi yönetmenin zor kısmı okumak ya da düşünmek değildir — **bookkeeping**'tir. Çapraz-referansları güncellemek, özetleri taze tutmak, çelişkileri yakalamak, onlarca sayfa arasında tutarlılık korumak. İnsanlar wiki'leri terk eder çünkü **bakım yükü değerden hızlı büyür**. LLM'ler sıkılmaz, bir referansı güncellemeyi unutmaz, tek bir pass'te 15 dosyaya dokunabilir. **Wiki bakımlı kalır çünkü bakımın maliyeti neredeyse sıfırdır.**

Senin işin: kaynak bulmak, analizi yönlendirmek, iyi sorular sormak, ne anlama geldiğini düşünmek. LLM'in işi: diğer her şey.

Bu desen ruhen Vannevar Bush'un 1945'teki **Memex** vizyonuna yakındır — kişisel, aktif olarak küratörlenmiş bilgi deposu, belgeler arasında çağrışımsal izler. Bush'un çözemediği tek şey kimin bakım yapacağıydı. LLM o kısmı halleder.

## Hard rules

1. **`raw/` immutable.** Ajan sadece okur, asla yazmaz/değiştirmez. Sadece kullanıcı ekler.
2. **Her iddia kaynaklı.** Wiki'deki her önemli cümle, hangi raw dosyadan geldiğini belirtir. Kaynaksız iddia yasaktır.
3. **Çelişki silinmez, işaretlenir.** "Kaynak A şunu derken, kaynak B bunu diyor" → görünür yere yazılır, ileride çözülür.
4. **Çift-yönlü bağlantı düşüncesi.** Bir sayfayı güncellerken ona link veren diğer sayfaları kontrol et.
5. **Her operasyon log'lanır.** Ingest, anlamlı query'ler ve lint pass'leri zaman damgalı `log.md`'ye gider.
6. **Schema co-evolves.** Bir kural çalışmıyorsa şemayı güncelle. Sonraki oturumlarda yeni kurallar geçerli olur.
7. **Filed-back her şey atomic olur.** Bir query cevabını wiki'ye dosyalarken, sentez tek bir "session özeti" değil ayrık atomik sayfalardır (her biri tek bir fikir).
8. **Sayfa silinmez, archive edilir.** Stale veya hatalı sayfa önce `archive/` altına taşınır, sonra index güncellenir. Tarih korunur.

## İlk çalıştırma adımları

Yeni bir vault için ajana şunları söyle:

1. Klasör yapısını kur (`raw/`, `sources/`, `entities/`, `concepts/`, `decisions/`)
2. `index.md` ve `log.md` iskelet dosyalarını oluştur
3. `CLAUDE.md`'yi bu skill'i temel alarak yaz — alana özgü bölümleri ekle (amaç, naming, ingest workflow özellikleri)
4. Vault'u Obsidian ile aç, graph view'i kontrol et
5. İlk kaynağı `raw/` içine koy, ajana "ingest et" de
6. Sonucu Obsidian'da gez, sayfa formatını ve naming'i beğenmediysen şemayı güncelle, tekrar çalıştır

Ondan sonra her yeni kaynakla wiki organik olarak büyür.

---

**Bu skill alan-bağımsızdır.** vibeapp gibi bir yazılım projesi, bir doktora tezi, bir kitap kulübü, kişisel bir gelişim günlüğü, bir startup'ın takım wiki'si — hepsi için aynı pattern uygulanır. Sadece şema dosyası alana özgü olur.

## Bu repoda

Bu repo, desenin bir **varyantını** uygular. Buradaki jenerik tanım değil, bağlayıcı olan `AGENTS.md` + `SCHEMA.md`'dir (çelişkide SCHEMA kazanır). Repo varyantının farkları:

- **Şema dosyası:** `CLAUDE.md` değil → `AGENTS.md` + `SCHEMA.md`
- **Wiki yapısı:** alt klasörlü vault (`sources/`, `entities/`, ...) değil → düz `wiki/` (alt klasör yok); organizasyon Tree protokolüyle hub-yaprak `## Links` bağlarıyla sağlanır
- **Log:** tek `log.md` değil → günlük `log/YYYY-MM-DD.md` dosyaları; satır formatı SCHEMA §5
- **Operasyonlar:** INGEST/QUERY/LINT'e ek olarak `tend` (bahçe bakımı) vardır
- **Epistemik durum:** skill'deki "her iddia kaynaklı" kuralına ek olarak `status: unverified → established` yükseltme disiplini yürürlüktedir

Kök: [[index]]
