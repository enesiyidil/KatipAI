# KatipAI — Özellik Listesi

> Eklenecek özellikler burada toplanır. Tamamlanan maddeler `[x]` ile işaretlenir.

**Son güncelleme:** 2026-07-07

---

## Nasıl kullanılır

- Yeni fikir gelince ilgili bölüme madde ekle.
- Uygulandıkça `- [ ]` → `- [x]` yap.
- Büyük özellikler alt maddelere bölünebilir; hepsi tamamlanınca üst madde de tiklenir.

---

## Not alma & vault

### Özelleştirilebilir not etiketleri (custom keys)

**Durum:** Planlandı

Şu an sistemde sabit **genel notlar** akışı var: konuşmacı belirli sesli komutlarla (`"bunu genel notlara ekle"`, `"genel not olarak …"`) not bırakabiliyor; notlar `general/Notlar.md` dosyasına yazılıyor (`core/vault/general_notes.py`, `GeneralNotes` sayfası).

**Hedef:** Kullanıcı kendi not kategorilerini tanımlayabilsin — yeni bir **key/etiket** ekleyip o key'e uygun bir not alanı oluştursun; o key ile gelen notlar ilgili bölüme yönlendirilsin.

- [ ] Kullanıcı tanımlı not key'leri için ayar/model (key adı, tetikleyici ifadeler, vault yolu veya dosya adı)
- [ ] Ayarlar UI: yeni key ekleme, düzenleme, silme
- [ ] Pipeline: transcript'te key eşleşmesi → ilgili vault dosyasına yazma (`note_pipeline` + vault writer genişletmesi)
- [ ] Web UI: her custom key için ayrı okuma sayfası veya tek sayfada sekmeli görünüm
- [ ] Varsayılan `genel not` akışının geriye dönük uyumluluğu

**Örnek kullanım:**

| Key | Tetikleyici (örnek) | Hedef |
|-----|---------------------|-------|
| `genel` | "genel not olarak …" | `general/Notlar.md` (mevcut) |
| `fikirler` | "fikir olarak kaydet …" | `general/Fikirler.md` |
| `todo` | "yapılacaklar listesine ekle …" | `general/Yapilacaklar.md` |

---

## Ses tanıma

### Tam ses tanıma (speaker recognition / diarization)

**Durum:** Planlandı

Şu an tek kullanıcı **ses profili** var: mikrofon kanalındaki chunk'lar kayıtlı profile göre eşleştiriliyor (`VoiceProfileService`, `VoiceMatcher`); eşleşme yoksa veya sistem sesi kanalındaysa konuşmacı kabaca **Ben** / **Diğer** / **Bilinmeyen** olarak etiketleniyor. Çoklu konuşmacı ayrımı ve kalıcı konuşmacı kimliği henüz yok.

**Hedef:** Toplantı ve arka plan kayıtlarında **kimin ne söylediğini** güvenilir biçimde ayırt edebilmek — birden fazla konuşmacıyı tanımak, transcript ve vault çıktısında doğru etiketlemek.

- [ ] Çoklu konuşmacı kaydı (enrollment): isim + ses örneği ile profil oluşturma
- [ ] Gerçek zamanlı veya chunk sonrası konuşmacı eşleştirme (embedding / diarization)
- [ ] Bilinmeyen konuşmacılar için otomatik segment + sonradan isim atama
- [ ] Transcript, timeline ve vault satırlarında doğru `speaker` etiketi
- [ ] Ayarlar UI: konuşmacı profilleri yönetimi, eşik değerleri
- [ ] Mevcut tek profilli ses filtresi (`voice_filter_mode`) ile uyumlu geçiş

---

## Toplantı modu

### Otomatik toplantı algılama (Teams → meeting modu)

**Durum:** Planlandı

Şu an **Toplantı Modu** tray menüsünden manuel seçiliyor (`RecordingMode.MEETING`); sistem sesi için uygulama bazlı capture ve echo ayrımı mevcut ama toplantı başlangıcı otomatik algılanmıyor. Toplantı notları da günlük transcript/AI not akışından ayrı bir sekmede toplanmıyor.

**Hedef:** Kullanıcı Teams üzerinden toplantıya girdiğinde KatipAI bunu algılasın, **toplantı moduna** geçsin ve kayıt profilini otomatik ayarlasın:
- Mikrofon → kullanıcının sesi (**Ben**)
- Teams sistem sesi → karşı taraf / diğer konuşmacılar (**Diğer**)
- Echo dedup, kanal ayrımı ve ilgili ayarlar toplantı senaryosuna göre otomatik yapılandırılsın
- Toplantı transcriptleri, özetleri ve notları **ayrı bir sekmede** (toplantı bazlı) görüntülensin

- [ ] Toplantı uygulaması algılama (öncelik: Microsoft Teams — `com.microsoft.teams2`)
- [ ] Algılama sonrası otomatik veya onaylı geçiş: normal → meeting modu + kayıt başlat
- [ ] Teams için sistem sesi capture'ının otomatik seçimi / bağlanması
- [ ] Çift kanal kayıt: mikrofon + Teams system audio eşzamanlı
- [ ] Toplantı moduna özel otomatik ayarlar (echo dedup, chunk süreleri, voice filter vb.)
- [ ] Toplantı bitince otomatik çıkış veya kullanıcı onayı ile normal moda dönüş
- [ ] Tray bildirimi: "Toplantı algılandı — kayda başla?" (`meeting_auto_detect`, `meeting_auto_start`)
- [ ] API: meeting durumu ve accept/dismiss uçları
- [ ] DB: `Meeting` oturum modeli (başlangıç/bitiş, uygulama, başlık, transcript/özet FK)
- [ ] Web UI: **Toplantılar** sekmesi — geçmiş ve aktif toplantılar, her toplantıya özel transcript + AI özeti
- [ ] Vault: toplantı başına ayrı dosya veya günlük dosyada toplantı bloğu (`meetings/2026-07-07 — Sprint Planlama.md`)
- [ ] Sonraki adım: Zoom, Meet, FaceTime vb. genişletme

