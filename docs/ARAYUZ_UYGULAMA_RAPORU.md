# Graf çalışma alanı — uygulama ve doğrulama

Tarih: 7 Kasım 2026. Kullanıcının onayladığı [tasarım](ARAYUZ_TASARIMI.md) uygulandı.

## Çalışan akışlar

- Tam ekran koyu graf; kalıcı renkli konular, yerel Canvas üzerinde organik küme sınırları, not seçimi, sürükleme, pan/zoom, ekrana sığdırma, yakınlaştırma ve seçim sırasında korunan kamera.
- Sağ not paneli; gerçek metin, konu ataması, işleme durumu, yeniden deneme, düzenleme, silme ve değişmez revizyon üzerinde kaynak vurgulama.
- Not oluşturma ve UTF-8 `.txt/.md` yükleme; idempotent yeniden deneme, kaydedilmemiş metin uyarısı.
- Liste ve 50 kayıtlık cursor sayfalaması; sunucuda uygulanan arama/konu filtreleri ve gerçek toplam. Konu ağacı ek sayfaları yükleyebilir.
- Konu oluşturma, ad/renk düzenleme, silme; not ve konu metadata'sında sürüm kontrolü. Konu değişikliği yeni bir extraction işi oluşturmaz.
- Ctrl+K ile not/varlık/konu arama; ok/Enter/Escape, odak geri dönüşü, iptal edilen/eski sorgu cevaplarını yok sayma.
- Kaynaklı soru-cevap, eksik bilgi ve yanıtsız durumları; varlık/iddia grafı, kaynak metni ve Unicode code point aralıkları. Negation/modality görünür tutulur.
- API/readiness/worker/model durumları, bağlantı hata mesajları, sıfır sonuç ve ilk not ekranları. 360 px'de tam ekran ayrıntı; azaltılmış hareket ve klavye odağı.

## Veri ve paketleme

`frontend/`: React + TypeScript + Vite + Cytoscape.js. Renkler ve yerleşim onaylanan referansın yapısını takip eder; uygulama örnek verileri otomatik üretmez.

Migration `005_workspace_topics.cypher` yeni konu kısıtlarını ve metadata aramasını ekler. Mevcut not/revizyonları silmez veya konularını tahmin etmez. Yeni alanlar MemoryStore ve Neo4j'de aynı sözleşmeyle uygulanır. Neo4j'de zaten bulunan `updated_at` okunur; bilinmeyen geçmiş tarihler uydurulmaz.

Yeni uçlar: `/api/v1/topics`, `/notes/{id}/metadata`, `/workspace/notes`, `/workspace/map`, `/search`. Liste filtreleri cursor'a bağlanır. Harita en fazla 300 not/600 ortak-varlık bağı döndürür; devam/sınırlama açıkça gösterilir. Ortak varlık bağı, iki notun aynı iddiayı doğruladığı anlamına gelmez. Yayımlanmamış/silinmiş revizyonlar bağ üretemez.

Docker `ui` target'ı Node build + Nginx'tir; JS/CSS yerel servis edilir. `/api` ve `/health` aynı origin üzerinden API'ye proxy edilir. Native demo için `scripts/frontend_server.py` aynı düzeni sağlar. Tarayıcı Neo4j/LM Studio kimlik bilgilerini almaz. Eski Streamlit kaynakları ve `legacy-ui` target'ı korunmuştur.

## Doğrulama

