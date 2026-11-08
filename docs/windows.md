# Windows kurulumu ve çalışma modları

Ana arayüz, onaylanan koyu graf tasarımını kullanan React çalışma alanıdır. Graf, sağ not paneli, liste/konular, Ctrl+K araması ve kaynaklı cevaplar aynı ekranda bulunur. Eski Streamlit kaynakları alternatif olarak korunur.

## Günlük kullanım — tek tık

Bu makinede kurulum tamamlandı. Proje klasöründeki **`BASLAT.cmd`** dosyasına çift
tıklayın. Docker Linux motoru gerekirse açılır ve hazır olması beklenir. LM Studio
arka uç servisi, projeye ait sohbet/embedding modelleri ve 1234 yerel sunucusu
hazırlanır. Neo4j, migration, gerektiğinde model bağlantı kontrolü, API, worker ve
arayüz hazır olduktan sonra **http://127.0.0.1:28501** tarayıcıda açılır.

Modelleri ve Docker'ı elle açmanız, terminal komutu yazmanız veya her seferinde
kurulum/derleme yapmanız gerekmez. Zaten açık servisler kullanılır. Yeniden başlatma
sonrasında kayıtlı ama durmuş proje container'ları mevcut veri volume'uyla açılır.
Model yükleme ve Docker'ın açılması zaman alabilir; başlatma penceresi bitene kadar
bekleyin. Aynı anda ikinci başlatma ilkini çoğaltmaz. Hata varsa pencere açık kalır;
ayrıntılar `reports/runtime/launcher.log` içindedir.

İşiniz bitince belge işlerinin tamamlanmasını bekleyip **`DURDUR.cmd`** dosyasına çift
tıklayın. Yalnızca bu projenin servisleri durur; notlar/volume'lar korunur. Docker ve
LM Studio başka uygulamalar da kullanabileceği için açık bırakılır. Çalışırken
bilgisayarın ve arka plan servislerinin çalışır durumda kalması gerekir.

Başlatıcı mevcut Windows kurulumuna yöneliktir; program/model/imaj indirmez veya
yeniden kurmaz. İlk kurulum aşağıdadır. Varsayılan model Qwen3.5 9B Q4_K_M (`qwen/qwen3.5-9b`) ve
Nomic v1.5 Q4_K_M'dir; sohbet bağlamı `.env` içindeki 8192 ayarıyla yüklenir, GPU
oranı 0,8, embedding CPU'dadır. Model değiştirilirse `.env` içine `LAUNCH_CHAT_MODEL`
ve `LAUNCH_EMBED_MODEL` ile `lms ls --json` içindeki tam dosya yolu/model anahtarı
verilebilir; `LAUNCH_CHAT_GPU` ile GPU oranı seçilebilir. Belirsiz model anahtarı,
yanlış yüklü kimlik/bağlam veya farklı LM Studio portu açık hata üretir; başka
modeller kendiliğinden kapatılmaz. Başlatıcı bu bilgisayardaki HTTP LM Studio
uçlarını kullanır; uzak/ayrı sunucu kurulumlarında aşağıdaki elle başlatma geçerlidir.

