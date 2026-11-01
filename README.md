# NovaDownloader

Zorin OS ve Ubuntu tabanlı Linux için Python 3.12 / PySide6 masaüstü uygulaması.

**Mevcut durum: Faz 2.2.** Tekil YouTube URL doğrulaması, arka planda gerçek
yt-dlp metadata analizi ve küçük resim desteği mevcuttur. Gerçek formatlardan
kalite/seçim modelleri ve boyut hesabı eklendi. Kalite seçim ekranı Faz 2.3'e
aittir; indirme ve gerçek dönüştürme henüz yoktur. Canlı YouTube doğrulaması ağ vekilinin
403 yanıtı nedeniyle engellenmiştir; deterministik testler canlı doğrulama sayılmaz.
İlerleme ve doğrulamalar: [PROJECT_PROGRESS](docs/PROJECT_PROGRESS.md).
Sonraki fazlar yalnızca kullanıcının talimatıyla başlatılır.

## Geliştirici kurulumu

Python 3.12 ve [uv](https://docs.astral.sh/uv/getting-started/installation/)
gereklidir. Zorin/Ubuntu sürümüne göre Python 3.12 ayrıca kurulmalıdır; sistem
Python'unu değiştirmeyin. Qt wheel'leri Qt'yi içerir; ayrıca pip ile `ffmpeg`
adlı paket kurmayın, o paket sistem FFmpeg'i değildir.

Ubuntu 24.04 / Zorin'in karşılık gelen paket depolarında:

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv ffmpeg libegl1 libgl1 \
  libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0 libxcb-icccm4 \
  libxcb-keysyms1 libxcb-image0 libxcb-render-util0
cd NovaDownloader
bash scripts/setup-dev.sh
bash scripts/setup-deno.sh  # npm gerektirir; yalnızca proje içine Deno kurar
source .venv/bin/activate
python -m novadownloader
```

`uv sync --frozen --group dev`, `.python-version` ve `uv.lock` kullanarak
`.venv` oluşturur ve kilitli paketleri kurar; sistem Python paketlerini değiştirmez.
`novadownloader` giriş noktası da sanal ortam etkinleştirildiğinde kullanılabilir.
`uv` uygun Python'u bulamazsa kendi desteklenen yönetilen Python'unu edinebilir.

Tam YouTube desteği için **Deno >= 2.3.0** gereklidir. Qt penceresi Deno eksikken
de açılır; analiz ise anlaşılır bağımlılık hatası verir. Bazı videolarda Deno
olmadan metadata alınabilse de EJS challenge desteği güvenilir değildir;
bu sürüm analiz öncesi Deno ve EJS kurulumunu kontrol eder. Deno'yu
[resmî kurulum belgesinden](https://docs.deno.com/runtime/getting_started/installation/)
kurup `PATH` içine ekleyin ve `deno --version` ile doğrulayın. Uygulama kendiliğinden
indirme/güncelleme yapmaz. `yt-dlp[default]`, yt-dlp'nin uyumlu EJS paketini içerir;
ayrıca rastgele bir EJS sürümü kurmayın.

Alternatif proje kurulumu: `bash scripts/setup-deno.sh`. Resmî `deno@2.9.6` npm
paketinin platform ikilisini `scripts/deno/package-lock.json` bütünlük hash'leriyle
`.tools/deno` içine kurar. Lifecycle scriptleri ve ek indirme fallback'leri
çalışmaz; `.venv/bin/deno` bu ikiliye bağlanır. Node/npm yalnızca bu kurulum
yöntemi için gerekir; uygulamanın çalışma zamanı değildir. Desteklenen sistemler
Linux x64/arm64 glibc'dir. Sistem paketi değişmez, farklı kullanıcı dosyası veya
bağlantısı üzerine yazılmaz. Python yorumlayıcısının yanındaki Deno, sanal ortam
etkinleştirilmeden de bulunur. `setup-dev.sh` sonrasında gerekirse tekrar çalıştırın.

## Doğrulama

```bash
source .venv/bin/activate
python -m novadownloader --version
python -m novadownloader --check-dependencies
QT_QPA_PLATFORM=offscreen pytest
ruff check .
ruff format --check .
QT_QPA_PLATFORM=offscreen python -m novadownloader --smoke-test
uv build
```

`--check-dependencies` JSON döndürür; tüm bileşenler kullanılabilir olduğunda
çıkış kodu 0, eksik/uyumsuz/başarısız kontrolde 1'dir. Python paket kontrolleri
kurulum sürümünü, dış araç kontrolleri sınırlı süreli sürüm komutunu doğrular;
YouTube erişimi veya gerçek indirme başarısı anlamına gelmez.

`--smoke-test` gerçek pencereyi oluşturur, asenkron tanılamayı bekler ve kapatır.
Eksik Deno tek başına GUI smoke testini başarısız yapmaz. `offscreen` yalnızca
headless test içindir; normal masaüstü kullanımında bu değişkeni ayarlamayın.
Zorin üzerinde ayrıca `python -m novadownloader --smoke-test` ve normal açılışla
görsel/fare/klavye doğrulaması yapılmalıdır.

## Kullanım (Faz 2.1)

URL alanına watch, youtu.be, shorts, mobil veya music YouTube bağlantısı
yapıştırıp Enter veya “Analiz et” kullanın. Takip parametreleri ve playlist
parametresi atılır; yalnızca seçili video analiz edilir. Playlist sayfası,
aldatıcı alan adları, kimliksiz bağlantılar, kullanıcı bilgili URL'ler ve özel
portlar reddedilir. Çıktıda başlık, kanal, süre ve mevcutsa küçük resim gösterilir.
Eksik alanlar “bilinmiyor”, başarısız thumbnail ise placeholder gösterir.

“İptal et” arka plan işlemini durdurur. Farklı bir bağlantıyı analiz etmek
öncekini iptal eder; eski sonuçlar yeni sonucu ezmez. İndirme yapılmaz. Ağ,
erişim, özel/silinmiş video ve extractor hataları çözüm önerileriyle gösterilir.
Analiz için toplam 45 saniye, her ağ isteğinde 12 saniye timeout, sınırlı retry
kullanılır. Kısıtlamaları aşacak cookie, proxy değiştirme veya DRM desteği yoktur.

Pencere araçların sürümlerini, eksikleri ve çözüm önerilerini listeler.
“Tekrar kontrol et” arka planda yeniden kontrol yapar. “Tanılamayı kopyala”
yalnızca sürüm/durum/açıklamayı panoya alır; ortam değişkenleri veya özel dosya
yollarını toplamaz. Kontrol veya analiz sürerken kapatma isteği güvenli durdurmayı
bekler. İndirme/geçmiş/ayar sayfaları bu fazın kapsamı dışındadır.

Teknik hata logu: `${XDG_STATE_HOME:-$HOME/.local/state}/novadownloader/application.log`.
Loglar sınırlı boyutta tutulur; URL ve yaygın kimlik doğrulama alanları maskelenir.
Log yazılamazsa stderr kullanılır. Video başlıkları Qt rich text olarak yorumlanmaz.
Thumbnail ağ işlemi asenkrondur; HTTPS doğrulaması korunur, yalnızca güvenilir
YouTube thumbnail alan adları kabul edilir ve boyut/süre sınırları uygulanır.

Canlı kontrol için normal masaüstünde bilinen bir herkese açık video URL'sini
analiz edin; gerçek başlık/kanal/süre ve küçük resmi karşılaştırın. Bulut ortamında
`www.youtube.com` ve `i.ytimg.com` erişimi gerekir. Mevcut makinede YouTube isteği
vekil tarafından 403 ile reddedildi; erişim açıldıktan sonra bu kontrol yeniden
yapılmalıdır. Bu faz video dosyası indirmez. yt-dlp ek metadata/manifest alan
adlarına ihtiyaç duyarsa ilgili hata ayrıca değerlendirilmelidir.

## Yapı ve kaynaklar

- [Uygulama planı](docs/IMPLEMENTATION_PLAN.md)
- [Mimari](docs/ARCHITECTURE.md)
- [İlerleme ve test kanıtı](docs/PROJECT_PROGRESS.md)
- [Bağımlılık kararları ve resmî kaynaklar](docs/DEPENDENCIES.md)
- [Format seçimi ve boyut modeli](docs/FORMAT_SELECTION.md)

Uygulama verileri için XDG yolları tanımlıdır; bu faz yalnızca teknik log yazar,
kişisel ayar veya görev verisi saklamaz. Kaynak kod MIT lisanslıdır. Qt/PySide6 ve diğer bağımlılıkların
lisansları ayrıdır; dağıtım öncesi LGPL/diğer yükümlülükler ayrıca incelenmelidir.
AppImage/DEB veya masaüstü kısayolu bu fazda üretilmemiştir.

Gelecekteki indirmeler yalnızca indirmeye yetkili olduğunuz içerikler için
kullanılmalıdır; erişim veya içerik korumalarını aşma desteği planlanmıyor.
