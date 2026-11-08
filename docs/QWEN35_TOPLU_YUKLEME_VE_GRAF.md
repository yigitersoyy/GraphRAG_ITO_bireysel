# Qwen3.5, toplu yükleme ve yeni graf

8 Kasım 2026 teslimi. Canlı arayüz: http://localhost:28501. Açık sayfayı yenileyin.
Sonraki açılışlarda kökteki `BASLAT.cmd` dosyasını kullanın.

## Model

Çıkarım ve cevap üretimi yalnızca LM Studio'daki **`qwen/qwen3.5-9b`** modelini kullanır.
Eski sohbet modeli devreden çıkarıldı; başka sohbet modeline otomatik geçiş yoktur.
Nomic `graphrag-embed` yalnızca arama vektörleri için korunur; mevcut 768 boyutlu
indeks değişmez. Yeni sohbet modeli 8192 bağlamla yüklendi.

`.env` içindeki `EXTRACTION_MODEL`, `ANSWER_MODEL`, `LAUNCH_CHAT_MODEL` yeni modele
ayarlandı. `CHAT_TEMPLATE_ENABLE_THINKING=false`, boş `LLM_INSTRUCTION_SUFFIX` ve
istekte `reasoning_effort=none` kullanılıyor. Düşünme ayarı işlem ve yetenek
parmak izlerine dahildir. Eski bekleyen işler farklı model profiliyle sessizce yürütülmez.
Mevcut belgeler topluca yeniden indekslenmedi.

## Birden fazla dosya

**Yeni not → dosya yükle** seçiminde Ctrl/Shift ile aynı anda en fazla **50 dosya**
seçilebilir. PDF, DOCX, XLSX, XLS, TXT ve MD karışık seçilebilir.
Her dosya ayrı not olur ve sırayla gönderilir. Bir dosyanın hatası diğerlerini durdurmaz.
Başarılı dosyalar tekrar denemede yeniden yüklenmez. Durdurma, o anki dosyadan sonra işler.

Tek dosyada mevcut düzenlenebilir metin önizlemesi devam eder. Toplu seçimde dosya
adına tıklayarak salt okunur önizleme açılır; ardından yükleme başlatılır.
Ortak konu seçilebilir veya dosya adına göre otomatik gruplama kullanılabilir.
“İşleme alındı” dosyanın kaydedilip kuyruğa girdiği anlamındadır; modelin belgeyi
tamamladığı anlamına gelmez. Son durum listeden izlenir.
Dosya başına boyut, metin, sayfa ve biçim sınırları [belge yükleme](BELGE_YUKLEME.md)
dokümanında geçerliliğini korur; OCR eklenmedi.

## Graf

Son görünüm güncellemesi: kullanıcının son isteğiyle zemin **siyah `#000000`**;
graf üzerindeki yardımcı metinler ve bağlantı etiketleri açık renktir. Konu düğümleri yaklaşık
108–140, belge serileri 94–124, belge düğümleri 52 birimdir. Varlıkların boyutu
bağlantı sayısıyla artar; ana düğümler bağlı belgelerden belirgin biçimde büyüktür.

Soruya cevap geldiğinde not haritası korunur. Cevabın kaynak belgeleri, ilgili
varlıkları ve bu belgelerin konu/seri düğümleri renkli; diğer düğüm ve bağlantılar
sönük gösterilir. Aynı konudaki ilgisiz belgeler vurgulanmaz. **Vurguyu temizle**
tüm haritayı normal görünümüne döndürür. Haritada eşleşen kaynak yoksa tümünü
soldurmak yerine açıklama gösterilir. **Destekleyici ilişkileri göster** ayrı
ayrıntı görünümünü açmaya devam eder. Bu vurgulama, cevabın kaynaklarına dayanır;
ek model çağrısı gerektirmez.

Bu güncellemede üretim derlemesi, **5 Vitest** ve **9 tarayıcı testi (39,0 sn)**
geçti. Tarayıcıda soru sonrası kaynak vurgusu, ilgisiz düğümlerin sönmesi,
vurguyu temizleme ve gri zemin doğrulandı. Canlı belgeler değiştirilmeden UI güncellendi.
Örnek soru ekranı: `reports/frontend-e2e/05-answer.png`.

- Siyah zemin; mavi belge, kırmızı konu, gri varlık ve belge serisi düğümleri.
- Daire içinde metin, ok yönleri ve ilişki etiketleri; yakınlaştırma, taşıma ve odaklama.
- `01_kvkk_6698_kanun_bolum_01` gibi dosyalar, aynı konudaki diğer bölümlerle
  ortak gri seri düğümüne `BÖLÜMÜ` bağıyla bağlanır. Bu bağ dosya adı bilgisidir.
- Modelin yayımlanmış ve kaynaklı varlık ilişkileri ayrıca gösterilir. İlişkiye
  tıklama kaynak belgeyi açar. İşlenememiş notlardan hukuki ilişkiler üretilmez.
- Liste üzerinden sürükleyerek veya konu seçimiyle taşıma korunur.

Harita sınırları: en fazla 300 belge, 100 kaynak varlığı ve 150 çıkarılmış ilişki.
Kısmi görünüm arayüzde belirtilir. İlk model geçişi sırasında bulunan 14 belge,
iki konu ve iki belge serisiyle gösterildi; o örnekte yayımlanmış çıkarım ilişkisi
bulunmuyordu. Daha sonra eklenen belgelerle sayı ve ilişkiler değişebilir.

## Doğrulama ve sınırlar

- Üretim derlemesi, 2 Vitest testi ve **9 tarayıcı testi (40,1 sn)** geçti.
  Başarılı toplu yükleme, karışık hata/yeniden deneme, seri düğümü, konu taşıma,
  mobil görünüm ve 300 belge/600 bağlantı etkileşimi sınandı.
- Python geniş koşusunda 394 test geçti; bir alt süreç testinin yeni düşünme
  ayarıyla uyumsuz fikstürü düzeltildi. Bu test ve ilgili hedefli kontrollerin
  sonraki koşusunda **21/21** geçti. Bilinen Windows Neo4j bağlantı havuzu takılması
  nedeniyle eşzamanlı aynı gönderim testi bu geniş koşudan hariç tutuldu.
- Gerçek Qwen3.5 yetenek kontrolünde 5/5 kontrol geçti. Ayrı ve sonrasında silinen
  deneme notunda gerçek çıkarım, iki ilişki üzerinden cevap ve tam kaynak alıntısı
  doğrulandı (38,12 sn). Mevcut notların revizyonları korundu.
- Önceki modelle alınan geniş kalite ölçümleri bu modelin genel doğruluğunun
  sertifikası değildir. Mevcut 9 eski başarısız BDDK işi otomatik yeniden denenmedi;
  yeni modelle yeniden deneme gerekir. Yeni yüklenen her belgenin durumunu izleyin.

Kanıtlar: `reports/tests-qwen35-full.xml`, `reports/tests-qwen35-followup.xml`,
`reports/qwen35-probe.log`, `reports/qwen35-live-check.json`,
`reports/qwen35-reference-graph.png`, `reports/qwen35-bulk-mobile.png`.
