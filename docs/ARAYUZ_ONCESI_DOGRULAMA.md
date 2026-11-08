# Arayüz öncesi uygulama ve doğrulama

> Dönemsel tasarım/teslim kaydıdır. Güncel mimari, testler ve kullanım durumu:
> [Temizlik ve Python UI kararı](TEMIZLIK_VE_PYTHON_GECISI.md). Eski durum sayıları
> ve model ölçümleri güncel veritabanının veya model kalitesinin garantisi değildir.

Tarih: 7 Kasım 2026  
Kapsam: `MIMARI_VE_YAPILACAKLAR.md` içindeki A–D aşamaları ve bu değişikliklerin test/dokümantasyonu. **Bu rapor arayüz öncesi A–D doğrulamasının tarihsel kaydıdır. E sonradan onaylanıp uygulandı; güncel durum [UI uygulama raporundadır](ARAYUZ_UYGULAMA_RAPORU.md). G dış erişim bekler.**

## Uygulanan altyapı

- Windows için kilitli kurulum, mod seçerek başlatma/durdurma, loglar, süreç sahipliği, port çakışması ve tekrar başlatma kontrolü.
- Salt okunur teşhis; yapılandırma, Docker, Neo4j, API/readiness, worker, model listeleri ve mevcut arayüz sağlığı.
- Ayrı bellek demosu, kalıcı demo ve gerçek model çalışma yolları. Kalıcı demo ve gerçek kullanımın Compose proje/volume'ları ayrıdır.
- Ana makine/container model adresleri ayrıldı. Model bağlamı, token bütçeleri, kimlik bilgileri, zaman aşımı ve bakım ayarları servisler arasında aktarılıyor.
- API/worker ve mevcut UI için ayrı Docker build target'ları; kilit dosyasından Linux/Python 3.12 wheel hazırlığı. UI kaynaklarında tasarım veya akış değişikliği yapılmadı.
- Windows'tan çalışan Neo4j yedekleme ve yalnızca boş hedefe geri yükleme; bellek demosunun aktif/bekleyen not revizyonlarını dışa aktarma.
- Extraction ve answer modellerini ayrı ayrı kontrol eden probe; farklı embedding endpoint/token desteği, modele uygun sorgu/belge ön işleme ve etkili ayarları kapsayan profil kaydı.
- Demo ayarları gerçek embedding ön işleme ayarlarından ayrıldı; gerçek mod başarısız olduğunda demo sağlayıcıya sessiz dönüş yapılmıyor.
- Gerçek modellerle ayrı, boş Neo4j üzerinde değerlendirme; veri silme yapılmıyor. Aynı işlenmiş notlar üç arama yöntemi için kullanılıyor. Başarısızlıklar rapordan çıkarılmıyor.
- Ayrı geliştirme/doğrulama verisi, soru bazında kaynak/cevap çıktıları, çıkarım karşılaştırması, gecikmeler, bekleme, RAM/VRAM ve yapılandırma/hashi içeren JSON/Markdown raporları.

## Gerçek model denemelerinde bulunan ve düzeltilen sorunlar

1. **Yanlış karakter konumları:** LLM'nin sayısal konum tahminleri güvenilir değildi. Yeni çıkarım şeması yalnızca birebir alıntıyı ister; kaynakta tek bir yerde bulunan alıntının konumunu sunucu belirler. Kaynakta olmayan veya belirsiz alıntı reddedilir. Eski sayısal çıktılar da doğrulanır.
2. **Eksik JSON alanları:** Python tarafındaki varsayılan değerler yüzünden cevap cümleleri model çıktısında tamamen atlanabiliyordu. İletilen cevap şeması artık cümle ve alıntı alanlarını zorunlu tutar. Şema sürümü de modelin tahminine bırakılmaz.
3. **Dar kurtarma bütçesi:** Dört tokenlık kontrol Qwen3'ün son yanıtı üretmesine yetmiyordu. Kurtarma kontrolü 64 token kullanır; başlangıç probe'u eski bir sürecin lease'inin güvenle dolmasını bekleyebilir.
4. **Boşta kalan süresi dolmuş slot:** Worker, yeni bir kullanıcı isteği gelmeden süresi dolmuş inference sahibini önce fence edip sonra probe ile toparlayabilir. Taze bir sahibin slotuna girmez.
5. **Uzun işte lease kaybı:** Worker iş sırasında yalnızca inference slotunu canlı tutuyordu. Artık işin kendi lease'i de token kontrolüyle yenilenir; işleme süresince worker heartbeat'i güncel kalır. Eski, iptal edilmiş veya süresi dolmuş iş sahibi yeniden canlandırılmaz. Şema migration dosyaları değiştirilmedi.

