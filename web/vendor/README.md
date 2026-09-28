# web/vendor/

Graph view'ın harici kütüphaneleri. Deterministik ve offline çalışma için
minified kopyalar repoya commit edilir; npm/build zinciri yoktur.
`graph.json`/`graph.js` verisi hariçtir (bkz. `../README.md`).

| Dosya | Paket | Sürüm | Kaynak | SHA256 |
|---|---|---|---|---|
| `sigma.min.js` | sigma | 3.0.3 | <https://cdn.jsdelivr.net/npm/sigma@3.0.3/dist/sigma.min.js> | `58e30383ab428f832068d9d16a5215c65ba12430d438ed091c5703f398de9e16` |
| `graphology.umd.min.js` | graphology | 0.26.0 | <https://cdn.jsdelivr.net/npm/graphology@0.26.0/dist/graphology.umd.min.js> | `dc337efa23903f61e064c8e7e7f93a429e6855dccfc2458802b4ed30c621c087` |
| `graphology-layout-forceatlas2.min.js` | graphology-layout-forceatlas2 | 0.10.1 | aşağıda | `4be15e080971a97dc6495cd5644c39d050fb09ddc17d2a8ebdf7550cd208e31d` |

Global isimler: `Sigma`, `graphology.Graph`,
`graphologyLayoutForceAtlas2` (`.assign` / `.inferSettings`).

Lisanslar yan dizindeki `*-LICENSE.txt` dosyalarıdır (hepsi MIT).

## FA2 bundle'ının yeniden üretimi

`graphology-layout-forceatlas2` UMD build yayınlamaz (yalnız ESM/CJS).
`file://` üzerinde ES module import CORS nedeniyle çalışmadığından tek
dosyalık IIFE bundle commit edilir:

```bash
mkdir fa2 && cd fa2 && npm init -y && npm install graphology-layout-forceatlas2@0.10.1
printf 'var fa2 = require("graphology-layout-forceatlas2");\nself.graphologyLayoutForceAtlas2 = fa2;\n' > entry.js
npx esbuild entry.js --bundle --format=iife --minify \
  --outfile=web/vendor/graphology-layout-forceatlas2.min.js
```

Sürüm güncellemesi: paket sürümlerini bu tabloda ve komutta birlikte güncelle,
sha256'ü yeniden kaydet.
