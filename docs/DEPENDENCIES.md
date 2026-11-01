# Bağımlılıklar ve resmî kaynaklar

2026-11-01 tarihinde Faz 1 hazırlığında incelendi. Tam çözülmüş sürümler ve
artefakt hash'leri `uv.lock` içindedir. Yeni sürüm almak bilinçli bir
`uv lock --upgrade` ve yeniden test gerektirir; uygulama bunu otomatik yapmaz.

- Python 3.12 hedeflenir (`>=3.12,<3.13`); bulut ortamında 3.12.14 mevcuttur.
- PySide6/Qt 6: Qt Widgets, sinyal/slot, QSS ve worker yaşam döngüsü.
- `yt-dlp[default]`: sonraki fazdaki motorun bağımlılığı; bu fazda sürüm
  tanılaması yapılır. `default`, o yt-dlp sürümüne uygun `yt-dlp-ejs` içerir.
- FFmpeg/FFprobe: Python paketi değildir; sistemdeki araç sürümleri çalıştırılarak
  denetlenir. İndirme sonrası birleştirme/dönüşüm sonraki fazdadır.
- Deno >= 2.3.0: resmî yt-dlp EJS belgesindeki alt sınır. Bulunmaması veya
  daha eski olması açıkça raporlanır. Tam YouTube desteği için gereklidir.
- Geliştirme: pytest, pytest-qt, Ruff, Hatchling ve uv.

## Doğrulanan resmî belgeler

1. [Qt for Python başlangıç](https://doc.qt.io/qtforpython-6/gettingstarted.html)
   — doğrudan belge sitesi bulut ağ politikasında kapalı olduğundan aynı resmî
   belgenin [Qt kaynak deposu](https://github.com/pyside/pyside-setup/blob/dev/sources/pyside6/doc/gettingstarted.rst)
   üzerinden Python uyumluluğu, venv ve pip/wheel kurulumu incelendi.
2. [yt-dlp README](https://github.com/yt-dlp/yt-dlp#dependencies)
   — FFmpeg/FFprobe, EJS ve JS runtime gereksinimleri.
3. [yt-dlp EJS wiki](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
   — Deno alt sınırı, varsayılan Deno desteği ve `default` grubunun EJS içerdiği
   doğrulandı. EJS sürümünü bağımsız yükseltmekten kaçınılır.
4. [Deno kurulumu](https://docs.deno.com/runtime/getting_started/installation/)
   — belge sitesi kapalı olduğundan [resmî belge kaynağı](https://github.com/denoland/docs/blob/main/runtime/getting_started/installation.md)
   incelendi. Otomatik uygulama başlangıcı kurulumu tasarlanmadı.
5. [PyPI](https://pypi.org/): paket sürümleri ve Python alt sınırları API
   metadatasıyla doğrulandı; indirme sırasında TLS/hash doğrulaması korundu.

Bulut ortamı Debian 13'tür; bu kayıt Zorin üzerinde çalışma kanıtı değildir.
Zorin/Ubuntu GUI, sistem paketleri ve dağıtım/lisans kontrolleri ayrıca gerekir.
