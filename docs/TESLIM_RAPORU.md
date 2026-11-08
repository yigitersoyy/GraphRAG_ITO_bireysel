# Yerel kullanım teslimi

> Dönemsel tasarım/teslim kaydıdır. Güncel mimari, testler ve kullanım durumu:
> [Temizlik ve Python UI kararı](TEMIZLIK_VE_PYTHON_GECISI.md). Eski durum sayıları
> ve model ölçümleri güncel veritabanının veya model kalitesinin garantisi değildir.

Son ek kapsam tamamlandı: **Qwen3.5-9B**, tek seçimde **50 karışık dosya** ve
referansa göre açık zeminli dairesel graf. [Güncel kullanım ve kanıtlar](QWEN35_TOPLU_YUKLEME_VE_GRAF.md).
Aşağıdaki eski model kalite ölçümleri yeni modelin genel doğruluğunu belgelemiyor.

Tarih: 8 Kasım 2026.

Teslim kapsamı Windows üzerinde tek kullanıcılı, yerel LM Studio ve kalıcı Neo4j ile çalışan not/graf uygulamasıdır. Ana arayüz React/Nginx çalışma alanıdır. Eski bellek demosu ve içindeki altı not korunmuştur; yeni kalıcı depoya otomatik taşınmamıştır.

## Tamamlanan işler

- Kurulum, proje sahipliğiyle başlatma/durdurma, salt okunur doctor, yedekleme/geri yükleme ve kalıcı veri doğrulaması.
- Gerçek model/embedding bağlantıları, paylaşılan inference kilidi, iş lease/heartbeat/recovery ve değişen pipeline için yeni revizyonla yeniden deneme.
- İlişki merkezli kaynak alıntılı çıkarım; Türkçe proje adı sınırları, plan/olasılık/olumsuzluk ve tam kaynak aralıkları.
- Not/dosya ekleme, düzenleme, silme, konular, arama, sayfalama, graf, kaynak revizyonu ve kaynaklı soru-cevap.
- Yanlış veritabanı/programlama dili ikamesine karşı tür kontrolü. Aynı küçük modelin yorumu tek başına kesin ret sayılmaz; bir onarım sonrası belirsizlik kullanıcıya görünür. Bozuk şema/alınan kaynak, geçersiz atıf ve bilinen tür çelişkisi bu geri dönüşle kabul edilmez.
- Açık kesinlik/güncel kullanım sorularında kaynak yalnızca plan/olasılık veriyorsa, uygun koşullarda alıntıdan sınırlı bir kısmi cevap. Başka temsil edilmeyen kaynak, çelişki veya belirsiz varlık varsa bu tamamlayıcı kullanılmaz.

## Doğrulama

- PDF/Word ek kapsamıyla **343 Python testi doğrulandı**: 342 testlik koşu (185,19 saniye) ve ayrı çalıştırılan eşzamanlılık testi 1/1 (2,01 saniye). Tek tam koşu olarak sunulmaz; Windows takılması aşağıda ve [belge yükleme raporunda](BELGE_YUKLEME.md) kayıtlıdır. Önceki temel teslimde 327 test tek koşuda geçmişti. Ruff lint/format ve mypy (62 kaynak dosyası) başarılı.
- TypeScript/Vite üretim derlemesi ve **2 arayüz birim testi** başarılı. **6 gerçek API Playwright akışı geçti**, 26,5 saniye: PDF/Word önizleme/yükleme/düzenleme, kaynaklar ve uyarı görünümü, CRUD/konular, sayfalama, mobil/çevrimdışı varlıklar ve 300 not/600 bağ sınırı.
- Uyarı görünümü testinde gerçek API cevabına yalnızca tanı bayrağı eklenir; not/cevap/kaynak içeriği test tarafından üretilmez. Model kalitesi bu demo tarayıcı testinden çıkarılmaz.
- Önceki 8 not/12 soru kümesinde cevaplar değişmez kaynaklar üzerinde üç yöntemle yeniden ölçüldü: her yöntemde yanıtlanabilir **8/8**, yanıtsız soruda doğru çekimserlik **4/4**, recall **1,000**, hata **0**. Uyarılı cevaplar özgün alıntılara karşı ajan tarafından incelendi.
- Yeni **5 not/8 soru** üzerinde iki geçiş × üç yöntem = **48 model isteği**: her yöntemde cevap **12/12**, doğru çekimserlik **4/4**, kaynak recall **1,000**, hata **0**. Beş not işlendi; beş etiketli ilişki eksiksiz eşleşti. p95: vektör 7,47 sn, hibrit 7,80 sn, graf 7,49 sn. Kaynaklar ajan tarafından incelendi; bağımsız insan sertifikası değildir.
- Son arayüz üzerinden hem Türkçe hem İngilizce gerçek HTTP smoke başarılı: ekleme, idempotency, iki adımlı cevap/graf, kaynak aralığı, güncelleme, eski kaynağın kalkması, silme ve kaynak kalmayınca çekimserlik. Yalnızca smoke tarafından oluşturulan notlar temizlendi.
- Salt okunur doctor: 12/12 kontrol başarılı. API yeniden oluşturulduktan sonra UI container'ı değişmeden vekil bağlantısı hazır duruma geldi; Nginx yapılandırma kontrolü geçti.

