# Model kalitesi devamı — 8 Kasım 2026

> Dönemsel tasarım/teslim kaydıdır. Güncel mimari, testler ve kullanım durumu:
> [Temizlik ve Python UI kararı](TEMIZLIK_VE_PYTHON_GECISI.md). Eski durum sayıları
> ve model ölçümleri güncel veritabanının veya model kalitesinin garantisi değildir.

> Bu belge tarihsel geliştirme günlüğüdür; ara başarısızlıklar korunmuştur. Son durum ve tamamlanan kabul: [teslim raporu](TESLIM_RAPORU.md). Aşağıdaki açık iş ve sert model-ret açıklamaları ilgili ara sürümü anlatır.

Bu çalışma, [önceki kalite raporundaki](KALITE_IYILESTIRME_RAPORU.md) açık D13/D14/D16 maddelerini sürdürür. Arayüz tasarımı değiştirilmedi. Sonuçlar bu belgenin doğrulama bölümüne kaydedilir; geliştirme denemeleri genel kalite onayı değildir.

## Değişiklik

Çıkarım modeli artık önce kaynak alıntısı ve ilişkiyi, ardından o ilişkinin türlenmiş özne/nesnesini üretir. Böylece modelin bütün varlıkları baştan yanlış sınıflandırıp sonraki ilişkileri bu seçime uydurması azaltılır. Wire biçimi `relations` dizisidir; sunucu bunu mevcut iç `entities`/`claims` biçimine dönüştürür. Kalıcı şema ve migration 5 değişmez. Pipeline sürümü `extract_v5_relation_first` oldu.

Dönüşümde aynı yerel kimliğin farklı ad/türlerle kullanılması reddedilir. Farklı yerel kimlikler sırf adları eşit diye bu dönüşümde birleştirilmez. Alıntı benzersiz kaynak alt dizgesi olmalıdır; karakter aralıklarını sunucu hesaplar. İç şema, ilişki türleri ve değişmez revizyon ofsetleri tekrar doğrulanır. Hatalı ilişki sessizce atılmaz. Demo/test sağlayıcılarının mevcut iç biçimi kabul edilmeye devam eder.

Bir Project varlığının adı kaynakta yalnızca `Project …` veya `Proje …` önekiyle geçiyorsa modelin bu öneki atması doğrulama hatasıdır. Sunucu adı değiştirmez; modelden tam kaynak adını yeniden üretmesi istenir. Kaynakta ayrıca öneksiz bir kullanım varsa farklı varlık olasılığı nedeniyle bu kural birleştirme tahmini yapmaz. Bu sınırlı kural bütün Türkçe ekleri çözümleyen bir morfoloji sistemi değildir.

Gerçek model akışında önce cevap adayı üretilir. Kaynak zinciri denetiminden sonra ayrı bir çağrı, yalnızca atıf yapılan özgün pasajlarla adayın sorulan özellik/özneye ve kaynağa uyumunu inceler. Sorunun açıkça istediği bilgi türü ve adayın gerçekten verdiği tür ayrı alanlardır. Örneğin programlama dili isteğine veritabanı verilmesi, model `supported=true` dese bile sunucu tarafından reddedilir. Evet/hayır, kesinlik ve açıklama soruları için `OTHER` kullanılır; özel addan istenen tür tahmin edilmez. Bu sınırlı sınıflama her anlamsal hatayı çözen bir ontoloji değildir.

Modelin soru türünü de yanlış etiketleyebildiği görüldü. Açık İngilizce “which/what programming language(s)” ve Türkçe “hangi programlama dili…” isteklerinde tür artık soru metninden sabitlenir; model bunu DATABASE/OTHER olarak yeniden adlandıramaz. Bu dar, iki dilli niyet kuralı bir cevap sözlüğü değildir: kişi/proje/teknoloji adına göre cevap üretmez, gerçek programlama dili kanıtını engellemez. Diğer ifade ve kategoriler model destekli kalır; genel anlamsal hata riski sürer.

Model çekimserlik önerirse bunun yerine yalnızca özgün pasajlar ve soruyla cevaplanabilirlik değerlendirilir; bu çağrı aday cevabı ve çıkarılmış graf ipuçlarını görmez. Mevcut yanıtlanabilir bilgi olduğu söylenirse bir yeniden üretim istenir. Açık dil isteğinde aday türü uyuşmazsa da aynı bağımsız yokluk teyidi yapılır: bilgi yoksa çekimserlik, bilgi varsa onarım hakkı korunur. Bu kontrol destekli cevapları önceden engelleyen genel bir kapı değildir. Onaylanmış planın güncel kişisel kullanım sayılması veya başka bir özelliğin cevap olarak verilmesi reddedilebilir. İnceleme cevaba atıf eklemez. En fazla iki aday üretimi vardır; her adayda bir denetim, açık tür uyuşmazlığında ek bir yokluk teyidi olabilir (en fazla dört denetim). İkinci aday da reddedilirse `GENERATION_INVALID` döner. Denetim/sunucu hatasında demo cevaba geçilmez.

