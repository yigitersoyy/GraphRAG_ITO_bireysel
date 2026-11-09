# PDF, Word ve Excel yükleme

**Toplu seçim:** Dosya penceresinde Ctrl/Shift ile en fazla 50 dosya seçebilirsiniz;
desteklenen biçimleri karıştırabilirsiniz. Dosyalar sırayla ayrı notlara alınır.
Başarısız dosya diğerlerini durdurmaz; tekrar deneme başarılı dosyaları çoğaltmaz.
Toplu seçimde dosya adına tıklayarak salt okunur önizleme açılır, ardından
**Dosyaları yükle** ile başlanır. Tek dosyada aşağıdaki düzenlenebilir önizleme
devam eder. “İşleme alındı” model işleminin bittiği anlamına gelmez; son durumu
listeden izleyin. Durdurma o anki dosyadan sonra işler. Ortak konu seçebilir veya
[başlığa göre otomatik gruplamayı](KONU_GRUPLAMA_VE_TASIMA.md) kullanabilirsiniz.

**Yeni not → PDF, Word, Excel veya metin dosyası yükle** ile dosya seçin.
Metin kaydetmeden önce editörde görünür. Metni kontrol edin, isterseniz düzenleyin ve
**Kaydet** düğmesine basın. Önizleme not veya model işi oluşturmaz. Kaydettikten sonra
mevcut işleme durumu, arama, graf ve kaynaklı soru-cevap akışı kullanılır.

| Biçim | Sınır ve davranış |
| --- | --- |
| `.pdf` | Metin katmanı olan PDF, en fazla 10 MiB / 200 sayfa. Sayfa sınırları metinde `[Sayfa N]` olarak gösterilir. |
| `.docx` | Word ana gövdesindeki paragraflar, bağlantı metinleri ve tablo hücreleri, belge sırasıyla düz metne çevrilir. En fazla 10 MiB. |
| `.txt`, `.md` | UTF-8, en fazla 1 MiB. |
| `.xlsx`, `.xls` | Excel sayfaları ve dolu hücreleri, sayfa adı ve hücre adresleriyle alınır. En fazla 10 MiB; aşağıdaki Excel sınırları geçerlidir. |

Çıkarılan metin en fazla **100.000 karakter / 1 MiB** olabilir. Uzun belgeleri bölerek
yükleyin. PDF, Word ve Excel dosyaları yerelde okunur; dosyanın kendisi saklanmaz. Elde edilen
metin, diğer notlar gibi kalıcı bir revizyona kaydedilir ve yerel modele işlenir.
Alıntıların karakter aralıkları bu metne aittir; özgün PDF/Word sayfasının görsel
koordinatlarını veya biçimlendirmesini temsil etmez. Metni düzenlerseniz kaydedilen
kaynak düzenlediğiniz metindir.

Taranmış PDF/görseller için otomatik OCR eklenmedi. Metinsiz veya yalnızca görsel içeren
sayfa tespit edilirse sessizce boş not kaydetmek yerine OCR uyarısı verilir. Metin ve
görselin aynı sayfada bulunması, görseldeki yazının da okunduğu anlamına gelmez.
Çok sütunlu PDF ve karmaşık tabloların okuma sırasını önizlemede kontrol edin.
Word üstbilgi/altbilgi, yorum, dipnot, gömülü dosya ve görsellerinin içeriği alınmaz;
esas içerik bunlardaysa ana gövdeye taşıyın veya metin olarak dışa aktarın.
Şifreli belgeleri şifresiz kopya olarak kaydedin. Eski `.doc` ve makrolu dosyaları
Word'de makrosuz `.docx` olarak kaydedin.

## Excel davranışı

