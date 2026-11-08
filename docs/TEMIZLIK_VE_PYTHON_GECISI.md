# Temizlik ve koşullu Python UI geçişi

Başlangıç: `c7c8f04`. Dal: `cleanup-python-ui`. Uygulama durumu bu dosyada izlenir.
Hedef tek desteklenen arayüz, korunan kullanıcı verisi ve daha az yinelenen koddur.
NiceGUI ancak mevcut işlev, görünüm ve performans ölçütleri sağlanırsa React'in yerini alır.

**Karar: React tek desteklenen arayüz olarak korundu.** NiceGUI 4.0.0 prototipi,
tarayıcıdaki graf motorunun Vue reaktivitesinden ayrılmasından sonra hareket
performansını geçti; ilk kullanılabilir graf süresini geçemedi. Tam UI göçü ve
NiceGUI Docker geçişi bu koşul nedeniyle uygulanmadı. Ana ortamda NiceGUI bağımlılığı,
ikinci UI servisi veya prototip kaynakları bulunmaz.

## Ölçülen geçiş kararı

300 sentetik not, aynı Edge işlemi, UI başına üç ayrı soğuk tarayıcı bağlamı,
1440×960. Yerel deneydir; frameworkler hakkında genel performans iddiası değildir.

| Ölçüm (üç koşunun ortancası) | React | NiceGUI 4.0.0 | NiceGUI kabul sınırı |
| --- | --- | --- | --- |
| İlk kullanılabilir graf | 1.901 ms | 3.216 ms | ≤ 2.626 ms — geçmedi |
| Pan p95 kare süresi | 27,7 ms | 7,5 ms | ≤ 34,6 ms — geçti |

Prototipte yerel Cytoscape 3.34.4, mevcut CSS, kapalı Tailwind, üretim JS dosyaları,
yeniden yükleme kapalı tek UI worker, async API istemcisi ve ham graf verileri
kullanıldı. İlk yanlış reaktif köprü düzeltildi; karar düzeltilmiş ikinci koşuya aittir.
Graf/konu/seri/varlık, kamera, seçim ve soru vurgusu denendi. Erken açılış kapısı
geçilemediği için eksik CRUD/yükleme ekranları tamamlanmış gibi raporlanmaz.

NiceGUI ayrı ortamda backend dahil 60 paket istedi; ana runtime 27 pakettir.
Temiz proje kilidi geliştirme araçları dahil 69'dan 44 pakete düştü. NiceGUI'nin
üretim imajı kurulmadığından karşılaştırmalı imaj boyutu iddiası yoktur.
Üretim wheelhouse'u artık yalnızca 28 backend/app wheel'i içerir; eski Streamlit
wheel önbelleği Docker'a kopyalanmaz.

Tekrar ölçüm: boş memory-demo API açıkken `cd frontend` ve `npm run benchmark`.
Araç canlı/Neo4j API'yi ve dolu demo ortamını reddeder; yalnızca kendi test notlarını
oluşturup siler. React/NiceGUI karşılaştırma kanıtı yerel `reports/ui-benchmark/` altında.

## İlerleme

- [x] Canlı 49 belgenin tamamı READY; model profili ve servis imajları kaydedildi.
- [x] React imajı `notes-graphrag-react-baseline:c7c8f04` adıyla korundu.
- [x] Tam Neo4j dump, düğüm/ilişki özellik özetleri ve okunabilir dışa aktarım oluşturuldu.
- [x] Ayrı boş volume'e geri yükleme: 1.367 düğüm / 1.630 ilişkinin tüm özellikleri eşleşti.
- [x] Eski Streamlit kapsamını devretme, bağımlılık/build temizliği.
- [x] Python yardımcılarının, sağlık kontrollerinin ve graf serileştirmesinin sadeleştirilmesi.
- [x] Sabit demo verisiyle React başlangıç ölçümleri ve testler.
- [x] Ayrı NiceGUI prototipi ve karşılaştırmalı geçiş kararı: React korundu.
- [x] Karara göre tek UI, Docker/lifecycle/CI güncellemesi ve son doğrulama.

