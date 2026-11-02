# Mimari — Faz 2.3

## Mevcut modüller

- `app.py` / `__main__.py`: bağımsız CLI tanılama veya QApplication oluşturma.
  `--check-dependencies` yolunda Qt GUI modülleri yüklenmez.
- `core/dependencies.py`: immutable tipli sonuçlar; Python/paket metadata
  sürümleri ve `PATH` üzerinden FFmpeg/FFprobe/Deno sürüm komutları.
  Shell kullanılmaz; her dış çağrıda 2 saniye zaman aşımı vardır. Ağ çağrısı,
  otomatik kurulum, güncelleme veya gizli değer toplama yapılmaz.
- `core/paths.py`: XDG config/data/cache/state keşfi. Geçersiz göreli XDG
  değerleri yok sayılır. İçe aktarma ve keşif dosya sistemi oluşturmaz.
- `workers/dependency_worker.py`: kontrollü QThread; yalnızca sinyaller gönderir.
  Widget'lara erişmez. Kontroller arasında kesilme isteğini değerlendirir.
- `ui/main_window.py`: tanılama görüntüleme, yeniden kontrol ve pano eylemi.
  Tek worker çalışır. Kapatma sırasında kesilme ister; event loop'u bloklamadan
  worker'ın bitmesini bekler. QThread zorla sonlandırılmaz.
- `ui/themes/dark.qss`, `resources/icon.svg`: wheel içine dahil görsel kaynaklar.

## Hata ve yaşam döngüsü

Eksik, uyumsuz ve çalıştırma hatası birbirinden ayrıdır. Eksik Deno ilk
pencerenin açılmasını engellemez; tam YouTube desteği için gereklidir. Tanılama
başarısı gelecekteki YouTube erişimini doğrulamaz. Paketin kurulu olması,
paketin tüm özelliklerinin çalışması anlamına gelmez. İlk pencerenin gerçekten
oluşturulması Qt'nin kullanılabilirliğini ayrıca doğrular.

Beklenmeyen bağımlılık worker hatası GUI'de güvenli, tekrar denenebilir hata olarak
gösterilir; hiçbir traceback veya ortam değeri UI/panoya aktarılmaz.
Bağımlılık kontrolünü kapatma en fazla o anki araç komutunun zaman aşımı
süresini bekler. Yaşayan worker varken QApplication sonlandırılmaz.

## Sonraki fazlar

Analiz iş mantığı `services`, tipli video metadata ve format/seçim modelleri
`models` altında mevcuttur. Görev modelleri ve `database` henüz eklenmedi. SQLite şeması, ayarlar, kuyruk,
bildirim ve dosya açma bu fazda mevcut değildir.

Tek bir uygulama süreci kullanılacak; web sunucusu, kullanıcı hesabı veya
frontend/backend ayrımı yoktur. Qt sinyalleri GUI sınırını koruyacak. İndirme
altyapısı yt-dlp/FFmpeg'e dayanacak; özel HTTP indirme motoru yazılmayacak.

## Faz 2.1 analiz akışı

1. `services/youtube_url_validator.py` alan adı allowlist'i, URL bileşenleri ve
   11 karakterlik video ID doğrulamasıyla kanonik tek video HTTPS URL'si üretir.
   Playlist URL'si reddedilir; video URL'sindeki `list` gibi yan parametreler atılır.
2. `ui/analysis_panel.py` giriş, durum ve metadata görünümünü yönetir.
   `AnalysisWorker` GUI dışında `VideoAnalyzer` çağırır. Aynı anda tek analiz
   worker'ı ve en fazla bir bekleyen en yeni istek bulunur.
3. `services/video_analyzer.py` yt-dlp/EJS/Deno ön kontrolünden sonra yeni bir
   süreç grubunda `python -m novadownloader.workers.analysis_process` çalıştırır.
   GUI thread'i bu beklemeye katılmaz. Kesilme veya 45 saniye timeout'ta yalnızca
   bu süreç grubu durdurulur; gerektiğinde SIGKILL kullanılıp süreç beklenir ve
   pipe'lar kapatılır. Qt thread'ine `terminate()` uygulanmaz.
4. Alt süreç, yalnızca normalize YouTube URL'sini
   `YoutubeDL.extract_info(download=False)` ile okur; playlist/indirme/remote
   EJS indirme kapalıdır. Ağ timeout 12 saniye, retry/extractor retry 1'dir.
   Çalışma proxy ve TLS ortamı miras alınır; erişim engelleri aşılmaz.
5. `models/video_metadata.py` metadata'yı savunmacı şekilde immutable modele
   dönüştürür. Faz 2.2 itibarıyla formatların güvenli alanları da JSON sonucu
   içinde geri gelir; medya URL'leri ve HTTP kimlik bilgileri taşınmaz.
   Eksik alanlar varsayılanlarla temsil edilir.
6. Artan istek kimlikleri başarı/hata/iptal sonucunu GUI sınırında doğrular.
   Eski worker ve eski thumbnail yanıtı yeni sonucu değiştiremez. Yeni istek,
   eski worker'ın güvenle bitmesinden sonra başlar; sınırsız thread birikmez.
