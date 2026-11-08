# GraphRAG arayüz tasarımı — referans uyarlaması

Tarih: 7 Kasım 2026  
Durum: **Kullanıcının “uygula” talimatıyla ilk dilim uygulandı.** Bu belge tasarım gerekçesini ve hedef akışları korur; gerçekleşen kapsam ve doğrulama [uygulama raporundadır](ARAYUZ_UYGULAMA_RAPORU.md).

Bu belge, gönderilen dört WEBP görseli ve 33,85 saniyelik videodaki görünümün bu projeye uygulanmasını tarif eder. Ekran çizimleri sentetik notlarla hazırlanmıştır; kullanıcının altı özel notu kullanılmamıştır. Çizimler çalışan uygulama veya canlı sonuç değildir.

## 1. Tasarım kararı

**Grafın kendisi ana ekran olacak.** Tam genişlikte kömür rengi zemin üzerinde renkli konu kümeleri, ince bağlantılar ve az sayıda kalıcı kontrol bulunacak. Bir nota tıklanınca sağda okuma paneli açılacak; haritanın konumu korunacak. Liste ve konu ağacı aynı notların alternatif görünümleri olacak. Projenin kaynaklı soru-cevap özelliği bu çalışma alanındaki ayrı bir sağ panelden kullanılacak.

Referansın masaüstü duvar kâğıdı ve pencere dışı perspektifi uygulamaya taşınmaz; tarayıcı içindeki çalışma alanı esas alınır. Notion logosu, paylaşma, kilit ve kullanıcı avatarları bu projede karşılığı olmadığı için tasarımın parçası değildir.

### Referanslardan alınan kararlar

| Referans | Tasarıma aktarımı |
| --- | --- |
| Görsel 1 | Dairesel notlar, büyük konu merkezleri, saydam organik küme sınırları, uzaktaki bağlantıların geri planda kalması. |
| Görsel 2 | Kartlar yerine sıkı bir tablo; başlık, konu, işleme durumu ve tarih sütunları. |
| Görsel 3 | Ctrl+K ile açılan, grafı karartan ve klavyeyle gezilen merkezi arama penceresi. |
| Görsel 4 | Grafın sağında sabit genişlikte not ayrıntısı; konu, kaynak, metin ve ilişkiler. |
| Video | Kaydırma/yakınlaştırma, görünüm değiştirme, konu ağacı, katman kontrolleri ve haritayı ekrana sığdırma. Yaklaşık 2,0 / 9,5 / 17,6 / 26,4 / 32,2 saniyelerdeki kareler incelendi. |

### Tasarım öncesi eleştiri ve düzeltme

İlk seçenek, mevcut dört sekmenin koyu renkli kartlarla yeniden düzenlenmesiydi. Bu, referansın graf merkezli karakterini kaybederdi. Son tasarımda büyük sayfa başlığı, kalıcı sol menü, istatistik kartları ve karşılama alanı kaldırıldı. Görsel vurgu yalnızca renkli graf kümelerinde yoğunlaştı. İnce çizgiler sınır veya ilişki anlatır; dekor olarak kullanılmaz. Referanstaki çok küçük yazılar okunabilir boyuta çıkarıldı. Soru-cevap, haritayı başka sayfaya dönüştürmeden sağ panelde çözüldü.

## 2. Ekran çizimleri

Dosyalar `docs/design/reference-v1/` altındadır. PNG'ler doğrudan görüntülenebilir; SVG'ler düzenlenebilir tasarım kaynaklarıdır.

- [Ana graf](design/reference-v1/01-harita.png)
- [Graf ve not paneli](design/reference-v1/02-not-paneli.png)
- [Not listesi](design/reference-v1/03-liste.png)
- [Arama penceresi](design/reference-v1/04-arama.png)
- [Kaynaklı cevap paneli](design/reference-v1/05-soru-cevap.png)

Çizimlerdeki kontroller etkileşimsizdir. Konular ve ilişkiler önerilen yeni veri modelini temsil eder; mevcut backend'in bunları zaten sunduğu anlamına gelmez.

