# Otomatik konu düğümleri ve listeden taşıma

Yeni notlarda varsayılan konu seçimi **Başlığa göre otomatik konu**.
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

## API ve sürüm denetimi

Otomatik atama API'de hem JSON not oluşturma hem dosya yüklemede çalışır;
yalnızca ilk başarılı oluşturma akışındadır. `auto_topic=false` otomatik atamayı kapatır.
Mevcut oluşturulmuş notlar ve manuel seçimler her açılışta yeniden sınıflandırılmaz.
Konu adları mevcut workspace kapsamında tekilleşir; eşzamanlı oluşturma çakışmaları
var olan konuyu kullanarak ele alınır. Taşıma mevcut `/api/v1/notes/{id}/metadata` ucunu
ve iki depodaki sürüm denetimini kullanır; yeni şema migration'ı gerekmez.