Ham kanıtlar: `reports/tests-delivery-recheck.xml`, `reports/frontend-e2e/results.json`, `reports/evaluation-final-regression-r10/20261108T085137Z/report.json`. Geliştirme sırasında başarısız olan koşular korunur; ayrıntılar [geliştirme günlüğünde](KALITE_DOGRULAMA_V3.md).

Model kontrolü bir doğruluk garantisi değildir. Örneğin Ruby ve TypeScript'in dil, PostgreSQL ve SQLite'ın veritabanı olduğu gibi bilinen kategori bilgisi yalnızca yanlış tür ikamesini denetler; kullanıcının bu teknolojileri kullandığına dair bilgi üretmez. Kategori tanımları için örnek birincil kaynaklar: [Ruby](https://www.ruby-lang.org/en/), [TypeScript](https://www.typescriptlang.org/), [PostgreSQL](https://www.postgresql.org/), [SQLite](https://www.sqlite.org/). Katalog sınırlıdır; bilinmeyen/karışık adlar kesin sınıflandırılmaz. Genel bağımsız insan doğruluk sertifikası verilmez.

## Kullanım

Yeni notlar yapılandırılmış başlık/dosya ön ekinden otomatik konu düğümüne alınır;
örneğin `01_kvkk_…` aynı KVKK konusunu kullanır. Listeden sürükle-bırak veya konu
seçimiyle başka düğüme taşınabilir. Mevcut KVKK/BDDK notları kaynak revizyonları
değişmeden ayrıldı. [Konu gruplama ve taşıma doğrulaması](KONU_GRUPLAMA_VE_TASIMA.md).

Günlük kullanım için proje klasöründeki **`BASLAT.cmd`** dosyasına çift tıklayın.
Docker, yerel modeller ve proje servisleri hazırlanır; arayüz otomatik açılır.
**`DURDUR.cmd`** proje servislerini veri silmeden durdurur.
[Tek tık başlatma doğrulaması](TEK_TIK_BASLATMA.md).

Son ek kapsam: Excel `.xlsx` ve `.xls` dosyaları da aynı yükleme/önizleme/kaynak akışına
alındı. Sayfa ve hücre adresleri korunur; formüller yeniden hesaplanmaz. Gizli sayfa ve
satırlar da dahil edilir; kaydetmeden önce metni kontrol edin. Güncel biçim/sınır/test
ayrıntıları [belge yükleme rehberindedir](BELGE_YUKLEME.md).

Excel sonrası genel doğrulama: 359 test geçti; önceden bilinen Windows/Neo4j
eşzamanlılık testi ayrı denemede takıldı ve başarılı sayılmadı. Son 6 tarayıcı
testi dört yükleme biçimini de kapsayarak 42,2 saniyede geçti. Her iki Excel
biçimi gerçek yerel modelle kaynak alıntıları üzerinden doğrulandı.

Bu makinede arayüz: **http://127.0.0.1:28501**. API: `http://127.0.0.1:28000`. LM Studio açık ve yapılandırılan modeller erişilebilir olmalıdır.

Yeniden başlatma:

```powershell
.\scripts\start.ps1 -Mode live -ApiPort 28000 -UiPort 28501 -BoltPort 37687 -Neo4jHttpPort 37474
```

Arayüzde **Yeni not** ile metin eklenebilir veya `.pdf`, `.docx`, UTF-8 `.txt` / `.md` dosyası yüklenebilir. Çıkarılan metin kaydetmeden önce kontrol edilip düzenlenebilir. İşleme durumu hazır olduktan sonra soru, kaynak ve graf kullanılabilir. Konu atamaları kullanıcı tarafından yapılır. Yeni gerçek belgeler mevcut deneme verisi otomatik silinmeden yüklenebilir. PDF/Word kullanıcı isteğiyle ilk teslimden sonra eklendi; [belge yükleme rehberi](BELGE_YUKLEME.md).

## Kapsam sınırları

- PDF ve Word (.docx) içe alma ek kapsam olarak tamamlandı. Otomatik OCR ve eski `.doc` biçimi desteklenmez. Sınırlar ve metin çıkarma ayrıntıları [belge yükleme rehberinde](BELGE_YUKLEME.md).
- Ağdan/çok kullanıcılı erişim açılmadı; loopback korunur. Kimlik doğrulamalı dış erişim ana planın koşullu G aşamasıdır.
- Otomatik konu/etiket/kişi tahmini, anlamsal benzerlik katmanı ve bütün notların sınırsız graf çizimi eklenmedi. Liste/aramanın tamamı kullanılabilir; harita 300 not/600 bağ ile sınırlıdır.
- Aynı modelin anlamsal incelemesi yanılabilir. Özellikle kaynak kontrolü uyarısında alıntılar okunmalıdır. Bu, otomatik testlerin veya sağlık probe'unun model doğruluğunu sertifikaladığı anlamına gelmez.

## Son ölçümün tekrarlanabilirliği ve servis teslimi

Nihai ölçüm: `reports/evaluation-delivery-holdout4/20261108T085847Z-34dc37/report.json`.
Dondurma kaydı: `reports/delivery-freeze.json`. Ölçüm sonrası model, prompt, veri ve eşik ayarı yapılmadı.
Sonrasında yalnızca İngilizce WH sorularında Türkçe özel ad yüzünden yanlış dilde yokluk mesajı
seçilmesi düzeltildi ve API yeniden oluşturulduğunda Nginx'in eski IP tutması giderildi.
Bu nedenle `service.py` kaynak özeti eski dondurma kaydıyla bit düzeyinde aynı değildir;
model değerlendirmesini son sunum/servis yamalarıyla yeniden koşulmuş gibi göstermiyoruz.
Nginx çözümü [resmî proxy açıklamasına](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass)
ve [Docker DNS hizmetine](https://docs.docker.com/engine/network/#dns-services) dayanır.
Yerel servis kanıtları: `reports/delivery-dns-recreation.json`, `reports/delivery-doctor.json`,
`reports/delivery-original-data-check.json` ve `reports/delivery-final-state.json`.

Windows üzerinde tam test tekrarlarından ikisi eşzamanlı Neo4j gönderiminde sürücünün
`BoltSocketBase.at_eof` havuz kontrolünde takıldı. Yığınlar saklandı; yalnızca bu teste ait
Python süreçleri durduruldu. Önceki 326 testlik tam koşu başarılıdır; takılan tekrar başarılı
sayılmaz. Genel kök neden henüz kanıtlanmadı; uygulamanın Docker servisleri ve canlı
Türkçe/İngilizce akışlarında aynı sorun gözlenmedi. Temiz yeniden koşuda **327/327 test**
140,39 saniyede geçti; atlanan/başarısız yok. Test takılması giderilmiş sayılmaz;
tekrar ederse sürücü/havuz sorunu ayrıca incelenmelidir. Son test için kullanılan ayrı
Neo4j container'ı durdurulur; kalıcı kullanıcı verisi ve eski demo servisleri korunur.

Son canlı Edge kontrolünde aynı origin üzerinden API/arama, 360 px mobil görünüm ve
yerel varlıklar doğrulandı: tarayıcı hatası, dış ağ isteği ve yatay taşma yok.
Kanıt: `reports/frontend-live/verification.json` ve aynı klasördeki ekran görüntüleri.