## 3. Görsel sistem

### Temel renkler

| Token | Değer | Görev |
| --- | --- | --- |
| `canvas` | `#181818` | Graf ve genel zemin. |
| `surface` | `#202020` | Sağ panel ve araç yüzeyleri. |
| `floating` | `#272727` | Arama penceresi ve bağlam menüsü. |
| `text` | `#EEEEEC` | Ana metin. |
| `muted` | `#A5A5A3` | İkincil metin ve açıklamalar. |
| `action` | `#459FE5` | Odak, seçili kontrol, ana işlem. |

Ayırıcılar beyazın yaklaşık %9 opaklığıyla çizilir. Köşeler araç düğmelerinde 5 px, arama penceresinde 10 px; graf ve sağ panel dikdörtgendir. Gölge yalnızca üstte açılan arama/menü katmanında kullanılır.

Mavi dolgulu ana düğmede açık metin yerine koyu `#10222E` metin kullanılır; küçük düğme yazılarının kontrastı korunur.

Konu renkleri: mor `#A683C9`, mavi `#529BD3`, turkuaz `#46AAA3`, turuncu `#D78C4B`, pembe `#C86694`, yeşil `#5B9F77`, sarı `#C5AC39`, sınıflanmamış gri `#9A9A98`. Bir konu kendi kalıcı `color_key` değerini taşır; sıralama veya sayfalama rengi değiştirmez. Bu renkler normal metin yerine nokta, şekil ve küme alanında kullanılır.

### Tipografi ve ölçüler

- Yazı ailesi: **Segoe UI Variable / Segoe UI**, ardından `system-ui`. Windows'ta yerel çalışma hissi ve Türkçe karakter desteği için seçildi. Dış font çağrısı yok; ayrı bir başlık ailesi kullanılmaz.
- Araçlar ve tablo: 14 px; ikincil bilgi: 12–13 px; not metni: 15 px / 24 px; not başlığı: 24 px / 30 px, 600 ağırlık.
- Graf etiketi ekranda 12–14 px. Uzaklaştırıldığında küçültüp okunmaz yapmak yerine seçili not/konu etiketleri dışındakiler gizlenir.
- Ana metin ve tablo sola hizalı; yalnızca graf düğüm etiketleri merkezde. Not satırı 45–65 karakter hedefler.
- Temel aralık 4 px; kontroller arası 8 px; yüzey içleri 16/24 px. Üst kimlik çubuğu 44 px, görünüm çubuğu 44 px, graf kalan yüksekliği doldurur.
- Masaüstünde sağ panel 380 px; kullanıcı 340–520 px arası genişletebilir. Panel içeriği kendi içinde kayar.

## 4. Yerleşim ve ekran davranışları

