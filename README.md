# Noma (Agents Repo)

Bu depo, insan ve yapay zeka (agent) ortak çalışma alanıdır. Kişisel asistanın bilgi tabanı, hafızası, sözleşmeleri ve araçları burada yaşar.

⚠️ **GÜVENLİK UYARISI:** Bu depo **public**'tir. Tüm kişisel veriler, wiki notları, loglar ve hafıza kayıtları `git-crypt` ile şifrelenmiştir. Şifrelenmemiş (public) dizinlere ASLA kişisel veri, API anahtarı veya şifre yazılmamalıdır.

## Kurulum ve Kilit Açma

Yeni bir düğüm (agent, bilgisayar, VPS) bağlarken şifreli dosyaları açmak için:
```bash
git-crypt unlock /guvenli/yer/noma.key
```

`index.md` kök hub haritasını, şifreli `index/hubs/` türetilmiş hub sayfalarını
taşır; gezinmeye kilit açıldıktan sonra `index.md` kökünden başlayın. Kilitli
bir klonda içerik okunmaz.

Anahtar yedeğini GitHub dışında, şifreli ve birbirinden bağımsız iki çevrimdışı
konumda saklayın. Yedeklerden birini yılda bir ayrı bir klonda `git-crypt unlock`
ile sınayın; anahtarı veya çıktısını repoya eklemeyin.

## Harita ve Yönlendirmeler

Depodaki dosyalar ve mimari kurallar için aşağıdaki yönlendirmeleri takip edin:

* **Sistem Mimarisi ve Temel Kavramlar:** `[[kisisel-bilgi-sistemi]]`, `docs/ARCHITECTURE.md`
* **Agent Politikaları ve Kurallar:** `[[agent-policy]]`, `AGENTS.md`, `SCHEMA.md`
* **Güvenlik ve Anahtar Protokolü:** `[[guvenlik-ve-anahtar]]`
* **Geliştirme Planı:** `docs/ROADMAP.md`
* **Obsidian Vault Kurulumu:** `docs/obsidian-recommended.md`

Zamanlanmış iş (cron) henüz yoktur: commit, push ve conflict çözümü elle
yapılır; zamanlanmış job `docs/ROADMAP.md` B5'e bağlıdır.
