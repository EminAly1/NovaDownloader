# NovaDownloader uygulama planı

## Çalışma sözleşmesi

Mevcut depo başlangıçta boş ve commit içermiyor. Python 3.12 ve Qt Widgets
(PySide6) ile yerel Linux uygulaması geliştirilecek. UI, servisler, modeller ve
kalıcılık ayrı sorumluluklar olacak. Ağ/indirme ve uzun süren araç kontrolleri
UI iş parçacığında çalışmayacak. Gerçek veriler gelmeden metadata, kalite veya
ilerleme gösterilmeyecek.

**Her turda tek faz:** Faz sonunda testler ve ilerleme kaydı güncellenir, yerel
commit oluşturulur ve durulur. Kullanıcı “Sonraki faza geç” demeden sonraki faz
başlatılmaz. Onaysız push yapılmaz. Yeni oturumda önce bu dosya ve
`docs/PROJECT_PROGRESS.md` okunur.

## Faz 1 — Depo inceleme ve temel altyapı (tamamlandı, onaylandı)

1. Git durumu, araçlar ve resmî kurulum gereksinimlerini doğrula.
2. `src` yerleşimi, `pyproject.toml`, Python sürüm tercihi ve kilitli geliştirme
   bağımlılıkları oluştur. Uygulamayı `python -m novadownloader` ile çalıştır.
3. XDG yolları ile Python, PySide6, yt-dlp, EJS, FFmpeg, FFprobe ve Deno için
   test edilebilir, zaman aşımı olan salt okunur tanılama oluştur. Kendiliğinden
   araç indirme/güncelleme yapma. Eksikleri çözüm önerisiyle göster.
4. Koyu temalı, yeniden boyutlandırılabilen ilk Qt penceresini; arka planda
   bağımlılık kontrolü, tekrar kontrol ve tanılama kopyalama eylemleriyle aç.
   İndirme/analiz ekranlarını bu fazda çalışırmış gibi sunma.
5. Birim ve Qt testleri, komut satırı/GUI smoke testi, Ruff ve paket derlemesini
   çalıştır. Linux CI ve gerçek geliştirme kurulum belgesini ekle.
6. `PROJECT_PROGRESS.md` içerisine sonuçları, sınırlamaları ve sonraki görevleri
   kaydet; yerel commit oluştur ve dur.

Çıkış kriteri: Paket kurulabilir; ilk Qt penceresi açılır, kapanış güvenlidir,
bağımlılık eksikleri anlaşılır gösterilir. Headless test, Zorin masaüstünde
manuel doğrulama veya gerçek YouTube indirmesi yerine geçmez.

## Faz 2 — Video analizi (alt fazlar halinde)

### Faz 2.1 — URL doğrulama ve metadata (tamamlandı, onaylandı)

- YouTube watch / kısa / shorts / mobil / music bağlantılarını güvenli ayrıştır,
  tekil video kimliğini doğrula ve kanonik HTTPS URL üret.
- Tipli, eksik alanlara dayanıklı metadata; `extract_info(download=False)`.
- QThread yönetimi ve iptal edilebilir, süre sınırına sahip yt-dlp alt süreci.
  İstek kimlikleriyle geç kalan sonuçları yok say. Güvenli kapanışı koru.
- Basit URL alanı, yükleme/iptal/başarı/hata ve asenkron thumbnail/placeholder.
- Kullanıcıya anlaşılır hata, teknik log; yerel Deno kurulumu ve belgeleme.
- Deterministik servis/worker/UI testleri ve mevcut 26 testin yeniden çalışması.
  Canlı YouTube erişimi ayrıca denenir; ağ engeli başarı sayılmaz.
- Faz sonunda ilerleme kaydı ve yerel commit; **Faz 2.2'ye otomatik geçilmez**.

Kalite listesi, format seçimi, boyut tahmini ve indirme bu alt fazın dışındadır.

### Faz 2.2 — Format seçimi ve boyut hesabı

Durum: Tamamlandı; 249 test başarılı. Canlı doğrulama proxy 403 nedeniyle engelli.
Faz 1 ve 2.1 onaylandı; `origin/work`
normal push sonrası `36b82cd18f9b334bb547894c238eeb925f3d4682` olarak doğrulandı.

- Mevcut metadata akışını URL/kimlik bilgisi taşımayan tipli formatlarla genişlet.
- Gerçek video/audio keşfi; çözünürlük/FPS/codec ayrımı ve deterministik sıralama.
- Uyumlu akış eşleştirme, MP4/WebM/MKV kapsayıcı ve FFmpeg gereksinimleri.
- Kesin/tahmini/bilinmeyen kaynak boyutu ile nihai çıktı boyutunu ayır.
- Ses kaynakları ve yalnızca model düzeyinde MP3 dönüşüm seçeneği.
- Mevcut 135 test + yeni deterministik model/servis/protokol testleri, Ruff,
  paket ve headless GUI doğrulaması. Canlı erişimi mevcut izinlerle ayrıca dene.