### 4.1 Ana çalışma alanı

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Bilgi alanı / Notlar              Kalıcı · Yerel model   Soru sor  + Yeni not│
├─────────────────────────────────────────────────────────────────────────────┤
│ Graf  Liste  Konular     Not veya varlık ara… Ctrl+K     Katmanlar  Sığdır    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│       (mor konu)                           (gri konu)                        │
│          • •    ──────────── • •                                             │
│                            (turuncu konu)                                   │
│  (yeşil konu)                                                               │
│                       (mavi konu)                                           │
│       (turkuaz konu)                                                        │
│  Renk açıklamaları                         −  +      Haritayı sürükle        │
└─────────────────────────────────────────────────────────────────────────────┘
```

Varsayılan görünüm Graf. Üstte büyük logo/başlık veya kalıcı sol menü yok. `Graf / Liste / Konular` görünümü değiştirir; seçili not, filtre ve grafın kamera konumu korunur. `Sistem` bilgisi üstteki durum alanından küçük bir çekmecede açılır.

Araç çubuğu geniş ekranda `Konular`, `Bağlantılar`, `Benzerlik` katmanlarını ayrı gösterir; dar ekranda tek `Katmanlar` menüsüne toplar. `Benzerlik` yalnızca gerçek hesaplanmış benzerlik verisi varsa açılabilir. Kişi türü doğrulanmadan `Kişiler` filtresi sunulmaz.

### 4.2 Grafın görsel dili

| Öğeler | Görünüş | Anlam |
| --- | --- | --- |
| Konu | Büyük dolu daire, altında ad ve not sayısı | Gezinme/gruplama; bir gerçek dünya varlığı veya doğruluk skoru değildir. |
| Not | Küçük dolu daire, konu rengi | Tek not; seçilince beyaz çevre halkası. |
| Konu alanı | %5–8 saydam dolgu, %30 sınır | Aynı konuya atanmış notların organik dış sınırı. |
| Not–konu bağı | Çok silik kısa çizgi | Konu üyeliği. |
| Not–not bağı | İnce düz çizgi | Ortak varlık üzerinden türetilmiş bağ; açılınca gerekçesi gösterilir. |
| Anlamsal benzerlik | İnce kesik çizgi | Hesaplanmış yakınlık; kaynak desteği veya kesin ilişki sayılmaz. |
| Seçili ilişki | Daha yüksek kontrast ve açıklama | Hover/odakta bağlı iki not ile ortak varlıklar görünür. |
| Kaynaklı ilişki görünümü | Yönlü çizgi, ilişki adı | Mevcut varlık grafındaki iddia; alıntı, olumsuzluk ve olasılık ayrı gösterilir. |

Not çapı başlangıçta sabittir; bağlantı sayısıyla aşırı büyüyüp büyük konuyla karışmaz. Konu çapı not sayısının kareköküyle sınırlı büyür. Düzensiz küme sınırı için not konumlarından dış zarf hesaplanıp yumuşatılır; tek/iki notlu konu için kapsül kullanılır. Dikdörtgen compound-node kutuları bu görünümün yerine geçmez.

Graf yerleşimi açılışta kısa süre yerleşir, sonra durur. Sürekli titreşim/yüzme yok. Sürükleme konuyu değiştirmez; konu taşıma açık bir `Konuyu değiştir` işlemidir. Seçim diğer kümeleri hafifçe soldurur; bağlı notları ve ilişkileri belirginleştirir. `Sığdır` yalnızca kullanıcı isteğiyle veya ilk yüklemede çalışır.

### 4.3 Sağ not paneli

```text
┌───────────────────────────────────────────┬────────────────────────┐
│ Graf  Liste  Konular          Ara…        │ Not              ×     │
├───────────────────────────────────────────┤ Atlas mimari notları   │
│                                           │ Konu      ● Projeler   │
│          seçili not ⊙                     │ Durum     İşlendi      │
│          komşuları belirgin               │ Eklenme   7 Kas 2026   │
│                                           │                        │
│  kamera konumu korunur                    │ Notun metni…           │
│                                           │                        │
│                                           │ İlişkileri göster      │
│                                           │ Düzenle        ⋯       │
└───────────────────────────────────────────┴────────────────────────┘
```

Üst başlık, konu, işleme durumu, gerçek tarih bilgisi; ardından tam metin. Kaynak bağlantısından gelindiyse ilgili değişmez revizyon açılır ve alıntı aralığı işaretlenir. Mevcut API `created_at` verir; `Güncellendi` için yeni `updated_at` alanı gereklidir. Bu alan yoksa `Eklenme` etiketi kullanılır.

`Düzenle` paneli başlık ve metin editörüne çevirir. `Kaydet` yeni revizyonu kuyruğa alır. Eski aktif metin aramada kullanılmaya devam ediyorsa “Yeni sürüm işleniyor; arama önceki sürümü kullanıyor” gösterilir. İş başarısızsa `Yeniden dene`; silme menü içinden, not adıyla açık onay alır. `.txt/.md` yükleme `Yeni not` içinde bulunur. Kaydedilmemiş metin varken panel/görünüm değişimi koruma ister.

Yüzdelik güven çubuğu eklenmez: mevcut sistemde kalibre edilmiş bir not doğruluk yüzdesi yoktur. Varsa işleme ilerlemesi açıkça `İşleme` olarak gösterilir.

### 4.4 Liste ve konular

Liste, referanstaki gibi tüm genişliği kullanan satırlardan oluşur. Sütunlar `Ad / Konu / Durum / Eklenme`; `updated_at` eklendiğinde son sütun `Güncellendi` olabilir. Satır 38–42 px; hover çok hafif açık zemin. Tıklama aynı sağ paneli açar. Konu rengi küçük bir nokta ve yazıyla gösterilir.

Sayfa başına 50 kayıt; `Önceki / Sonraki`, görünür aralık ve mevcutsa sunucudan gelen toplam. Toplam bilinmiyorsa uydurulmaz. Konu/arama değişince cursor geçmişi sıfırlanır. Filtre yalnızca yüklenen 50 kayıtta çalışmaz. Aktif sıralama yalnızca API destekliyorsa gösterilir.

`Konular` görünümü videodaki folder görünümünün karşılığıdır: konu adı ve not sayısı açılır/kapanır; içerik aynı not satırlarıdır. Dosya sistemi klasörü değildir. Konusu olmayan notlar `Düzenlenmemiş` altında durur. Bu gruplama gerçek konu verisi gerektirir.

### 4.5 Hızlı arama

Ctrl+K / üst arama alanı: ortada 620 px genişlikte panel, arkada %55 siyah karartma. Sonuç türleri `Not`, `Varlık`, `Konu` ayrı küçük etiket taşır; yazar bilgisi uydurulmaz. Not başlığı ve kısa eşleşme alıntısı görünür. 200 ms gecikmeli sorgu, önceki isteği iptal etme ve geç gelen cevabı yok sayma uygulanır.

Yukarı/aşağı ok seçimi değiştirir; Enter sonucu açar, Escape önce aramayı kapatıp odağı geri verir. Not seçimi haritada o notu bulur ve paneli açar. Varlık seçimi kaynaklı ilişki görünümüne geçer. “Sonuç bulunamadı” durumunda yeni not oluşturma seçeneği bulunur. Arama bir LLM çağrısı başlatmaz.

### 4.6 Soru-cevap

`Soru sor` sağda 420 px panel açar. Üstte soru alanı; altta cevap, varsa eksik bilgi ve numaralı kaynaklar. Bir kaynak seçilince panelin içinde `Cevaba dön` ile geri gelinebilen revizyon ayrıntısı açılır; ikinci bir yan panel eklenmez. Graf destekleyici varlık/iddia altgrafına geçebilir; `Not haritasına dön` önceki kamerayı geri getirir.

`answered`: normal cevap. `partial`: “Notlarda bulabildiklerim” ve eksik kalan bilgi. `insufficient_evidence`: “Notlarında bu soruyu yanıtlayacak yeterli kaynak bulamadım.” Model meşgulse gerçek duruma uygun bekleme mesajı; API akış vermediği için sahte token akışı yok. İlişki grafı olumsuz ve olası iddiaları kesin ilişki gibi sunmaz.

## 5. Bu repoya teknik uyarlama

### Önce mevcut veriyle hedef görünümü ayırmak

Mevcut `ui/app.py` Streamlit sekmeleridir. Graf `ui/components/evidence_graph/__init__.py` içinde yaklaşık 420 px yüksekliğinde bir Cytoscape bileşenidir. `/api/v1/graph` tam çalışma alanını vermez: tam olarak bir `entity_id` veya `note_id` ister, 1–2 adım ve 100 düğüm/150 ilişkiyle sınırlıdır. Düğümleri notlar değil varlıklardır. Tüm notları ayrı ayrı çağırıp bu altgrafları birleştirmek önerilmez.

| İstenen özellik | Şu an | Gereken iş |
| --- | --- | --- |
| Not ekle/değiştir/sil, `.txt/.md` | API hazır | Yeni editör ve işlem durumu bileşenleri. |
| Not sayfalama | Cursor API hazır; UI kullanmıyor | Cursor geçmişi ve filtrelerle uyumlu gezinme. |
| Kaynaklı cevap ve alıntı | API hazır | Sağ panel ve revizyon vurgulama. |
| Varlık çevresindeki ilişkiler | API hazır | Ayrı `Kaynak ilişkileri` katmanı; yön/polarity/modality korunur. |
| Tüm notların haritası | Yok | Sınırlı, sayfalı çalışma alanı harita sorgusu. |
| Konu merkezleri ve konu ağacı | Yok | Kalıcı konu metadata'sı, üyelik ve yönetim API'si. |
| Global not arama | Yok; `entities?q=` yalnızca varlık arar | Başlık/metin/kategori için arama okuma modeli. |
| `Kişiler` filtresi | API güvenilir entity type sunmuyor | İleride tür doğrulama ve API alanı; ilk sürümde genel `Varlıklar`. |
| Benzerlik çizgileri | Chunk embedding var; notlar arası API yok | Ayrı hesaplama, eşik, profil sürümü ve kapsam sınırı. |
| Güncellenme tarihi | Note model/API'de yok | Yeni migration, zaman damgası, geriye dönük bilinmeyen değer davranışı. |
| Durum bilgisi | Readiness + system status hazır | İki isteği bağımsız ele alan görünür durum alanı. |

### Önerilen frontend

**React + TypeScript + Vite ve Cytoscape.js** ile ayrı `frontend/` öneriyorum. FastAPI, worker, Neo4j ve LM Studio hizmetleri kullanılmaya devam eder. Bu bir tasarım kararı önerisidir; paket kurulmadı veya frontend oluşturulmadı.

Gerekçe: kalıcı kamera durumu, bağımsız sağ panel, klavye araması ve katmanların ortak seçim durumu için tarayıcı tarafında tek bir çalışma alanı uygun. Streamlit içinde özel bileşenle yapılabilir; fakat sayfa kabuğu ve bileşenler arası etkileşim için daha fazla köprü kodu gerektirir. Salt renk/CSS değişikliği referansı karşılamaz.

React bileşenleri ve paylaşılan etkileşim durumu için [resmî React rehberi](https://react.dev/learn), geliştirme/derleme için [Vite rehberi](https://vite.dev/guide/), graf olayları, stiller ve yerleşimler için [Cytoscape.js dokümantasyonu](https://js.cytoscape.org/) esas alınır. Sürümler uygulama sırasında birlikte doğrulanıp kilitlenir.

Organik küme sınırları Cytoscape'in düğüm kutusu özelliği gibi varsayılmaz: grafın altında ayrı Canvas katmanı hesaplanan dış zarfları çizer; pan/zoom/drag olaylarıyla dönüşüm eşleştirilir. Çizim `requestAnimationFrame` ile birleştirilir. Etiketler seçime ve zoom düzeyine göre azaltılır. Tüm JS/CSS/graf varlıkları yerel paketlenir; CDN bağımlılığı kaldırılır.

Tarayıcı aynı origin üzerindeki `/api` yoluna erişir. Geliştirmede Vite proxy, paketlemede statik frontend + API reverse proxy önerilir. Neo4j veya LM Studio adresi/anahtarları tarayıcıya verilmez. Ayrı frontend build target'ı ve mevcut Windows başlatma akışının güncellenmesi sonraki uygulama kapsamındadır. Eski Streamlit kabul kontrolü tamamlanana kadar alternatif giriş olarak tutulabilir.

### Yeni okuma modeli ve metadata taslağı

İlk sürümde konular **kullanıcı tarafından atanır**. Kaydedilmemiş bir tahmin notun kesin konusu gibi görünmez. Daha sonra öneri üretimi eklenirse `Öneri` olarak işaretlenir ve kullanıcı kabulüyle kalıcı konuya dönüşür. Bir notun bir ana konusu ve isteğe bağlı ek etiketleri olabilir.

Önerilen ek kayıtlar: `Topic(topic_id, name, color_key)`, not metadata'sında `topic_id`, `updated_at`, `metadata_version`. Metin revizyonu ile konu değişikliği ayrıdır; konu değiştirmek LLM çıkarımını yeniden çalıştırmaz. Bu kayıtlar Neo4j ve MemoryStore sözleşmelerine birlikte eklenir. Değişiklikler yeni numaralı migration ile yapılır; mevcut migration dosyaları düzenlenmez. Yeni model kurulunca notlar `Düzenlenmemiş` başlar; mevcut bilinmeyen güncelleme tarihleri bugünmüş gibi doldurulmaz.

Taslak API yüzeyi (henüz mevcut değildir):

- `GET /api/v1/workspace/map`: konu/not düğümleri, türetilmiş bağ türü, `graph_version`, `metadata_version`, kapsam/limit ve genişletme cursor'u. İlk yükleme için önerilen sınır 300 not / 600 bağ; bu bir ölçülmüş kapasite iddiası değildir.
- `GET /api/v1/search?q=...&types=...&cursor=...`: başlık/metin ve varlık/konu sonuçları, kısa eşleşme metni. Yalnızca görünür ve izinli veriler.
- Konu listeleme/oluşturma/güncelleme uçları ve `PATCH /api/v1/notes/{id}/metadata`: konu ataması; eşzamanlı değişiklik için metadata version kontrolü.
- Not listelemesine `q`, `topic_id`, desteklenen `sort` filtreleri. Cursor bu filtrelere bağlanır; farklı filtreyle eski cursor kullanılmaz.

Harita türetimi yalnızca silinmemiş notların aktif READY revizyonlarını ilişkilere dahil eder. İşlenen/başarısız not kabukları ayrı durumla gösterilebilir ama yayımlanmamış iddiaları bağ olarak kullanmaz. Aynı adlı iki varlık isim eşitliğiyle birleştirilmez; kalıcı ID kullanılır. Ortak varlık bağı iki notun aynı iddiayı doğruladığı anlamına gelmez. Bağın tıklanması kullanılan entity/claim/revision ID'lerini ve gerçek alıntıları getirir.

İş başarısı sonrası graph version, konu değişiminde metadata version değişir; önbellek ikisini de dikkate alır. Silme/yeniden işleme sonrası eski not/bağlar haritadan kaldırılır. Büyük koleksiyonlarda konu özeti ve seçili konu genişletme kullanılır; görünüm sınırlandıysa “300 not gösteriliyor; bir konu seçerek daralt” denir, tüm veri gösterilmiş gibi davranılmaz.

Benzerlik ikinci dilimdir. Not vektörü üretme yöntemi, embedding profil kimliği, eski revizyonların geçersizleştirilmesi, top-k/threshold ve karşılıklı bağ birleştirme kuralı tanımlanmadan düğümler arasına dekoratif benzerlik çizilmez. Bu sınırlar belirlendikten sonra ayrı ölçülür; benzerlik değeri doğruluk yüzdesi olarak gösterilmez.

## 6. Hareket, erişilebilirlik ve durumlar

- Seçim vurgusu 120 ms; panel 160 ms; kullanıcı istediğinde konuya odaklanma 220 ms. `prefers-reduced-motion` ile geçişler kaldırılır; sürekli yerleşim animasyonu yok.
- Hover'a ek olarak klavye odak stili bulunur. Grafın eşdeğer erişilebilir not listesi vardır; her küçük daireyi zorunlu Tab durağına çevirmekten kaçınılır. Grafik etiketi gizlenince içerik liste/arama yoluyla erişilebilir kalır.
- Arama modalında odak içeride tutulur ve kapanınca tetikleyiciye döner. Normal masaüstü not paneli modal değildir; grafla birlikte kullanılabilir. Renk tek bilgi taşıyıcısı değildir: konu adı, durum yazısı ve bağ türü bulunur.
- Normal metin kontrastı 4,5:1; kontrol/odak sınırları en az 3:1 hedeflenir. Arka plan bağlantıları dekoratif bağlamdır; seçili bağ yüksek kontrastta ve metinsel açıklamayla sunulur.
- 1100 px altında panel açıldığında graf daralır, ikincil kontroller menüye taşınır. 760 px altında liste ilk görünüm olur; graf ayrı seçenek ve tam ekran not detayı bulunur. Dokunma hedefleri en az 44 px. 360 px genişlikte yatay sayfa kayması olmaz.
- Boş koleksiyon: “İlk notunu ekle” ve `.txt/.md` yükleme. Sıfır sonuç: filtreyi temizle. Model kapalı: not okuma/listeleme devam eder, cevap ve işleme durumları ayrı açıklanır. API erişilemiyorsa son görünüm eski olduğu belirtilerek korunur; yeniden deneme sunulur.
- Sistem durumu “Kalıcı / Geçici” ve “Yerel model / Demo” bilgisini sade biçimde gösterir. `/health/ready` 503 olsa bile `/system/status` isteği ve açıklaması ayrı ele alınır.
- Alıntı aralıkları API'de Unicode code point cinsindedir; JavaScript'in UTF-16 `slice` davranışı doğrudan kullanılmaz. Emoji/Türkçe içeren kaynaklarda code point dönüşümü ve aynı değişmez revizyon doğrulanır.

## 7. Kullanıcı yönlendirmesinden sonraki uygulama sırası

Bu liste yapılacak işi tarif eder; bu teslimde hiçbir adım başlatılmadı.

1. Tasarım ve ayrı frontend kararı netleştirilir. İlk dilim: graf/not paneli/liste/konular/arama/kaynaklı cevap; benzerlik sonraki dilim.
2. Konu metadata'sı, harita okuma modeli ve arama sözleşmeleri eklenir; MemoryStore ve Neo4j aktif revizyon sınırları test edilir.
3. Ayrı frontend kabuğu, yerel asset paketleme, aynı origin API bağlantısı ve tasarım tokenları hazırlanır.
4. Not haritası, organik küme sınırları, seçim, pan/zoom ve sağ panel uygulanır.
5. Liste/cursor, konu ağacı, editör/yükleme, arama klavye akışı bağlanır.
6. Kaynaklı cevap ve kaynak ilişki grafı, hata/işleme durumları tamamlanır.
7. Gerçek API ile akış testleri, görsel karşılaştırma, klavye/mobil ve çevrimdışı asset kontrolleri yapılır; başlatma dokümanları güncellenir.

Önceki `MIMARI_VE_YAPILACAKLAR.md` E aşaması Streamlit iyileştirmesi varsayıyordu; bu tasarım yeni frontend ve API genişlemesi önerir. O belgedeki kapsam ve teslim listesi ancak kullanıcı bu yönü seçtiğinde güncellenir. Daha önce raporlanan model kalite açıkları bu arayüz çalışmasıyla çözülmüş sayılmaz.

### Kabul kontrolü

- Referansla yan yana 1440×960 ve 1024×768 kontrol: graf baskın, konu renkleri tutarlı, ince araç çubuğu, sağ panel ve sade liste.
- 0/1/50/51/101 notta sayfalama; filtre sonrası cursor; son kaydı silme ve işlem durumları.
- Konu renklendirmesi yeniden açınca değişmez; atanmayanlar `Düzenlenmemiş`; isim benzerliği entity ID'sinin yerine geçmez.
- Graf konumu seçim/panel/listeden dönüşte korunur; kullanıcı sürüklerken otomatik yeniden yerleşim olmaz.
- Ctrl+K, ok/Enter/Escape; 360 px ekran; azaltılmış hareket; görünür klavye odağı.
- Kaynak açılması aynı revision ID ve Unicode aralığını gösterir; olumsuzluk/olasılık ilişkide görünür.
- Güncelleme/silme sonrası eski kanıt ve eski harita bağı görünmez; `limited` durumu saklanmaz.
- Önerilen 300 düğüm/600 bağ hedefinde pan/zoom/frame ölçümü ve binlerce notta konu genişletme denenir; performans sonucu ölçülmeden başarı ilan edilmez.
- İnternet kapalıyken yerel paketlerden graf çizilir; modele erişilemediğinde okuma çalışır.

**Tasarım teslimindeki durma noktası:** Önceki turda bu noktada duruldu. Sonraki “uygula” talimatı geliştirmeyi yetkilendirdi; güncel uygulama durumu ayrı raporda izlenir.