İnceleme aynı modelle yapılır; bağımsız doğruluk garantisi değildir. Kanıt ve atıf denetiminin yerini almaz. Her çağrı ortak inference kilidini ve soru süresini kullanır. İnceleme sırasında veri yayımlanırsa çekimserlik dahil eski sonuç atılır. Demo modunda bu denetim kapalıdır; gerçek API ve canlı değerlendirmede açıktır. Tanı alanları inceleme türünü, çağrı ve aday sayısını gösterir. Ek çağrıların gecikme maliyeti ölçülür.

## Değerlendirme düzeni

Mevcut yerel Qwen3 8B Q4_K_M / Nomic v1.5 768 boyut profili korunur; yeni model indirilmez. Kullanıcı notları ölçüme alınmaz. Her canlı ölçüm ayrı, boş Neo4j volume'unda yapılır; normal gerçek model API/worker bu sırada durdurulur. Özgün bellek demosu korunur.

Başlangıç kümesi geliştirme içindir. Önceki `validation` ve `holdout` kümeleri artık incelendiğinden regresyon verisidir. `holdout2` için yazılan bir olumlu dil örneği geliştirme probunda kullanıldığı için bu küme son bağımsız kontrol sayılmadı. Yeni `holdout3` 8 not/12 soru içerir: olumlu dil kullanımı, ilgisiz özellik, iki kaynaklı onaylanmış plan, olasılık, Türkçe şube/ekli proje metni, aynı dönem için birbirini dışlayan veritabanı ifadeleri ve eksik kişi/iletişim bilgisi. Hiçbir `holdout3` cevabı son ölçüm öncesi çalıştırılmaz. Kod/veri/eşik hash'leri `reports/quality-freeze-v7.json` dosyasında dondurulur; sonuçlara göre değiştirilmez. Küçük ve ajan tarafından yazılmış veri bağımsız insan doğrulaması sayılmaz.

## Geliştirme kanıtı

İlişki merkezli ilk deneme `reports/quality-v3-probe.json` dosyasındadır. Son kodla Türkçe ofis notu, Türkçe ekli proje ataması ve açık onaylanmış plan iki tekrarda da geçerli çıktı verdi; proje adı tam, plan etiketi `PLANNED` oldu. Ofis/olay adlarının çekimli yazımı tekrarlar arasında değişebildi; bütün varlıkların kanonikleşmesi çözülmüş sayılmaz. Kayıt `reports/quality-v3-extraction-check.json`.

## Son doğrulama

**300 Python testi geçti**, başarısız/atlanan yok; pytest ölçümü 241,35 saniye. Bir mevcut Starlette/httpx deprecation uyarısı var. Ruff lint/format ve mypy (59 kaynak dosyası) başarılı. Son kayıt `reports/quality-tests-v7.xml`. Daha önceki 295/299 test sonuçları ara sürümlerdir. Arayüz kaynakları değiştirilmedi; bu dilimde yeni tarayıcı tasarım çalışması yapılmadı.

İlk tam koşu Windows'ta eşzamanlı aynı-kayıt testinde ilerlemedi. Kendi test sürecinin çağrı yığını Neo4j sürücüsünün bağlantı havuzu/EOF kontrolünü gösterdi; `reports/quality-v3-test-hang-stack.txt` kaydedildikten sonra yalnızca bu süreç durduruldu. Sürücü hatasının kök nedeni doğrulanmadı. Test tek başına geçti; ardından tam koşular da geçti. Son 300 testte aynı takılma olmadı; bu aralıklı gözlem gizlenmedi veya kalite hatalarıyla karıştırılmadı.

Nihai `holdout3` çıkarımında 8/8 not işlendi; etiketlenmiş sekiz ilişkinin tamamı ad/predicate/olumsuzluk/kip bakımından tam eşleşti. Yeni İngilizce onaylanmış plan `PLANNED`, olasılık `POSSIBLE`, Türkçe ekli proje ataması tam `Proje Martı` adıyla `WORKS_ON` ve Redis kullanımı `NEGATED` çıktı. Türkçe şube kaydı ilişki uydurmadan ham metin olarak arandı. Kaynak `reports/quality-final-extraction-preview.json`; aynı çıkarım final raporda da yer alır. Bu örneklerde D13/D14 kabulü sağlandı; bütün Türkçe metinlerin veya her plan ifadesinin doğru çözüleceği iddia edilmez.

