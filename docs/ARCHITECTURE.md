# Mimari — Faz 1

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

Beklenmeyen worker hatası GUI'de güvenli, tekrar denenebilir hata olarak
gösterilir. Bu faz henüz log altyapısı içermez; hiçbir traceback veya ortam
değeri UI/panoya aktarılmaz. Kapatma en fazla o anki araç komutunun zaman aşımı
süresini bekler. Yaşayan worker varken QApplication sonlandırılmaz.

## Sonraki fazlar

Analiz/indirme iş mantığı `services`, tipli video/format/görev modelleri `models`,
kalıcılık `database` altında eklenecek. Bu katmanlar henüz uygulanmadığından
boş modül veya sahte davranış oluşturulmadı. SQLite şeması, ayarlar, kuyruk,
bildirim ve dosya açma bu fazda mevcut değildir.

Tek bir uygulama süreci kullanılacak; web sunucusu, kullanıcı hesabı veya
frontend/backend ayrımı yoktur. Qt sinyalleri GUI sınırını koruyacak. İndirme
altyapısı yt-dlp/FFmpeg'e dayanacak; özel HTTP indirme motoru yazılmayacak.
