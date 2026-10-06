# Plan Dosyası Şablonu (plans/)

Adlandırma: `YYYY-MM-DD-<kısa-ascii-slug>.md` (SCHEMA §1). Tek iş = tek dosya;
frontmatter taşımaz (session özeti gibi). Oturum devrinde Durum, Sıradaki Adım ve
Devir Notu bölümleri güncel tutulur; boş bırakılmaz. Yer tutucular kod aralığında
(canlı wikilink üretmesin; bkz. wiki_note.md artefakt notu).

---
# `{{İş Başlığı}}`

Amaç: `{{hedef ve kabul ölçütü — 1-2 satır}}`

Bağ: [[index]] · `{{ilgili wiki notu/plan yolu — yoksa sil}}`

## Durum
`{{in_progress | parked | done | cancelled}}` · güncelleme: `{{YYYY-MM-DD HH:mm}}`

## Adımlar
- [ ] `{{somut adım}}`
- [x] `{{tamamlanan adım — kısa sonuç/atıf}}`

## Sıradaki Adım
`{{devam eden iş varken her devirde yenilenen tek somut adım; done/cancelled ise "yok"}}`

## Devir Notu
`{{oturum kapanışında: şu ana kadar ne yapıldı, hangi bağlam/belirsizlik açık,
dikkat edilecekler, doğrulama komutları}}`

---