- Yerel commit oluştur; Faz 2.2 henüz onaylanmadığı için push yapma ve dur.

Kapsam dışı: Faz 2.3 kalite seçim ekranı, indirme ve gerçek dönüştürme.

### Faz 2.3 — Kalite seçim arayüzü (başlatılmadı)

- Onay sonrası mevcut `FormatCatalog` üzerinden video/ses seçeneklerini sun.
- Seçimi, boyut kesinliğini, kaynak/çıktı farkını ve FFmpeg gereksinimini göster.
- Kayıp ses/format ve bilinmeyen değer durumları için UI testleri ekle.
- Faz 2.2 commit'ini yalnızca kullanıcı onayından sonra push edip remote'u doğrula.
- İndirme motoruna bu alt faz üzerinden otomatik geçme.

Faz 2'nin aşağıdaki genel görevleri alt fazlara bölünerek sürdürülecektir.

- Sıkı YouTube URL doğrulaması; tipli metadata ve format modelleri.
- İptal edilebilir arka plan yt-dlp analizi; zaman aşımı ve hata sınıflandırma.
- Asenkron thumbnail; yalnızca mevcut çözünürlük/codec/FPS seçenekleri.
- UI'den bağımsız boyut hesabı: kesin > yaklaşık > süre/bitrate > bilinmiyor.
  Ayrı ses/video toplamı, muxed bitrate ve dönüşüm boyutu ayrımı.
- Deterministik fixture testleri; canlı analiz ayrı ve isteğe bağlı.

Çıkış kriteri: Desteklenen URL gerçek metadata ve formatlarla analiz edilir;
arayüz yanıt verir, hatalar ve eksik boyutlar doğru gösterilir.

## Faz 3 — İndirme motoru

- Gerçek format kimliği seçimi, uyumlu ses/video eşleştirme ve FFmpeg işleme.
- Disk/izin kontrolü, güvenli dosya adı, üzerine yazmayı önleme.
- yt-dlp ilerleme hook'ları, sınırlı retry/timeout/fragment eşzamanlılığı.
- Kooperatif iptal, korunmuş `.part` verisiyle desteklenen devam etme;
  post-processing ayrı durum ve güvenli süreç kapanışı.
- Fixture ve yerel medya ile işlevsel testler; izinli canlı indirme opt-in.

Çıkış kriteri: Doğru çıktı gerçek dosyaya kaydedilir, işleme bitmeden tamamlandı
gösterilmez, ağ/alan/izin hataları ve kaynak yaşam döngüsü test edilir.

## Faz 4 — Tam kullanıcı arayüzü

- Ana sayfa, indirmeler, geçmiş, ayarlar navigasyonu ve işlevsel sayfalar.
- Önizleme kartı, dinamik video/ses seçimleri ve gerçek ilerleme.
- Koyu/açık tema, SVG ikonlar, erişilebilir odak/kısayollar ve küçük ekranlar.
- Boş, yükleniyor, hata, tekrar dene ve eksik dosya durumları.

Çıkış kriteri: Dar ve geniş pencerede tutarlı, işlevsel ve test edilmiş UX.

## Faz 5 — Kuyruk ve kalıcılık

- SQLite şeması/migration; job UUID ve doğrulanmış durum geçişleri.
- Varsayılan iki eşzamanlı iş; bağımsız hata/iptal/devam ve güvenli kapanış.
- Ayar/geçmiş saklama, XDG konumları ve dosya yöneticisi/bildirim entegrasyonu.
- Açılışta yarım işleri tamamlandı saymadan ve otomatik indirmeden kurtarma.

Çıkış kriteri: İşler/ayarlar yeniden açılışta korunur ve kuyruk test edilir.

## Faz 6 — Teslim ve Linux doğrulaması

- Kritik servis/UI/integration testlerini ve CI'ı tamamla.
- Gerçek Zorin/Ubuntu masaüstünde smoke, ölçekleme ve dosya açma doğrulaması.
- Kurulum/kullanım/mimari belgeleri ve desktop launcher/ikon.
- Paketleme/lisans gereksinimlerini değerlendir; yalnızca üretilip doğrulanan
  paketleri hazır say. Gerçek test sayıları ve sınırlamalarla teslim raporu.

## Genel kabul ve kapsam

Her fazın kanıtı ilerleme dosyasında tutulur. Erişim engelleri aşılmaz;
indirme yalnızca kullanıcının yetkili olduğu içeriklerle doğrulanır. Playlist,
toplu URL, zamanlama, altyazı ve güncelleme denetimi çekirdekten sonraya bırakılır.