Tam son cevap ölçümü ve canlı sürüm doğrulaması aşağıda kaydedilir. Genel kalite onayı henüz verilmez.

Geliştirme sırasında ilk aday incelemesi doğru çekimserlikleri de reddetti. İlk başlangıç koşusunda 9/9 not ve 1,000 kanıt recall elde edilmesine rağmen vector/hybrid yöntemlerinde dörder, graph yönteminde üç `GENERATION_INVALID` oluştu; yöntemlere göre doğru çekimserlik 0/5, 0/5, 2/5 kaldı. Bu koşu başarılı sayılmaz. Ham rapor `reports/evaluation-quality-baseline-v3/20261108T071533Z-d02c40/report.json` olarak korundu. Ham incelemede “başkent bilgisi yok” gerekçesiyle çekimserliğin yanlış reddedildiği görüldü. Bu nedenle adaydan bağımsız cevaplanabilirlik aşaması eklendi. Aynı sentetik başlangıç verisinde başkent ve dil tercihi soruları artık cevap üretilmeden çekimser kaldı.

Bu ilk geliştirme koşusu sırasında tanılama aynı veritabanının ortak inference kilidiyle araya girdi. Çağrılar eşzamanlı model yürütmesi yapmadı, ancak beklemeyi etkilediği için bu koşunun gecikmeleri bağımsız performans karşılaştırması olarak kullanılmaz. Son ayrılmış ölçüm tanı trafiği olmadan yapılır.

İkinci geliştirme denemesinde cevaplanabilirlik bütün sorular için bir ön kapıydı. Önceki holdout verisinde çekimserlik 3/3 ve recall 1,000 olsa da vector/hybrid yöntemleri yanıtlanabilir soruların yalnızca 4/7'sini, graph 5/7'sini cevapladı. Belirsizlik, ofis ve birden fazla kaynak soruları gereksiz engellendi. Bu gerileme kabul edilmedi; genel ön kapı kaldırılıp yukarıdaki aday türü denetimi ve çekimserlik için danışma kontrolü kullanıldı. İlk deneme `reports/evaluation-quality-regression-v4/20261108T073439Z-bf979d/report.json` olarak korunur. Sayısal recall/çekimserlik eşiklerinin tek başına yeterli olmadığını bu koşu da gösterir.

Son akışın hedefli canlı kontrolünde Harbor olasılığı, Ankara olayları ve Ember'in iki kaynak ifadesi cevaplandı; Rana'nın dil sorusundaki veritabanı cevabı reddedilip çekimserliğe dönüştü. Bu kontrol `reports/quality-v5-targeted-live.json` dosyasındadır. Sadece dört bilinen örnekle genel başarı ilan edilmez.

Önceki sentetik kaynakların başlık/metinleri birebir eşleştirilerek ve graf sürümü değişmeden üç yöntemde cevaplar tekrar ölçüldü; veri yeniden işlenmedi. Bu ara koşuda tüm yanıtlanabilir sorular cevaplandı fakat Rana dil sorusundaki ilgisiz kısmi cevap vector/hybrid'de hâlâ geçebildi. Bu nedenle açık dil isteğini modelin yeniden adlandırmasını engelleyen dar kural eklendi. Ara rapor: `reports/evaluation-quality-regression-v5/20261108T074737Z/report.json`. Son ayrılmış ölçüm bu kuralı da içerir.

## Son teslim durumu

8 Kasım son teslim: A–F yerel tek kullanıcı kapsamı tamamlandı. D13/D14/D16 örnek kabulü geçti; genel model doğruluğu garantisi verilmez. Yeni 5 not/8 soru üzerinde iki tekrar ve üç yöntemle 48 istek tamamlandı: her yöntemde yanıtlanabilir 12/12, doğru çekimserlik 4/4, kaynak recall 1,000, hata 0. Arayüz ve kullanım sınırları [teslim raporundadır](TESLIM_RAPORU.md). G dış erişim koşullu ve kapsam dışıdır.

Son yaklaşım: şema, kaynak aralığı, zincir ve bilinen tür çelişkisi zorunlu denetimlerdir. Aynı küçük modelin tek başına anlamsal itirazı bir onarım ister; ikinci itirazda geçerli kaynaklı cevap görünür belirsizlik uyarısıyla sunulabilir. Açık kesinlik sorularında çok dar kaynak koşullarıyla plan/olasılık alıntısından kısmi yanıt desteklenir. Nihai holdout4 sonrasında prompt/model/veri/eşik ayarı yapılmadı.
