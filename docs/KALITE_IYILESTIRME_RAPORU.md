# Kaynak ve model kalitesi — 7 Kasım 2026

> Dönemsel tasarım/teslim kaydıdır. Güncel mimari, testler ve kullanım durumu:
> [Temizlik ve Python UI kararı](TEMIZLIK_VE_PYTHON_GECISI.md). Eski durum sayıları
> ve model ölçümleri güncel veritabanının veya model kalitesinin garantisi değildir.

Ana planın D devamı kapsamında kaynak zinciri, belirsizlik etiketleri, konu dışı cevapta çekimserlik ve güvenli yeniden işleme ele alındı. Genel model kalitesi henüz onaylanmadı. Arayüz tasarımı değiştirilmedi.

## Uygulanan değişiklikler

- Structured output şemasında `$ref` çözülürken kaybolan alan açıklamaları korunur. Çelişen doğrulama kısıtları gevşetilmez. `POSSIBLE`/`PLANNED` ve olumsuzluk açıklamaları modele gerçekten ulaşır.
- Çıkarım yönergesi varlık türlerini, Türkçe proje adı sınırlarını ve ilişkiye özgü kipleri açıklar. Onarım özgün not üzerinden bir kez yapılır. Geçersiz ilişki sessizce boş başarılı sonuca dönüştürülmez.
- Çıkarım sürümü `extract_v4_typed_qualifiers` oldu. Kuyruktaki revizyon farklı pipeline fingerprint'i taşıyorsa `PIPELINE_CHANGED` ile durur. Kullanıcının yeniden denemesi yeni revizyon/iş üretir; eski aşamalı çıktılar yeni profille karıştırılmaz. Yayımlanmış notlar otomatik yeniden işlenmez.
- Cevap yönergesi, sorulan özellik kaynaklarda yoksa başka doğru bilgilerle cevap vermek yerine çekimserlik ister. `answered` ile eksik bilgi listesi birlikte kabul edilmez.
- Mevcut graf iddialarında soru varlığından cevap varlığına bir/iki adımlı yol varsa atıfların bütün halkaları kapsaması denetlenir. Eksikte en fazla bir yeniden üretim istenir; uygulama kendiliğinden atıf eklemez. Kontrol anlamsal doğruluk/ilgililik ölçütü değildir; eksik çıkarımı tamamlamaz veya eş adlı varlıkları çözmez. Graf iddiası olmayan ham metin cevapları engellenmez.
- Cevap grafındaki kenarlar değişmez kaynak revizyonu, alıntı ve karakter aralığı taşır. Arayüzün kenar/kaynak listesi bu veriyle doğru revizyonu açar.

## Ölçüm düzeni

Aynı Qwen3 8B Q4_K_M, 8192 bağlam, `/no_think`, sıcaklık 0,2 ve Nomic v1.5 768 boyut profili korundu. Eşikler değiştirilmedi. Normal gerçek model API/worker ölçüm sırasında durduruldu. Her küme yeni, boş ve ayrı Neo4j volume'unda çalıştı; kullanıcı notları değerlendirmeye alınmadı.

Başlangıç kümesi geliştirme içindir. Önceki doğrulamanın hataları incelendiği için artık regresyon kümesidir. Yeni 8 not/10 soruluk holdout sonuçları görülmeden yazıldı; kod/veri/eşik hash'leri son ölçüm öncesinde `reports/quality-freeze.json` dosyasına kaydedildi. Holdout sonuçlarına göre bu teslimin prompt veya eşikleri ayarlanmaz. Veri ajan tarafından yazılmıştır; bağımsız insan değerlendirmesi değildir.

## Başlangıç ve regresyon

| Küme / yöntem | İşlenen not | Kanıt recall | Yanıtsız soruda doğru çekimserlik | Soru hatası | Cevap p95 |
| --- | --- | --- | --- | --- | --- |
| Başlangıç / vector | 7/9 | 0,864 | 5/5 | 0 | 5.046 ms |
| Başlangıç / hybrid | 7/9 | 0,864 | 5/5 | 0 | 4.040 ms |
| Başlangıç / graph | 7/9 | 0,864 | 5/5 | 0 | 4.245 ms |
| Regresyon / vector | 6/6 | 1,000 | 2/2 | 0 | 4.835 ms |
| Regresyon / hybrid | 6/6 | 1,000 | 2/2 | 0 | 5.053 ms |
| Regresyon / graph | 6/6 | 1,000 | 2/2 | 0 | 5.286 ms |

