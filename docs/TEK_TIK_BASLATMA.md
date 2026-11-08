# Tek tık başlatma teslimi

> Dönemsel tasarım/teslim kaydıdır. Güncel mimari, testler ve kullanım durumu:
> [Temizlik ve Python UI kararı](TEMIZLIK_VE_PYTHON_GECISI.md). Eski durum sayıları
> ve model ölçümleri güncel veritabanının veya model kalitesinin garantisi değildir.

8 Kasım 2026. Windows'ta günlük kullanım için proje kökündeki **`BASLAT.cmd`**
dosyasına çift tıklayın. Docker, LM Studio arka ucu, iki yerel model ve proje
servisleri hazırlanır; hazır olunca tarayıcı açılır. **`DURDUR.cmd`** yalnızca
proje servislerini durdurur ve veri volume'larını korur. [Kullanım ayrıntıları](windows.md).

Başlatıcı program/model indirmez, diğer modelleri kapatmaz, mevcut kurulumla çalışır.
Soğuk Docker açılışı sırasında Linux motorunun hazır olması beklenir. Var olan
servisler kullanılır; durmuş proje aynı portlar ve veri volume'uyla devam eder.
İlk başlatma güncel ayarlarla migration ve model yetenek kontrolünü de çalıştırır.
Tarayıcı ancak API, worker heartbeat ve UI hazır olduğunda açılır.

Model seçimi dosya yolu/model anahtarının katalogda tam eşleşmesine dayanır.
Kurulu CLI yüklemede `modelKey` beklediği için tam dosyadan çözümlenen **tekil anahtar**
kullanılır; belirsiz anahtarın ilk eşleşmeyi seçmesine izin verilmez. Yüklü bir proje
kimliği başka dosyaya/bağlam uzunluğuna bağlıysa sessizce değiştirilmez, hata gösterilir.
GPU oranı 0,8, sohbet bağlamı 8192 ve paralellik 1; embedding CPU. Kişisel `.env`
ve model ağırlıkları değiştirilmedi.

Manager ve launcher kilitleri dosyanın varlığına dayanmak yerine işletim sistemi
kilidi kullanır. Süreç çökünce kilit çözülür; eski dosya sonraki başlatmayı engellemez.
İkinci eşzamanlı komut ilk başlatmayı çoğaltmaz. Diskteki `.lock` dosyaları silinmez.

## Doğrulama

- **36 ilgili test geçti**: model/endpoint seçimi, mevcut servisleri kullanma,
  kapalı Docker'ı başlatıp bekleme, Docker hazır olma zaman aşımı, tarayıcının hazır
  olmadan açılmaması, aynı anda başlatma kilidi, çökme sonrası kilit çözülmesi,
  kayıtlı durmuş projenin portlarıyla devam etmesi ve sağlayıcı bağlantıları.
- Ruff lint/format ve mypy (64 kaynak) başarılı.
- Gerçek yerel testte dört proje container'ı durduruldu, yalnızca proje kimlikli iki
  model bellekten çıkarıldı; `live.json` korundu. Başlatıcı modelleri yeniden yükleyip
  aynı veri volume'uyla API/worker/UI'ı **40,50 saniyede** hazır duruma getirdi.
- Gerçek **`BASLAT.cmd`** çağrısı tekrar çalıştırıldı: **3,27 saniye**, container
  kimlikleri aynı kaldı, tarayıcı açma yoluna ulaşıldı. Son API readiness ve worker
  heartbeat başarılı. Eski demo servisindeki altı not ve kalıcı not sayısı korundu.
- Docker motoru bu gerçek testte zaten açıktı; Docker Desktop tamamen kapalıyken
  açılma/bekleme yolu kontrollü testte doğrulandı. Bilgisayarın fiziksel yeniden
  başlatıldığı veya LM Studio GUI'sinin kapatıldığı iddia edilmez.

Kanıtlar: `reports/tests-launcher-final.xml`, `reports/one-click-live.json`,
`reports/one-click-live.log`, `reports/runtime/launcher.log`.
İlk kapalı-model denemesinde CLI dosya yolu kabul etmedi; bu hata saklandı, tekil
model anahtarı düzeltmesinden sonra yukarıdaki gerçek test başarıyla tekrarlandı.

Ek son kontroller: `scripts/verify_runtime.py` gerçek demo HTTP ekleme/kaynaklı
cevap/güncelleme/silme ve start-idempotency-stop akışını geçti; deneme portları
serbest bırakıldı. Gerçek `DURDUR.cmd` ve ardından yeniden başlatma da başarılı.
Son durumda kullanıcı çalışma alanında dört not bulunduğu için, eski "çalışma
alanı boş olmalı" kontrolü uygulanmadı; o eski yardımcı bu varsayımda durdu ve
veri silmedi. Son kontrol yalnızca readiness, worker ve not sayılarını okur.
Servisler açık bırakıldı. Kanıt: `reports/one-click-final-state.json`.

LM Studio arka uç başlatma mekanizması: [resmî daemon komutu](https://lmstudio.ai/docs/cli/daemon/daemon-up).