## Streamlit testlerinin karşılığı

| Önceki senaryo | Korunacak doğrulama |
| --- | --- |
| Zararlı başlığın güvenli gösterimi | Tarayıcıda metin olarak başlık, script çalışmaması |
| Geçersiz kaydı düzeltip yeniden gönderme | Tarayıcıda boş metin sonrası geçerli kayıt |
| Not ekleme, cevap ve kaynak gösterimi | Mevcut gerçek demo API tarayıcı testi |
| Düzenleme ve silme | Mevcut CRUD tarayıcı testi |
| Başarısız iş ve tekrar deneme | Backend API/worker testleri; UI tekrar deneme kontrolü |
| Yetersiz kanıtın uyarı olarak gösterimi | Tarayıcı soru akışında yanıtsız soru |
| API kesilmesi | Bağlantı/readiness testi ve yeniden deneme isteğinde 503 gösterimi |
| Unicode ve güvenli alıntı | Metin yardımcı testi ve kaynak tarayıcı testi |

## Uygulanan temizlik

- Streamlit UI, iki test dosyası, Docker legacy hedefi ve isteğe bağlı UI grubu kaldırıldı.
- `_WORD`, kullanılmayan fake `cosine` ve yinelenen memory kosinüs hesabı temizlendi.
- Boş cluster canvas ve her render/pan/zoom'daki temizleme işi kaldırıldı.
- Sağlık istemcileri `/health/ui` kullanıyor; eski adres bir uyumluluk alias'ı.
- Graf JSON üretimi route'lar arasında özel fonksiyon ithal etmek yerine ortak view'da.
- Soru alanı mevcut 2.000 karakterlik backend sınırıyla uyumlu.
- Shell arşiv komutları ortak Python uygulamasına yönlendiriliyor. Dolu restore hedefi
  reddedilir; yazılamayan backup dizini kaynak durdurulmadan reddedilir; dump hatasında
  önceden çalışan kaynak tekrar açılır. Linux root yalnızca belirtilen backup dizininin
  sahipliğini Neo4j UID'sine ayarlar.
- Test hedefi açıkça seçilmiş olsa bile `.env` ve live runtime kaydındaki canlı Bolt
  adresleri temizleme fixture'ına verilemez; durdurulmuş worker veri silme izni değildir.
- Tarayıcı testinde p95 kare süresi ≤ 50 ms taban bütçesi; ayrı benchmarkta üç koşulu
  karşılaştırmalı göç eşiği uygulanıyor. CI her ikisinin raporlarını saklar.

## Doğrulama

392 Python testi geçti; bilinen Windows eşzamanlı aynı gönderim testi bu yerel
geniş koşudan hariç tutuldu. Ek arşiv güvenliği/lifecycle hedefli koşusunda 26 test
geçti. 11 tarayıcı testi ve 5 Vitest testi geçti. Ruff/format ve 65 kaynakta mypy geçti.
Yeniden deneme kontrolünün hata görünümü tarayıcıda sentetik FAILED durumu/503 ile;
gerçek iş başarısızlığı ve yeniden denemenin veritabanı davranışı backend testleriyle sınandı.
Windows start/idempotent-start/HTTP smoke/stop kontrolü test portlarını serbest bıraktı.
Üç Shell betiğinin Linux bash sözdizimi kontrolü geçti. Arşiv kodunun Linux root
ve UID 10001 yolları ayrı container'larda, veritabanına dokunmayan hata simülasyonuyla
doğrulandı; sahiplik ve hata sonrası yeniden başlatma davranışları geçti. Canlı yeni Docker sürümünde
Qwen3.5-9B çıkarım, iki ilişki ve tam kaynak alıntısı 53,27 saniyede doğrulandı;
denemeye ait tek not silindi. Özgün 49 notun aktif/hedef revizyonları, metinleri ve
başlıkları yedekle birebir karşılaştırıldı. Yeni API/worker imajı 226,8 MiB; React UI
89,37 MiB. Eski API imajı CLI ile boyut sorgusuna açık kalmadığından önce/sonra
API boyutu farkı iddia edilmiyor. Eski React imajı etiketle korunuyor.
Yerel raporlar: `reports/cleanup-full.xml`, `reports/frontend-e2e/`,
`reports/ui-benchmark/results.json`, `backups/cleanup-c7c8f04/restore-verified.json`.