- **272 Python testi geçti**, atlanan/başarısız yok; 186,82 saniye. Bir mevcut Starlette/httpx deprecation uyarısı bulunur. Yeni konu, aktif kaynak, cursor kapsamı ve 0/1/50/51/101 not kontrolleri iki depoda da çalıştı.
- Ruff, format ve mypy başarılı; TypeScript/Vite üretim derlemesi başarılı. Birim kaynak testi: **2 geçti** (emoji/Türkçe code point aralığı ve yanlış revizyon/range reddi).
- Gerçek API kullanan **5 Playwright testi geçti**: graf/listeler/arama/kaynak, editör/konu/silme, 360 px/azaltılmış hareket/dış asset olmaması, konu yönetimi/readiness hata görünümü, 300 not/600 bağ sınırı.
- 300 not/600 bağ testinde yerel headless Edge, 1440×960, pan sırasında 900 ms rAF örneklemesi: son koşuda 125 örnek; p95 kare aralığı **7,1 ms**, en yüksek **20,8 ms**. Bu kısa ölçüm genel 60 FPS garantisi değildir. Ham kayıt `reports/frontend-e2e/performance.json`.
- Docker API/worker/migration/UI imajları derlendi; migration 005 kalıcı veriye uygulandı. Container içinden gerçek LM Studio probe ve yeni Nginx UI adresi üzerinden gerçek model HTTP smoke başarılı: oluşturma, kaynaklı cevap, değiştirme, silme, eski kanıtın kalkması.
- Doctor: Neo4j, modeller, API liveness/readiness, worker ve UI health kontrolleri başarılı.
- Konu rengi/üyeliği ve aktif revizyon/metin gerçek Neo4j yeniden başlatıldıktan sonra korundu; kontrol kendi oluşturduğu sentetik not/konuyu temizledi. Şema sürümü 5; kanıt `reports/workspace-live-verification.json`.
- Windows setup tekrar çalıştırıldı; `.env` hash'i değişmedi. Yeni UI ile başlatma/aynı komutu tekrarlama/HTTP smoke/durdurma testi geçti, deneme portları bırakıldı.
- Yeni arama terimlerini raw erişim loglarına yazmamak için Nginx ve Uvicorn raw access logları kapatıldı. Uygulamanın request ID/metot/yol logları sorgu metni içermez.
- Son Docker UI sürümü masaüstü ve 360 px boyutta gerçek API ile açıldı; tarayıcı hatası, dış asset isteği ve yatay taşma yok. Sentetik arama işareti API/UI container loglarında bulunmadı. Kanıtlar `reports/frontend-live/verification.json` ve `log-verification.json`.

İlk tam Python koşusunda bir eşzamanlı kayıt testi bağlantı havuzu zaman aşımı verdi (269 geçti / 1 başarısız). Aynı test tek başına ve son tam 272 test koşusunda geçti; koşu kaydı gizlenmedi. İlk frontend test düzeninde Vitest e2e dosyasını da toplamıştı; birim taraması `src` ile sınırlandırıldı. Son birim/tarayıcı koşuları başarılıdır.

Tarayıcı kanıtları `reports/frontend-e2e/` altındadır: `01-map.png`, `02-list.png`, `03-search.png`, `04-note.png`, `05-answer.png`, `06-mobile.png`, `07-offline-graph.png`. Hepsi ayrı bellek demosunda sentetik 51 not ile üretildi; kişisel notlar kullanılmadı. JSON test raporu ve başarısız koşuların izleri de aynı alandadır. Ekranlar ve raporlar yerel, git dışı kanıtlardır.

Testler, tarayıcıdaki uygulamanın gerçek API isteklerini kullanır; cevap/arama CRUD akışları mock edilmez. Demo sağlayıcı model kalitesi ölçümü değildir. Çevrimdışı kontrol, yüklenmiş grafın ağ yokken kullanılmasını ve dış asset isteği olmamasını doğrular; uygulamanın sunucusuz PWA olarak çalıştığı iddia edilmez.

## Açık sınırlar

- Anlamsal benzerlik ayrı dilimdir; hesaplanmış veri olmadığı için kontrol kapalıdır. Etiketler, otomatik konu önerileri ve doğrulanmış kişi türü filtresi bu dilime eklenmedi.
- Yerleşim oturum içinde kararlıdır; sürüklenen konumların tarayıcı yeniden açıldığında kalıcı olarak geri yüklenmesi eklenmedi. Konu adları/renkleri ve not üyelikleri kalıcı modda veritabanında saklanır.
- İlk yükleme hedefi 300 not/600 bağdır; geniş bir gerçek koleksiyonda bağımsız performans sertifikası verilmedi. Sınırı geçen veride konu/arama ve sonraki bölüm kullanılabilir.
- Önceden raporlanan gerçek model kalite sorunları bu arayüz çalışmasıyla çözülmüş sayılmaz. Geçerli kaynak aralığı anlamsal doğruluk garantisi değildir.
- Özgün bellek demosundaki altı not korunur ve yedeklenmiştir; kalıcı ortama otomatik taşınmadı. Dış erişim/kimlik doğrulama G aşaması bu teslimin kapsamı değildir.

## Çalıştırma

Yeni kurulum: `scripts/setup.ps1` ardından `scripts/start.ps1 -Mode demo`. Arayüz varsayılan `http://localhost:8501` adresindedir. Gerçek model için `-Mode live -Build`; mevcut modu yeniden derlemeden önce durdurun. Ayrıntılar [Windows kılavuzunda](windows.md).

Bu oturumdaki gerçek model arayüzü için hedef `http://127.0.0.1:28501`, API `http://127.0.0.1:28000` olarak ayrıldı. Özgün eski demo `8000/8501` portlarında korunur.