## Kullanılan yerel profil

| Bileşen | Profil |
| --- | --- |
| İşletim sistemi | Windows 11 |
| Host Python | 3.12.10 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |
| Host RAM | 33.982.464.000 bayt; yaklaşık 31,65 GiB |
| LM Studio | 0.4.28+2; CLI commit `43d4b26` |
| Seçilen sohbet modeli | Qwen3 8B, Q4_K_M; sunulan kimlik `graphrag-chat-qwen3` |
| Sohbet ayarları | 8192 bağlam, GPU offload 0.8, parallel 1, sıcaklık 0.2, açık `\n/no_think` son eki |
| Embedding modeli | Nomic Embed Text v1.5, Q4_K_M; kimlik `graphrag-embed`, CPU, ölçülen boyut 768 |
| Embedding ön işleme | Belge `search_document: `; sorgu `search_query: {question}` |
| Neo4j | 5.26.32 Community, uygulama şema sürümü 4 |

Qwen 2.5 7B de denendi; bazı varlık referanslarını ve Türkçe çıkarımları doğrulamadan geçiremedi. Bu başarısız ölçümler korundu. Model değişimi yeni model kimliği ve güncellenmiş probe ile yapıldı; yeni ağırlık indirilmedi.

## Operasyonel kanıtlar

| Kontrol | Sonuç |
| --- | --- |
| Windows kurulumunu tekrar çalıştırma | Mevcut `.env` hash'i değişmedi; kilitli kurulum başarılı. |
| Demo başlatma ve aynı komutu tekrarlama | İkinci servis oluşturulmadı; HTTP smoke geçti. |
| Yönetilen demoyu durdurma | Deneme portları bırakıldı; özgün demo kapatılmadı. |
| Salt okunur doctor | Özgün demo üzerinde tüm kontrol satırları başarılı. |
| Kalıcı demo yeniden başlatma | Aynı revizyon metni, graf ve alıntılar korundu. |
| Yedekten dönüş | Yeni boş volume'da metin/graf doğrulandı; şema 4, indeksler online. |
| Gerçek LM Studio probe | Container içinden model, iki dilde completion, JSON şeması, boyut ve arama örneği başarılı. |
| İngilizce ve Türkçe gerçek HTTP smoke | Not oluşturma, işleme, kaynaklı cevap, graf, değiştirme ve silme başarılı. Modelin `partial` etiketi ayrıca kaydedildi. |
| Gerçek provider timeout | `PROVIDER_TIMEOUT`, `RECOVERING` ve gerçek endpoint probe'u ile toparlanma doğrulandı. |
| Yanlış model/boyut, kesilmiş çıktı, kapalı endpoint | Özgül hata kodları doğrulandı. |
| Gerçek worker çökmesi | Model çağrısı sırasında süreç öldürüldü; container yeniden başladı ve iş attempt 2 ile tamamlandı. |
| Eşzamanlı API/worker trafiği | İki API sorusu HTTP 200 döndü; eşzamanlı ingestion tamamlandı. Sonrasında slot IDLE. |
| Model token reddi | HTTP sözleşme simülatörü ile test edildi. Gerçek yerel LM Studio'da kimlik doğrulama kapalı; gerçek 401 testi yapılmış sayılmıyor. |

Yedekleme kaynak container'ı kısa süre durdurdu. Sadece bu çalışmanın sentetik notlarıyla test yapıldı. Özgün bellek demosundaki notların yedeği `reports/backups/` altında tutuluyor; otomatik veri taşıma yapılmadı.

Yerel kanıt dosyaları: `reports/persistence-verification.json`, `reports/live-fault-verification.json`, `reports/live-concurrency-verification.json`, `reports/model-profile-qwen3.json`. Bu dosyalar ve not yedekleri git dışında tutulur.

## Otomatik testler ve canlı kalite ölçümleri

**Tam test paketi: 256 geçti, atlanan/başarısız test yok; 184,53 saniye.** Bir mevcut Starlette/httpx deprecation uyarısı var. Neo4j testleri ayrılmış test veritabanında çalıştırıldı. Ruff, biçim ve mypy kontrolleri de başarılıdır.

| Küme / yöntem | İşlenen not | Kaynak recall | Doğru çekimserlik | Cevap p95 |
| --- | --- | --- | --- | --- |
| Başlangıç / vector | 7/9 | 0,864 | 5/5 | 4385 ms |
| Başlangıç / hybrid | 7/9 | 0,864 | 5/5 | 4999 ms |
| Başlangıç / graph | 7/9 | 0,864 | 4/5 | 6292 ms |
| Doğrulama / vector | 6/6 | 1,000 | 4/4 | 4871 ms |
| Doğrulama / hybrid | 6/6 | 1,000 | 4/4 | 5171 ms |
| Doğrulama / graph | 6/6 | 1,000 | 4/4 | 4922 ms |