## Veri ve geri dönüş

### Silme sonrası arama düzeltmesi

Arama penceresi artık workspace graf/metadata sürümü değiştiğinde aynı sorguyu
yeniden çalıştırır. Sorgu veya sürüm değişirken eski sonuçlar hemen temizlenir ve
önceki istek iptal edilir. Böylece başka bir sekmede silinen not ve yalnızca ona
dayanan varlıklar açık aramada kalmaz; mevcut workspace yenileme aralığı en fazla
yaklaşık beş saniyedir. Aynı adlı iki ayrı aktif kayıt silinmiş kayıtla karıştırılmaz.
Yeni regresyon önce eski UI'de üç sonucun kaldığını doğrulayarak başarısız oldu;
düzeltmeden sonra geçti. İki tarayıcı kontrolü, memory/Neo4j üzerinde dört API
kontrolü ve beş Vitest testi geçti. Canlı UI de silinen kayıt için sıfır sonuçla doğrulandı.

### Silinenler görünümü

**Liste → Silinenler** düğmesi veya konu filtresindeki **Silinenler** seçeneği,
silinen kayıtları ayrı ve sayfalı listeler. **Düzenlenmemiş**, konusu atanmamış
aktif notlar için korunur; silinmiş olmakla aynı anlama gelmez. Silinen kayıtlar
normal katalog, arama, graf ve soru kaynaklarına dahil edilmez.

Yeni salt okunur API: `GET /api/v1/workspace/deleted-notes?limit=50&cursor=...`.
Yalnızca `note_id`, `title`, `deleted_at`, `content_purged` ve sayfalama bilgisi
döner; içerik veya eski kaynak metinleri açılmaz. En yeni silinenler önce gelir;
aynı zaman damgasında kimlik sıralaması ve cursor sınırları iki store'da eşittir.
Migration, silme davranışı ve saklama süresi değiştirilmedi. Mevcut içerik
temizliği sonrası adı silinen tombstone'lar **İçeriği temizlenmiş not** olarak görünür.
Geri yükleme veya kalıcı silme düğmesi bu kapsamda eklenmedi.

Memory/Neo4j katalog ve store sözleşmeleri dahil 80 test geçti. Mobil görünümde
silinenler listesi, normal listeye dönüş ve aramada bulunmama dahil 13 tarayıcı
testi ve 5 Vitest testi geçti. Canlı API'de ilgili iki kaydın yalnızca Silinenler'de
olduğu, arama ve Düzenlenmemiş sonuçlarına girmediği doğrulandı. Ruff ve mypy geçti.

`backups/cleanup-c7c8f04/` ve `reports/` yalnızca yerelde tutulur. Tam yedek,
okunabilir dışa aktarımın yerine geçmediği gibi dışa aktarım da tam yedek değildir.
Canlı Compose projesi ve volume adı değiştirilmez. Migration 001–005, mevcut
belgeler, model/embedding profili ve işlem geçmişi korunur. Başarısız eski işler
kendiliğinden yeniden denenmez. `.vscode` yerel ayarları kapsam dışındadır.

## NiceGUI kabul kapısı

1440×960 ve 360×800 görünüm; siyah zemin, ana/alt düğüm boyutu ve kaynak vurgusu;
not/konu/seri/varlık grafı, kamera, sürükleme, arama, kaynak ve yükleme akışları.
Aynı cihazda üç koşunun ortancası: p95 kare süresi ≤ max(16,7 ms, React × 1,25),
ilk kullanılabilir graf süresi ≤ React × 1,25 + 250 ms. Eşdeğerlik sağlanmazsa
temiz React tutulur; NiceGUI ikinci kalıcı arayüz haline getirilmez.