Excel içe alma `.xlsx` ve eski `.xls` biçimlerini destekler. Her dolu hücre
`"Sayfa adı"!A1 = değer` biçiminde kaynağa eklenir. Birden fazla sayfa, Türkçe metin,
tarih/saat, boole ve sayılar korunur. Yüzde/para birimi gibi hücre biçimleri ayrıca
belirtilir; sayının kendisi keyfî biçimde yuvarlanmaz. Birleşik hücrelerin değerleri
yalnızca kaydedildikleri ana hücrede görünür; tablo görünümü yeniden çizilmez.

**Gizli sayfa ve satırlar da dahildir.** Kaydetmeden önce önizlemeyi kontrol edin;
istemediğiniz verileri bu metinden silebilir veya ayrı bir Excel kopyası hazırlayabilirsiniz.
Formüller, makrolar ve dış bağlantılar çalıştırılmaz. XLSX'te formül ifadesi ile
dosyadaki son kayıtlı sonuç ayrı gösterilir; sonuç yoksa açıkça hesaplanmadığı yazılır.
XLS'te hücrelerin kayıtlı değerleri alınır, formül ifadeleri alınmaz. Kayıtlı sonuçlar
eski olabilir: güncel sonuç gerekiyorsa Excel'de yeniden hesaplayıp kaydedin.
Grafik, görsel, yorum, pivot mantığı ve biçimlendirilmiş sayfa görünümü alınmaz.
`.xlsm`, `.xlsb` ve `.ods` yerine makrosuz `.xlsx` kopyası yükleyin.

Sınırlar: dosya 10 MiB; en fazla 50 sayfa; sayfa başına 10.000 satır / 256 sütun;
20.000 dolu hücre. Genel 100.000 karakter / 1 MiB metin sınırı da geçerlidir.
XLSX açılmış arşivi en fazla 20 MiB / 2.000 kayıttır. Sınır aşılırsa dosya sessizce
kesilmez, yükleme reddedilir. Daha az sayfa/satır içeren dosyalar oluşturun.

Parser'lar `openpyxl` ve `xlrd`'dir; önceki PDF/Word ile aynı ayrı süreç, zaman aşımı
ve Linux bellek sınırlarını kullanırlar. Formül önbelleği davranışı için
[openpyxl API](https://openpyxl.readthedocs.io/en/3.1/api/openpyxl.reader.excel.html),
eski Excel değer/tarih türleri için [xlrd API](https://xlrd.readthedocs.io/en/stable/api.html).

## Ortak dönüştürme akışı

İçe alma mevcut `/api/v1/notes/upload` ucundadır. Salt okunur
`POST /api/v1/notes/upload/preview` aynı dönüştürücüyle `{text}` döndürür.
Önizleme ile yükleme aynı sınırları kullanır; MIME başlığına güvenilmez. PDF için
`pypdf`, Word ZIP/XML için `zipfile` ve `defusedxml` kullanılır. Dosyadan yol çıkarılmaz,
makrolar çalıştırılmaz, dış XML varlıkları çözümlenmez. Bozuk/şifreli dosyalar, aşırı
açılmış arşiv boyutu ve uzun metinler not oluşturulmadan reddedilir.

İkili dönüştürme 20 saniye zaman aşımı olan ayrı süreçte çalışır; aynı API sürecinde
en fazla iki parser çalışır. Linux parser süreçlerinde ayrıca 512 MiB adres alanı sınırı
vardır. Windows'ta boyut/sayfa/arşiv/zaman sınırları uygulanır. Word açılmış arşivi
20 MiB / 2.000 kayıtla sınırlıdır. API'nin normal JSON istek sınırı 2 MiB kalır;
yükleme uçlarında dosya ve multipart payı için 12 MiB istek sınırı vardır.

Metin çıkarma sınırlamaları: [pypdf belgeleri](https://pypdf.readthedocs.io/en/latest/user/extract-text.html).
Word ana gövde yapısı: [Microsoft WordprocessingML](https://learn.microsoft.com/en-us/office/open-xml/word/how-to-open-and-add-text-to-a-word-processing-document).