Başlangıç kümesi yöntem başına 16 soru/tek geçiş; doğrulama yöntemi başına 8 soru/iki geçiştir. Soru çağrılarında hata yoktur; başlangıç kümesindeki `n05` ve `n08` notları `EXTRACTION_INVALID` ile başarısızdır. Bunlar recall hesabında tutuldu. Başlangıç kümesi hedefleri geçmedi; doğrulama sayısal hedefleri geçti. Modeller önceden yüklüydü: ilk geçiş gerçek model yükleme soğuğu değildir. Doğrulama sıcak p95: vector 5066, hybrid 4603, graph 4922 ms.

Doğrulama boyunca örneklenen tüm makine tepe RAM değeri 30.862.348.288 bayt (28,74 GiB), GPU tepe kullanımı 5685 MiB; örnekleme aralığı 2 saniye. Diğer uygulamalar bu değerlere dahildir.

**Ajanın anlamsal incelemesi:** Doğrulamada olumsuzluk, çelişen iki kaynak, Türkçe cevap, eş adlı varlık ve yanıtsız sorular iki geçişte korundu. Ancak vektör yöntemindeki Ece→Vega→Redis cevabı doğru olmasına rağmen yalnızca veritabanı notunu kaynak gösterdi; Ece→Vega halkasının atfı eksik. Hibrit/graf bu soruda iki notu da gösterdi. `v05` çıkarımında “kullanabilir” için beklenen `POSSIBLE` yerine `PLANNED` üretildi (etiketli 7 ilişkinin 6'sı tam eşleşti); cevap metni olasılığı korudu. Başlangıç grafında `q08` ve `q16` kaynaklı fakat soruya cevap vermeyen cümleler üretti; bunlar anlamsal başarı sayılmadı. Bağımsız insan incelemesi yapılmadı; otomatik raporların `quality_approved` değeri false kalır.

Yerel raporlar: `reports/evaluation-qwen3-baseline/20261107T114917Z-95e0c3/report.json`, `reports/evaluation-qwen3-validation/20261107T115437Z-7fbf17/report.json`; ajan inceleme kaydı `reports/semantic-review.md`. Önceki başarısız Qwen 2.5 ölçümleri de korundu.

Kalite eşiği örneği `evaluation/thresholds.example.json` içindedir: hibrit/graf için kaynak recall en az 0,90; yanıtsız sorularda doğru çekimserlik 1,00; soru hatası 0; uçtan uca p95 en fazla 30 saniye. Bunlar başlangıç mühendislik hedefleridir; küçük veri kümesinde geçmeleri genel model kalitesi onayı değildir.

## Kalan sınır

- **E sonradan uygulandı:** Ana UI `frontend/` altında yeni React çalışma alanıdır; eski `ui/` kaynakları korunur. Güncel doğrulama UI uygulama raporundadır.
- **G beklemede:** Dış erişim/kimlik doğrulama kurulmadı; yayın portları loopback üzerinde tutuldu.
- Yapısal olarak geçerli alıntı, cevabın anlamsal doğruluğunu tek başına kanıtlamaz. Küçük sentetik kümeler geniş gerçek not koleksiyonunun yerine geçmez.
- RAM/VRAM sayıları örneklenmiş tüm makine değerleridir. Model sürecine ait kesin tepe bellek veya bağımsız performans sertifikası değildir.
- Demo notlarının kalıcı gerçek ortama taşınması, arayüz ve kullanım tercihi netleşince ayrıca ele alınır.

## Arayüz öncesi teslim anındaki servisler (tarihsel)

- Özgün bellek demo API'si `127.0.0.1:8000`, mevcut arayüzü `127.0.0.1:8501` üzerinde korundu; altı notun güncel dışa aktarımı alındı.
- Gerçek model API/worker/Neo4j son imajla başlatıldı; API `127.0.0.1:28000`, Neo4j Bolt `127.0.0.1:37687`. Bu çalışma için gerçek modele bağlı yeni UI başlatılmadı (`-NoUi`). Doctor kontrolleri başarılıdır.
- Kalıcı demo API/UI `18000/18501` portlarında çalışır. Değerlendirme ve test veritabanları durduruldu; volume'lar korundu.
- Bu adresler son yerel oturum durumudur; yeniden başlatma komutları `docs/windows.md` içindedir.