LM Studio arka uç başlatma mekanizması: [resmî daemon komutu](https://lmstudio.ai/docs/cli/daemon/daemon-up).

## Ön koşullar

- Python 3.12 ve Windows Python launcher (`py -3.12 --version`).
- Yerel arayüz kurulumu için Node.js 24 ve npm (`node --version`, `npm.cmd --version`). Docker frontend derlemesi kendi Node aşamasını kullanır.
- Kalıcı modlar için Linux container'ları çalıştıran Docker Desktop.
- Gerçek kullanım için ana makinede LM Studio, yüklenmiş sohbet ve embedding modelleri.
- İlk kurulum ve wheel indirme sırasında ağ erişimi.

Repo kökünde PowerShell açın:

```powershell
.\scripts\setup.ps1
```

Betik PATH üzerindeki `uv` aracını kullanır; yoksa projeye ait `.tools` ortamına sabit sürümünü kurar. Uygulama Python 3.12 ile `.venv` içine `uv.lock` üzerinden kurulur. `.env` yoksa örnekten oluşturulur, varsa korunur. `.env` dosyasını git'e eklemeyin.

Arayüz bağımlılıkları `frontend/package-lock.json` ile `npm ci` üzerinden kurulur ve derlenir. Backend-only kurulumda `setup.ps1 -SkipFrontend` kullanılabilir. Yerel demo başlatıcısı arayüz paketini derler; aynı modu tekrar başlatmak ikinci servis oluşturmaz.

Yürütme ilkesi `.ps1` dosyasını engelliyorsa sistem genelini değiştirmek yerine bu çağrı için `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1` kullanılabilir.

## Bellek demosu

```powershell
.\scripts\start.ps1 -Mode demo
.\.venv\Scripts\python.exe scripts/doctor.py --mode demo
.\scripts\stop.ps1 -Mode demo
```

UI: `http://localhost:8501`; API: `http://localhost:8000`. Bu modda model ve Docker gerekmez. Notlar süreç kapatılınca kaybolur. İkinci `start` aynı servisleri kullanır. Port başka bir sürece aitse betik o süreci kapatmaz.

Portlar doluysa:

```powershell
.\scripts\start.ps1 -Mode demo -ApiPort 18001 -UiPort 18502
```

## Kalıcı demo

Önce `.env` içindeki `NEO4J_PASSWORD` değerini belirleyin ve Docker Desktop'ı başlatın:

```powershell
.\scripts\start.ps1 -Mode persistent-demo -Build
.\scripts\stop.ps1 -Mode persistent-demo
```

`-Build`, kilitli Linux/Python 3.12 wheel'lerini ana makinede hazırlar ve servis imajlarını oluşturur. API/worker imajı UI bağımlılıklarını kurmaz. UI ayrı Node build aşamasından sonra Nginx ile çalışır; ilk `npm ci` için ağ erişimi gerekir. Çalışırken tarayıcı CDN'e bağlanmaz. Kaynak veya bağımlılık değişikliğinde ilgili modu durdurup yeniden `-Build` kullanın.

Compose projesi `notes-graphrag-persistent-demo`, veri volume'u bu proje adına bağlıdır. Gerçek kullanım `notes-graphrag-live` projesiyle ayrı volume kullanır. `stop` volume silmez. İlk örnekteki bellek demosu ile aynı portlar kullanılır; ikisini birlikte çalıştırmak için farklı portlar verin:

```powershell
.\scripts\start.ps1 -Mode persistent-demo -ApiPort 18000 -UiPort 18501 -BoltPort 17687 -Neo4jHttpPort 17474 -Build
.\.venv\Scripts\python.exe scripts/doctor.py --mode persistent-demo --api-base http://127.0.0.1:18000 --ui-port 18501 --neo4j-uri bolt://127.0.0.1:17687
```

## Gerçek LM Studio kullanımı

Kullanıcının isteğiyle çıkarım ve cevap modeli Qwen3.5 9B'ye geçirildi. Önceki Qwen3 8B yüklemesi kapatıldı; uygulamada eski modele geri dönüş yok. Yerel sunucu ve modeller için:

```powershell
lms load qwen/qwen3.5-9b --identifier qwen/qwen3.5-9b --context-length 8192 --gpu 0.8 --parallel 1 -y
lms load text-embedding-nomic-embed-text-v1.5 --identifier graphrag-embed --gpu off -y
lms server start --port 1234 --bind 127.0.0.1
```

Bu komutlar model indirmez. Başka model seçerseniz kimlik, boyut, bağlam ve ön işleme ayarlarını onunla eşleştirin. `.env` örneği:

```dotenv
EXTRACTION_MODEL=qwen/qwen3.5-9b
ANSWER_MODEL=qwen/qwen3.5-9b
CHAT_TEMPERATURE=0.2
LLM_INSTRUCTION_SUFFIX=""
CHAT_TEMPLATE_ENABLE_THINKING=false
EMBEDDING_MODEL=graphrag-embed
EMBEDDING_DIMENSIONS=768
EMBEDDING_PROFILE=nomic-embed-text-v1.5-q4km-768-v1
EMBEDDING_QUERY_TEMPLATE="search_query: {question}"
EMBEDDING_DOCUMENT_PREFIX="search_document: "
LM_STUDIO_CONTEXT_TOKENS=8192
```

Nomic için sorgu ve belge önekleri [modelin kendi belgesinde](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) açıklanır. Türkçe kalite ayrıca ölçülmelidir; çalışan bağlantı kaliteli cevap garantisi değildir.

Qwen3.5 için eski `/no_think` son eki kaldırıldı. `CHAT_TEMPLATE_ENABLE_THINKING=false` ile JSON/text çağrılarında `chat_template_kwargs.enable_thinking=false` ve LM Studio'da doğrulanan `reasoning_effort=none` gönderilir. Düşünme ayarı probe ve pipeline parmak izine dahildir. [Qwen3.5 model kartı](https://huggingface.co/Qwen/Qwen3.5-9B).

Model çıkarım şeması yalnızca kaynak alıntısını ister; kaynakta tek bir yerde bulunan alıntının konumunu ve şema sürümünü sunucu belirler. Uydurma veya konumu belirsiz alıntı kabul edilmez. Desteklenmeyen ilişki türü ve bilinmeyen varlık referansı yine hata üretir.

Yerel Python `LLM_BASE_URL` / `EMBEDDING_BASE_URL` adreslerini, container'lar `COMPOSE_LLM_BASE_URL` / `COMPOSE_EMBEDDING_BASE_URL` adreslerini kullanır. Böylece `.env` içindeki yerel `127.0.0.1` ayarı container'ın kendi içine yönlenmez. Ayrı embedding sunucusu ve `EMBEDDING_API_KEY` desteklenir.

```powershell
.\scripts\start.ps1 -Mode live -Build
```

Başlatma sırası: Neo4j → migration → container içinden kaydedilmiş model probe'u → API/worker/UI → readiness ve worker heartbeat kontrolü. Probe başarısızsa gerçek mod demo modele dönmez. API'nin liveness kontrolüyle readiness kontrolü farklıdır. Mevcut probe kaydı varsayılan olarak 24 saat geçerlidir; yenilemek için aynı Compose projesi ve ayarlarıyla `docker compose -p notes-graphrag-live run --rm api probe --record` çalıştırın.

Arayüz gerekmiyorsa `-NoUi` ekleyin. Özel port kullanıyorsanız teşhiste `--api-base` ve `--neo4j-uri` verin. Doğrudan Compose çağrılarında aynı port değişkenlerini de koruyun.

## Kontroller

Frontend geliştirme ve test:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run build
npm.cmd test
```

`npm.cmd run dev` API için varsayılan `http://127.0.0.1:8000` adresine proxy yapar; başka hedef için aynı terminalde `WORKSPACE_API_URL` ayarlayın. Kalıcı tarayıcı testleri yalnızca boş `memory-demo` üzerinde çalışır. `start.ps1 -Mode demo -ApiPort 18001 -UiPort 18502` sonrasında `frontend/` içinde `npm.cmd run test:e2e` kullanılır. Testler gerçek model/kişisel veri hedefini reddeder; sentetik notları temizler.

```powershell
.\.venv\Scripts\python.exe scripts/verify_runtime.py
.\.venv\Scripts\python.exe scripts/smoke.py --api-base http://127.0.0.1:8000 --language en
.\.venv\Scripts\python.exe scripts/smoke.py --api-base http://127.0.0.1:8000 --language tr
```

`verify_runtime.py` mevcut yönetilen bellek demosu varsa çalışmayı reddeder. Varsayılan deneme portları 18001/18502'dir. Türkçe smoke gerçek modeller içindir; kurallı demo çıkarıcısının Türkçe model kalitesini temsil ettiği varsayılmaz.

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe
.\.venv\Scripts\python.exe -m pytest -q --basetemp reports/pytest-local
```

Veritabanı testleri ayrı, silinebilir hedef gerektirir. `NEO4J_TEST_URI`, `NEO4J_TEST_PASSWORD` ve `NEO4J_TEST_WIPE=1` yalnızca bu test hedefi için ayarlanır. Testler hedef veriyi temizler ve taze worker heartbeat'i gördüklerinde durur. `--basetemp` için yalnızca testlere ayrılmış bir dizin kullanın; pytest bu dizini temizleyebilir.

## Teşhis ve kurtarma

- `scripts/doctor.py` salt okunurdur; migration, inference, servis durdurma veya veri silme yapmaz. Parola ve token yazdırmaz.
- Çalışma kayıtları ve sahiplik dosyaları `reports/runtime/` altındadır. Durdurma, yalnızca bu yöneticinin başlattığı süreçleri/Compose projesini yönetir.
- Başlatma yarıda kaldıysa `BASLAT.cmd` yeniden denenebilir. Manager/launcher kilitleri işletim sistemi kilididir; süreç kapanınca kilit otomatik çözülür. Diskte `.lock` dosyasının kalması çalışan kilit olduğu anlamına gelmez; elle silmeyin. Aynı anda iki yönetim işlemi başlatmayın.
- Mevcut bellek demosunu kapatmadan önce notları dışa aktarın: `.venv\Scripts\python.exe scripts/export_notes.py --out reports/backups/my-notes.json`. Araç aktif/bekleyen revizyonları alır; tam tarihçe yedeği değildir. Aynı dosyayı ezmez.
- Not yedekleri ve değerlendirme raporları veri içerebilir; `reports/` ve `backups/` git dışında tutulur.

Kalıcı veri için platformdan bağımsız yedekleme:

```powershell
.\.venv\Scripts\python.exe scripts/neo4j_archive.py backup --container notes-graphrag-persistent-demo-neo4j-1 --directory backups/2026-11-07
```

Yedekleme kaynak container'ı kısa süre durdurur ve daha önce çalışıyorsa yeniden açar. Kullanılmayan yeni bir yedek dizini seçin. Linux'ta bind mount hedefinin container kullanıcısı tarafından yazılabilir olması gerekir.

Geri yükleme yalnızca yeni oluşturulmuş, **boş ve durmuş** hedef container'ın volume'una yapılır:

```powershell
.\.venv\Scripts\python.exe scripts/neo4j_archive.py restore --container my-empty-restore-container --directory backups/2026-11-07
docker start my-empty-restore-container
```

Başlatılmış ve veritabanı dosyaları oluşmuş bir hedef reddedilir. Araç mevcut veri üzerine yazmaz ve restore hedefini otomatik açmaz. Kaynağın volume'unu hedefe bağlamayın.

Tüm varsayılan yayın portları loopback üzerindedir. Ağdan kullanım ve kimlik doğrulama ayrı G aşamasıdır.

Uzun model çağrılarında worker iş lease'ini ve workspace heartbeat'ini yeniler.
Yenileme sahiplik tokenını denetler; süresi dolmuş veya başka worker'a geçmiş işi canlandırmaz.
Başlangıçtaki batch probe eski inference lease'inin dolmasını bekleyebilir; etkileşimli
isteklerin kısa bekleme bütçesi ayrı tutulur.
