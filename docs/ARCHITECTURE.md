# Mimari — Faz 2.1

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

Analiz iş mantığı `services`, tipli video metadata `models` altında mevcuttur.
Format/görev modelleri ve `database` henüz eklenmedi. SQLite şeması, ayarlar, kuyruk,
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
   dönüştürür. Formatlar ve medya URL'leri UI'ye taşınmaz; yalnızca küçük JSON
   metadata sonucu geri gelir. Eksik alanlar varsayılanlarla temsil edilir.
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