7. `ui/thumbnail.py` Qt Network ile asenkron HTTPS yükler; ortamdaki HTTP
   proxy'sini korur. Redirect otomatik takip edilmez. 10 saniye toplam süre,
   2 MiB veri, 16 milyon piksel ve JPEG/PNG/WebP sınırları vardır. Hata, boş URL
   veya iptalde placeholder gösterilir; hata metadata başarısını bozmaz.

`core/exceptions.py` kullanıcı mesajlarını teknik hatadan ayırır.
`core/logging_config.py` XDG state altında dönen log oluşturur, URL ve yaygın
kimlik doğrulama alanlarını maskeler. yt-dlp debug/request dump toplanmaz.
Geçersiz URL kullanıcıya gösterilir; teknik servis/thumbnail hataları loglanır.
Faz 1 bağımlılık worker'ı henüz teknik log kullanmaz; mevcut güvenli hata
bildirimi korunmuştur.

## Faz 2.2 veri yolu

`extract_info(download=False)` → `VideoMetadata.from_info` → `MediaFormat`
tuple'ı → JSON alt süreç protokolü → ana süreçte yeniden doğrulama.
`VideoMetadata.formats` varsayılan olarak boştur, önceki metadata tüketicileri
çalışmaya devam eder. Faz 2.3 kalite ekranı aynı sonucu kullanır; ikinci analiz
worker'ı veya ek ağ isteği oluşturulmaz.

`build_catalog(metadata.formats, metadata.duration_seconds, is_live=metadata.is_live)`
çağrısı UI bağımsız `FormatCatalog` üretir. Seçimler format ID'lerini, eşleşen
sesi, çıkış kapsayıcısını, öneriyi ve FFmpeg gereksinimini taşır. Kaynak akış
boyutu ve nihai çıktı tahmini ayrı alanlardır. `make_mp3_option` yalnızca bir
dönüşüm planı üretir; FFmpeg çağırmaz. Hesap ve seçim modülleri Qt veya ağ kullanmaz.

Politikalar, birimler ve ertelenen işler [FORMAT_SELECTION.md](FORMAT_SELECTION.md)
içinde açıklanır. Kalite seçenekleri Faz 2.3 arayüzünde sunulur.

## Faz 2.3 widget ve seçim akışı

- `ui/theme.py`: merkezi renk/boşluk/radius token'ları; `dark.qss` şablonunu
  uygulama açılışında çözer. Hover, focus, checked, error ve disabled durumları
  ortak kurallardadır. `ui/icons.py` aynı palette özgün SVG çizgi ikonları üretir.
- `MainWindow`: sol navigasyon + dört kaydırılabilir sayfa. 900 px altında
  erişilebilir ad/tooltips korunan kompakt ikon navigasyonu; minimum 640×520.
  Tanılama Ayarlar'a taşındı, mevcut worker/kopyalama/tekrar kontrol korunur.
- `UrlInputWidget`, `VideoPreviewCard`, `EmptyStateWidget`: ortak görünüm
  bileşenleri. Yükleme/hata/boş durumları ayrı dosyalar yerine URL ve durum
  bileşenlerinde tutulur. Başlık üç satırda elide edilir; tam metin tooltip ve
  erişilebilir adda korunur. Thumbnail 16:9'dur, ölçek/DPI değişiminde sınırlı
  çözümlenmiş görüntüden yeniden ölçeklenir; ağ ve decoder sınırları korunur.
- `AnalysisPanel`: mevcut request ID, pending istek ve worker yaşam döngüsünü
  sürdürür. URL düzenleme, temizleme, yeni analiz ve iptal metadata/kalite/özet
  durumunu birlikte sıfırlar. Eski sonuç seçimi yeniden etkinleştiremez.
- `services/selection_service.py`: `build_catalog` sonucuna, desteklenen ilk
  gerçek ses kaynağından `make_mp3_option` ile tek 192 kbps MP3 dönüşüm planı
  ekler. Codec/sıralama/boyut kurallarını yeniden yazmaz; Qt ve ağ içermez.
- `MediaTypeSelector`, `QualityOptionCard`, `QualitySelectionPanel`:
  `QButtonGroup` ile tek seçim, mod başına geçerli seçimi hatırlama, ok/Home/End
  desteği. Odaklanan satır kaydırma alanında görünür kılınır. UI boyut hesaplamaz;
  servis modellerindeki kesinlik ve hazır boyut etiketlerini gösterir.
- `DownloadSummaryCard`: seçim, kaynak/çıktı farkı, FFmpeg gereksinimi ve
  isteğe bağlı teknik ayrıntılar. İndirme butonu daima devre dışıdır.
- `models/download_request.py`: video ID/kaynak URL/başlık/FormatSelection
  içeren immutable istek. Yalnızca metadata'ya ait kullanılabilir akışları
  kabul eder. Dosya yolu, indirme yürütücüsü veya postprocessor başlatmaz.

Seçim bu oturumda bellektedir; yeni analizde ve kapanışta temizlenir. Sayfa
geçişi analiz worker'ını çoğaltmaz, pencere kapanışı her iki worker'ı bekler.
`tests/ui/test_phase23.py` gerçek widget davranışını; `scripts/capture-ui.py`
yalnızca geliştirmede etiketli fixture ile ekran görüntülerini doğrular.
Üretim giriş noktasında fixture veya sahte başarı yolu yoktur.
