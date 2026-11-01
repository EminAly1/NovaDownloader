# NovaDownloader

Zorin OS ve Ubuntu tabanlı Linux için Python 3.12 / PySide6 masaüstü uygulaması.

**Mevcut durum: Faz 1.** Paket altyapısı ve gerçek bağımlılık tanılaması içeren
ilk Qt penceresi mevcuttur. Henüz YouTube analizi veya indirme yapmaz.
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
source .venv/bin/activate
python -m novadownloader
```

`uv sync --frozen --group dev`, `.python-version` ve `uv.lock` kullanarak
`.venv` oluşturur ve kilitli paketleri kurar; sistem Python paketlerini değiştirmez.
`novadownloader` giriş noktası da sanal ortam etkinleştirildiğinde kullanılabilir.
`uv` uygun Python'u bulamazsa kendi desteklenen yönetilen Python'unu edinebilir.

Tam YouTube desteği için **Deno >= 2.3.0** gereklidir. Bu fazın Qt penceresi
Deno eksikken de açılır ve eksikliği gösterir. Deno'yu
[resmî kurulum belgesinden](https://docs.deno.com/runtime/getting_started/installation/)
kurup `PATH` içine ekleyin ve `deno --version` ile doğrulayın. Uygulama kendiliğinden
indirme/güncelleme yapmaz. `yt-dlp[default]`, yt-dlp'nin uyumlu EJS paketini içerir;
ayrıca rastgele bir EJS sürümü kurmayın.

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

## Kullanım (Faz 1)

Pencere araçların sürümlerini, eksikleri ve çözüm önerilerini listeler.
“Tekrar kontrol et” arka planda yeniden kontrol yapar. “Tanılamayı kopyala”
yalnızca sürüm/durum/açıklamayı panoya alır; ortam değişkenleri veya özel dosya
yollarını toplamaz. Kontrol sürerken kapatma isteği güvenli durdurmayı bekler.
İndirme/geçmiş/ayar sayfaları bu fazın kapsamı dışındadır.

## Yapı ve kaynaklar

- [Uygulama planı](docs/IMPLEMENTATION_PLAN.md)
- [Mimari](docs/ARCHITECTURE.md)
- [İlerleme ve test kanıtı](docs/PROJECT_PROGRESS.md)
- [Bağımlılık kararları ve resmî kaynaklar](docs/DEPENDENCIES.md)

Uygulama verileri için XDG yolları tanımlıdır; bu faz kişisel ayar veya görev
verisi yazmaz. Kaynak kod MIT lisanslıdır. Qt/PySide6 ve diğer bağımlılıkların
lisansları ayrıdır; dağıtım öncesi LGPL/diğer yükümlülükler ayrıca incelenmelidir.
AppImage/DEB veya masaüstü kısayolu bu fazda üretilmemiştir.

Gelecekteki indirmeler yalnızca indirmeye yetkili olduğunuz içerikler için
kullanılmalıdır; erişim veya içerik korumalarını aşma desteği planlanmıyor.
