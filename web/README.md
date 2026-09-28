# web/ — Graph View

Wiki'nin `[[wikilink]]` ilişkilerinden üretilen, Obsidian benzeri read-only
graph explorer. Sunucu gerekmez; `index.html` çift tıkla açılır.

- Kanonik kaynak `wiki/*.md`'dir; `data/graph.json` ve `data/graph.js`
  türetilmiştir (derived), elle düzenlenmez ve git'e girmez.
- Node sürükleme gibi görsel state yalnız tarayıcı localStorage'ında yaşar,
  wiki dosyalarına asla yazılmaz.

## Kullanım

```bash
python3 scripts/noma_build_graph.py   # wiki → web/data/graph.{json,js}
open web/index.html                   # çift tık da olur; sunucu gerekmez
```

- Arama: `/` odaklanır, Enter ilk sonuca gider.
- Node tık → detay paneli; `Yerel graph` → seçili notun derinlik 1-3 çevresi;
  `Genel` → tüm graph. Sağ tık → bağlam menüsü, çift tık → odakla.
- Sürüklerken komşular yaylanır (canlı ForceAtlas2); `Fizik` düğmesi kapatır.
- Klavye: `←`/`→` komşu gez, `↑` üst hub, `↓` alt not, `Enter` yerel/global,
  `+`/`−` zoom, `0` genel görünüm, `Esc` temizle.
- Hover: node/kenar ipucu, komşu vurgusu; seçili node nabız efekti.
- Filtreler: type/scope/stage/bağlantı durumu (eksik notlar dahil).
- `Yeniden diz`: ForceAtlas2 yerleşimini sıfırdan hesaplar (ana thread'de
  dilimli; `file://` üzerinde Web Worker CORS nedeniyle kullanılamaz).

## Yapı

```
web/
├── index.html          # giriş; graph'a özgü değil, gelecek view'lar eklenebilir
├── graph/              # graph view modülü (render, layout, ui, bootstrap)
├── vendor/             # commit'li harici kütüphaneler (provenance: vendor/README.md)
└── data/               # ÜRETİM ÇIKTISI — gitignore'lu, elle düzenlenmez
```

Karar kaydı: `wiki/graph-view-web.md`.