### Toplantı adı (Teams entegrasyonu)

**Durum:** Araştırılacak — entegrasyon kolaysa dahil edilecek

Sadece process algılama ile toplantı adı muhtemelen gelmez; başlık için ek kaynak gerekir. Öncelik sırası:

| Yöntem | Zorluk | Not |
|--------|--------|-----|
| Teams pencere başlığı / UI metni okuma | Düşük–orta | OAuth yok; kırılgan ama hızlı POC |
| Outlook / takvim eşlemesi (yakın saatteki etkinlik) | Orta | Toplantı davetinden başlık |
| Microsoft Graph API (Teams + Calendar) | Yüksek | OAuth, izinler, en güvenilir başlık |

- [ ] POC: Teams aktifken pencere başlığından toplantı adı çekilebiliyor mu test et
- [ ] Başlık alınamazsa fallback: `Teams toplantısı — {tarih saat}` veya kullanıcıdan düzenleme
- [ ] Graph API entegrasyonu yalnızca POC başarısız ve değer yüksekse (ayrı faz)
- [ ] Toplantı başlığının tray bildirimi, UI sekmesi ve vault dosya adında kullanılması

### Toplantı dışı arama algılama (1:1 çağrılar)

**Durum:** Planlandı

Teams'te planlı toplantı dışında yapılan **sesli/görüntülü aramalar** da benzer kayıt ihtiyacı doğurur. Bunlar da toplantı gibi ele alınmalı: otomatik algılama, meeting modu, transcript ve özet.

**Hedef:** 1:1 veya küçük grup aramaları (toplantı odası olmayan) tespit edilip aynı pipeline ile kaydedilsin.

- [ ] Teams arama durumu algılama (call UI / process state — toplantı odasından farklı sinyal)
- [ ] Arama başlayınca meeting modu + çift kanal kayıt (toplantı ile aynı profil)
- [ ] Arama bitince oturum kapatma ve özet üretimi
- [ ] UI'da aramalar: toplantılar sekmesinde veya alt tür olarak (`Teams Araması — Ahmet`)
- [ ] Mümkünse karşı taraf adı (Teams UI / Graph / son görüşme geçmişi)
- [ ] Telefon uygulaması / FaceTime gibi diğer arama kaynaklarına genişletme (sonraki adım)

**Örnek akış:**

```
Teams toplantısı veya araması açıldı
  → KatipAI algılar (+ mümkünse başlık: "Haftalık Sprint" / "Arama — Ayşe")
  → Toplantı modu + Teams system audio + mikrofon kaydı
  → Ben / Diğer ayrımı otomatik
  → Transcript + özet → Toplantılar sekmesi + vault
  → Oturum kapandı → normal mod
```

---

## Arama & asistan

### RAG chatbot (içeride soru-cevap)

**Durum:** Planlandı

Şu an transcript, AI notları ve genel notlar ayrı sayfalarda okunuyor; kullanıcı geçmişte konuşulan bir şeyi bulmak için manuel arama yapmak zorunda. Uygulama içinde doğal dilde soru sorup cevap alabileceği bir asistan yok.

**Hedef:** KatipAI içinde bir **chatbot** olsun; AI notları, transcriptler, genel notlar, toplantı özetleri ve vault içeriği **RAG** ile indekslensin. Kullanıcı soru sorduğunda veya bir şey aradığında ilgili parçalar bulunup yerel LLM (Qwen) ile cevap üretilsin.

**İndekslenecek kaynaklar:**

| Kaynak | Örnek soru |
|--------|------------|
| Transcriptler | "Dün Ahmet ne dedi?" |
| AI notları / oturum özetleri | "Son toplantıda kararlar neydi?" |
| Genel notlar | "Yapılacaklar listemde ne var?" |
| Toplantı notları | "Sprint planlamada konuşulan riskler?" |
| Vault markdown | "Geçen hafta hangi konular geçti?" |

- [ ] Embedding modeli + vektör deposu (tamamen lokal — sqlite-vec / chroma / benzeri)
- [ ] İndeksleme pipeline: yeni transcript, özet ve not eklendikçe otomatik chunk + embed
- [ ] Chunk stratejisi: tarih, konuşmacı, oturum/toplantı metadata'sı ile etiketleme
- [ ] RAG retrieval: semantik arama + isteğe bağlı tarih/kaynak filtresi
- [ ] Chat API: `POST /api/chat` — soru → retrieval → LLM cevap + kaynak referansları
- [ ] Web UI: sohbet paneli / sayfası (mesaj geçmişi, kaynak snippet'leri, ilgili vault linki)
- [ ] Cevaplarda **kaynak gösterimi** (hangi transcript/not, hangi tarih) — halüsinasyonu azaltmak için
- [ ] Mevcut veriler için ilk kurulumda backfill indeksleme
- [ ] Sonraki adım: MCP / dış araç entegrasyonu, komut tabanlı aksiyonlar ("bunu genel nota ekle")

**Örnek kullanım:**

```
Kullanıcı: "Bu hafta proje deadline'ı hakkında ne konuşuldu?"
  → RAG: ilgili transcript + AI özet chunk'ları
  → LLM: özet cevap + kaynaklar (7 Temmuz oturum, Sprint toplantısı)
```

---

## Diğer özellikler

*(Aklına gelenleri buraya ekle.)*

- [ ] …
