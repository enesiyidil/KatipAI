# KatipAI — Özellik Listesi

> Eklenecek özellikler burada toplanır. Tamamlanan maddeler `[x]` ile işaretlenir.

**Son güncelleme:** 2026-07-05

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

Şu an **Toplantı Modu** tray menüsünden manuel seçiliyor (`RecordingMode.MEETING`); sistem sesi için uygulama bazlı capture ve echo ayrımı mevcut ama toplantı başlangıcı otomatik algılanmıyor.

**Hedef:** Kullanıcı Teams üzerinden toplantıya girdiğinde KatipAI bunu algılasın, **toplantı moduna** geçsin ve kayıt profilini otomatik ayarlasın:
- Mikrofon → kullanıcının sesi (**Ben**)
- Teams sistem sesi → karşı taraf / diğer konuşmacılar (**Diğer**)
- Echo dedup, kanal ayrımı ve ilgili ayarlar toplantı senaryosuna göre otomatik yapılandırılsın

- [ ] Toplantı uygulaması algılama (öncelik: Microsoft Teams — `com.microsoft.teams2`)
- [ ] Algılama sonrası otomatik veya onaylı geçiş: normal → meeting modu + kayıt başlat
- [ ] Teams için sistem sesi capture'ının otomatik seçimi / bağlanması
- [ ] Çift kanal kayıt: mikrofon + Teams system audio eşzamanlı
- [ ] Toplantı moduna özel otomatik ayarlar (echo dedup, chunk süreleri, voice filter vb.)
- [ ] Toplantı bitince otomatik çıkış veya kullanıcı onayı ile normal moda dönüş
- [ ] Tray bildirimi: "Toplantı algılandı — kayda başla?" (`meeting_auto_detect`, `meeting_auto_start`)
- [ ] API: meeting durumu ve accept/dismiss uçları
- [ ] Sonraki adım: Zoom, Meet, FaceTime vb. genişletme

**Örnek akış:**

```
Teams toplantısı açıldı
  → KatipAI algılar
  → Toplantı modu + Teams system audio + mikrofon kaydı
  → Ben / Diğer ayrımı otomatik
  → Toplantı kapandı → normal mod
```

---

## Diğer özellikler

*(Aklına gelenleri buraya ekle.)*

- [ ] …
