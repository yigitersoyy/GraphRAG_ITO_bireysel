# Otomatik konu düğümleri ve listeden taşıma

8 Kasım 2026. Yeni notlarda varsayılan konu seçimi **Başlığa göre otomatik konu**.
Dosya adının ortak ön eki bir konu düğümü oluşturur veya mevcut düğümü kullanır:

- `01_kvkk_6698_kanun_bolum_01` ve `02_kvkk_veri_imha_yonetmeligi_bolum_01` → KVKK.
- `03_bddk_5411_bankacilik_kanunu_bolum_01` → BDDK.

Baştaki sıra numarası ve dosya uzantısı temizlenir. Mevcut konu adları büyük/küçük
harften bağımsız eşleşir; kullanıcının seçtiği ad/renk korunur. Örneğin mevcut `kvkk`
konusu yeniden `KVKK` adıyla çoğaltılmaz. Yapılandırılmış dosya adlarında ilk ön ek
kullanılır; sıradan, belirsiz başlıklardan model çağrısıyla konu uydurulmaz.
Bir konu bulunamazsa not Düzenlenmemiş kalır. Konu menüsünden belirli bir konu veya
Düzenlenmemiş seçilerek otomatik atama kapatılabilir.

## Liste üzerinden taşıma

**Liste** görünümünde not satırını tutup üstteki konu hedefine bırakın. Hedefler
filtre uygulanırken ve konunun içinde hiç not yokken de kullanılabilir.
Hedefe tıklamak konuyu filtreler. Satırdaki **Konu** seçimi aynı taşıma işlemini
klavye ve mobil üzerinden sağlar. Yeniden sayfa açıldığında atama korunur;
graf notu yeni konu kümesine yerleştirir. Konu oluşturmak/yeniden adlandırmak için
mevcut **Konuları düzenle** kullanılır. Konu içindeki satır sırasını değiştirme
eklenmedi; taşıma notun bağlı olduğu düğümü değiştirir.

Taşıma yalnızca not metadata'sını değiştirir. Metin, kaynak revizyonu, çıkarılmış
ilişkiler ve işleme işi değiştirilmez. Gösterilen metadata sürümüyle CAS uygulanır;
başka bir işlem atamayı değiştirdiyse üstüne yazılmaz, yenileme mesajı gösterilir.
Liste yenilenene kadar taşıma kontrolleri bekler; eski sürümle ikinci taşıma
başlatılmaz. İdempotent oluşturma tekrarı elle yapılan taşımayı geri almaz.

## Uygulama ve tasarım

Otomatik atama API'de hem JSON not oluşturma hem dosya yüklemede çalışır;
yalnızca ilk başarılı oluşturma akışındadır. `auto_topic=false` açık seçimi kapatır.
Mevcut oluşturulmuş notlar ve manuel seçimler her açılışta yeniden sınıflandırılmaz.
Konu adları mevcut workspace kapsamında tekilleşir; eşzamanlı oluşturma çakışmaları
var olan konuyu kullanarak ele alınır. Taşıma mevcut `/notes/{id}/metadata` ucunu
ve iki depodaki sürüm denetimini kullanır; yeni şema migration'ı gerekmez.

`frontend-design` rehberiyle mevcut görsel dil korundu: arka plan `#181818`, yazı
`#EEEEEC`, ikincil yazı `#A5A5A3`, sınır `#484848`, bırakma vurgusu `#459FE5`;
konu renkleri mevcut palettir. Yazı ailesi Segoe UI, düzen mevcut yoğun listedir.
Kart/kanban düzeni yerine listenin üstünde kompakt hedef şeridi ve satır içinde
seçim kullanıldı. Mobilde konu seçimi görünür, hedefler yatay kaydırılabilir.

## Doğrulama ve mevcut veriler

- Otomatik atama, mevcut konuya eşleşme, elle taşıma sonrası tekrar oluşturma,
  manuel seçenek ve dosya yükleme hem bellek hem Neo4j üzerinde doğrulandı.
- **7 gerçek API Playwright testi geçti**, 54,1 saniye. Yeni test gerçek sürükle-
  bırak, yenileme sonrası kalıcılık, mobil seçim ve çakışmada veri korunmasını
  kapsar. Çakışma hata görünümü için yalnızca ilgili PATCH yanıtı 409 ile benzetilir;
  başarılı taşıma gerçek API'ye gider.
- Üretim derlemesi ve 2 frontend birim testi, Ruff lint/format ve mypy (65 kaynak)
  başarılı. Canlı masaüstü/graf/liste ve 360 px mobil görünüm incelendi; taşma veya
  tarayıcı hatası yok. Canlı görsel kontrol kullanıcı notlarını taşımadı.
- Genel koşuda **391 test geçti**, 1 test başarısız oldu, 1 eski Neo4j eşzamanlılık
  testi bilinen Windows takılması nedeniyle baştan ayrıldı. Başarısız olan önceki
  başlatıcı çökme testi, Windows venv başlatıcısını sonlandırırken asıl Python alt
  sürecini bırakıyordu. Test gerçek yorumlayıcıyı kullanacak şekilde düzeltildi;
  ilgili **19 testin tamamı yeniden geçti**. Tek tam koşu bütünüyle başarılıymış
  gibi sunulmaz; uygulama kilidi veya konu kodu bu düzeltmede değiştirilmedi.
- Canlı ortamda mevcut **14 notun tamamı** konuya bağlandı: `kvkk` **4**, BDDK **10**.
  Kullanıcının önceden oluşturduğu `kvkk` adı/renk korundu. Önceki metadata
  yedeklendi; kaynak metne veya işlere yazılmadı. 14 notun desired revision ID'si
  birebir aynı kaldı. Konusu/sürümü elle değiştirilmiş notların üzerine yazılmaz.
- Canlı API ve UI güncellendi. Çalışan worker ve Neo4j yeniden başlatılmadı;
  kullanıcının devam eden belge işleri korunarak yalnızca metadata atandı.

Kanıtlar: `reports/tests-topic-transfer.xml`, `reports/tests-topic-lock-followup.xml`,
`reports/frontend-e2e/results.json`, `reports/topic-grouping-before.json`,
`reports/topic-grouping-live.json`, `reports/topic-grouping-verified.json`,
`reports/topic-ui-live.json` ve `reports/topic-live-graph.png` / `topic-live-list.png`.