Her iki kümede bir geçiş yapıldı; aynı soru üç yöntemde ayrı ayrı soruldu. Başlangıç recall eşiği geçmediği ve iki ingestion başarısız olduğu için değerlendirme komutu başarısız döndü. Hatalar paydadan çıkarılmadı. Gecikmeler yerel ölçümdür; önceki koşularla farkı tek başına hızlanma kanıtı değildir.

Ham başlangıç raporu: `reports/evaluation-quality-baseline-v2/20261107T202740Z-6c6043/report.json`. Regresyon: `reports/evaluation-quality-regression-v2/20261107T203233Z-8b0350/report.json`.

Önceki başlangıç graf ölçümünde 4/5 olan doğru çekimserlik bu koşuda 5/5 oldu. İstanbul ofisi sorusunda ilgisiz Atlas bilgisi verilmedi; ilgili not işlenemediği için çekimser kalındı. Bu cevaplanabilir sorunun çözülmesi değildir. Grace'in programlama dili sorusunda veritabanı/proje bilgisi cevap olarak sunulmadı.

Regresyonda etiketlenmiş yedi ilişki beklenen ad/ilişki/olumsuzluk/kip karşılaştırmasında tam eşleşti; eksik/fazla ilişki yok. Daha önce yanlış `PLANNED` olan “gelecek yıl Neo4j kullanabilir” ilişkisi `POSSIBLE` çıktı. Ece → Project Vega → Redis cevabı üç yöntemde de atama ve depolama notlarının ikisini kaynak gösterdi. Önceki vektör ölçümünde atama kaynağı eksikti. Çelişen Orion kaynaklarının ikisi ve olasılık ifadesi cevapta korundu; bu küçük örnekler genel anlamsal başarı garantisi değildir.

## Ayrılmış son ölçüm

| Yöntem | İşlenen not | Kanıt recall | Doğru çekimserlik | Soru hatası | Cevap p95 |
| --- | --- | --- | --- | --- | --- |
| vector | 8/8 | 1,000 | 4/6 | 0 | 5.052 ms |
| hybrid | 8/8 | 1,000 | 4/6 | 0 | 4.973 ms |
| graph | 8/8 | 1,000 | 4/6 | 0 | 5.535 ms |

İki geçiş × 10 soru × 3 yöntem = 60 istek. Her yöntemde üç yanıtsız soru iki kez sorulduğu için çekimserlik paydası altıdır. Bütün alıntı aralıkları yapısal olarak geçerli; eşikler çekimserlik nedeniyle geçmedi. Ham rapor: `reports/evaluation-quality-holdout-v2/20261107T203647Z-d00367/report.json`.

- Aylin → Proje Kuzey → Redis ve Rana → Project Cedar → PostgreSQL cevaplarında her iki kaynak da üç yöntemde ve iki geçişte yer aldı. Olumsuz MongoDB kullanımı ve Harbor için yalnızca olasılık anlamı korundu. Graf iddiası üretilmeyen Ankara notu metinden cevaplandı.
- **Kip hatası:** `h04` onaylanmış planı model `ASSERTED` çıkardı; beklenen `PLANNED`. Etiketlenmiş sekiz ilişkinin yedisi tam eşleşti. Cevaplar kaynak metni kullanıp plan anlamını korusa da graf etiketi yanlıştır. D14 genel kabulü açık kalır.
- **İlgisiz cevap:** `h-q10` “Rana hangi programlama dilini kullanıyor?” sorusuna her yöntem iki geçişte de “Rana uses PostgreSQL” dedi. Proje planından kişinin becerisi çıkarılamaz. İki geçerli atıf ve tam graf zinciri bu hatayı önlemedi. D16 genel kabulü açık kalır.
- **Gereksiz çekimserlik:** `h-q06` için vector/hybrid iki geçişte de iki kaynak bulunmasına rağmen cevap vermedi. Graf yöntemi iki kaynağın ifadelerini birlikte gösterdi. Notlar iki teknolojinin beraber kullanılabileceğini dışlamadığından bunu zorunlu bir mantıksal çelişki saymak yerine iki kaynak ifadesini korumak gerekir; veri kümesindeki “conflicting” inceleme yönergesi bu açıdan dar bir değerlendirme varsayımıdır. Ham veri/etiketler sonuca göre değiştirilmedi.

Sonuçlar görüldükten sonra dondurulan kod, veri ve eşikler değiştirilmedi. Bütün gerçek cevaplar ilk üretimde biçim/kaynak zinciri kontrolünden geçti; eksik zincirde yeniden üretim davranışı otomatik testte zorlandı. Ajan incelemesi insan onayı yerine geçmez; ham raporlardaki insan anlamsal inceleme alanları beklemede kalır.

Holdout boyunca örneklenen tüm sistem RAM tepesi 29.592.625.152 bayt, GPU tepesi 5.500 MiB. Diğer uygulamalar dahildir; 2 saniyelik örnekleme tam süreç belleği ölçümü değildir. İlk geçiş modelin diskten soğuk yüklenmesini ölçmez.

## Açık kalan D13

Başlangıçtaki iki Türkçe not (`n05`, `n08`) son uçtan uca koşuda hâlâ `EXTRACTION_INVALID` verdi. Tekil denemelerde `n08` bazen doğru ilişki türünü üretse de “Project Borealis” adını “Borealis” olarak kısalttı; bu kimlik bölünmesi riski nedeniyle çözülmüş sayılmaz. `n05` için model, ofis/bütçe arasında desteklenmeyen veya türü uyumsuz ilişki üretmeye devam etti. Şema biçiminin geçerli olması ilişki anlamını güvenilir yapmıyor.

Sıradaki işler:

1. D13: mevcut profille karşılaştırılacak ayrı bir çıkarım modeli veya ilişki merkezli şema denemesi. Kabul: iki notun farklı tekrarlarında kararlı sonuç, tam proje adı, kaynakla desteklenen tür/ilişki ve diğer örneklerde regresyon olmaması.
2. D14: hem olasılık hem açık onaylanmış plan örneklerinde doğru graf kipleri; `h04` bu aşamada regresyon örneğidir.
3. D16: sorulan özellik/özne ile cevabın anlamsal uygunluğunu ayrıca doğrulama; `h-q10` yanlış cevabını ve `h-q06` gereksiz çekimserliğini birlikte ele alma. Kaynak zinciri denetimi tek başına yeterli değildir.

Başarısız çıkarımı boş sonuca zorlamak veya test sorularına özel kural yazmak çözüm kabul edilmez. Yeni değişiklik sonrası mevcut holdout artık regresyon verisidir; yeni bir ayrılmış değerlendirme gerekir.

## Son doğrulama

- Tam Python koşusu **281 geçti**, başarısız/atlanan yok; 240,32 saniye. Bir mevcut Starlette/httpx deprecation uyarısı var. `reports/quality-tests-final.xml`.
- Ruff lint/format ve mypy (58 kaynak dosyası) başarılı. Eklenen Playwright testi Prettier kontrolünden geçti.
- **5 gerçek API Playwright testi geçti**, 17,8 saniye. Cevabın destekleyici ilişki listesinden değişmez kaynak revizyonunu açma ve alıntı vurgulama dahildir. `reports/frontend-e2e/results.json`.
- İlk tam koşu 274 geçti / 1 başarısız / 6 kurulum hatası verdi: Windows genel pytest geçici dizinine izin yoktu; `--basetemp` proje içine alındı. Ayrı süreç testinin alt süreci yerel `.env` model ayarlarını okuyordu; göndericiyle aynı fingerprint ayarları açıkça geçirildi. Önce sorunlu 7 test, sonra bütün 281 test geçti. İlk tarayıcı ek testi graf görünümünde listeyi bekledi; liste görünümüne geçiş düzeltildikten sonra bütün beş test geçti. Başarısız koşu kanıtları silinmedi.
- Yeni wheel ve API/worker/migration Docker imajları üretildi. Özgün bellek demosu salt okunur kontrol edildi: altı not erişilebilir. Ayrı test/değerlendirme servisleri volume'ları korunarak durduruldu.
- Canlı API/worker yeni imajlarla aynı Neo4j volume'unda açıldı; şema 5 korundu. Nginx yeniden başlatıldı. Container içinden model listesi, iki dilde sohbet, structured output, 768 boyut embedding ve retrieval probe başarılı olup kaydedildi.
- Gerçek UI proxy'si `http://127.0.0.1:28501` üzerinden **İngilizce ve Türkçe HTTP smoke geçti**: not oluşturma, idempotency, iki adımlı kaynaklı cevap, kesin alıntı aralığı, graf, değiştirme, eski kanıtın kalkması, silme ve silme sonrası çekimserlik. Yalnızca bu kontrollerin oluşturduğu sentetik notlar temizlendi. Kayıtlar: `reports/quality-live-smoke-en.txt`, `quality-live-smoke-tr.txt`.
- Son salt okunur doctor kontrolünde API liveness/readiness, worker heartbeat, UI, Neo4j ve model erişimi başarılı: `reports/quality-live-doctor.json`. API `http://127.0.0.1:28000`, UI `http://127.0.0.1:28501`; erişim loopback olarak kaldı. Eski demo `8000/8501` portlarında korunur.

Bu teslim altyapı ve kaynak doğrulama iyileştirmesidir; tamamlanmış model kalite onayı değildir.
