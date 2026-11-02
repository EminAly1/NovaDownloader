# Format seçimi ve boyut sözleşmesi — Faz 2.2

## API

```python
from novadownloader.services.format_selector import build_catalog, make_mp3_option

# metadata, VideoAnalyzer.analyze sonucudur; yeniden ağ isteği gerekmez.
catalog = build_catalog(metadata.formats, metadata.duration_seconds, is_live=metadata.is_live)
for choice in catalog.video_options:
    print(choice.display_name, choice.format_expression, choice.available)

if catalog.audio_options:
    source = catalog.audio_options[0].audio
    conversion = make_mp3_option(source, metadata.duration_seconds, 192, is_live=metadata.is_live)
```

Bu kod indirme/dönüştürme yapmaz. UI `FormatSelection` üzerinden `resolution`,
`fps`, `codec`, `kind`, `recommended`, `format_ids`, `required_audio_id`,
`requires_merge/remux/conversion`, `ffmpeg_required` ve boyutları kullanabilir.
Teknik ayrıntılar iç içe `video` / `audio` modellerindedir. `dataclasses.asdict`
ve `json.dumps(..., allow_nan=False)` ile modeller serileştirilebilir.
Metadata protokolünden gelen alanlar yeniden `MediaFormat.from_info` ile doğrulanır;
rastgele bir sözlük doğrudan dataclass kurucusuna güvenilir veri diye verilmemelidir.

Analizde `check_formats=False` kullanılır; yt-dlp'nin oynatılabilirlik kontrolü
için örnek medya indirmesi de kapalıdır. Format varlığı çıkarıcı verisine dayanır;
medyanın gerçekten indirilebilir olduğu bu fazda doğrulanmaz.

## Keşif ve normalizasyon

Yalnızca yt-dlp'nin mevcut `formats` dizisi kullanılır; çözünürlük seçenekleri
sabit üretilmez. `QUALITY_NAMES` sadece bilinen yüksekliklerin görünen isimlerini
çevirir. 864p gibi farklı yükseklikler de mevcutsa korunur.

Format ID, genişlik/yükseklik, FPS, ext, vcodec/acodec, tbr/vbr/abr, dosya boyutu,
protocol; ayrıca dil/tercih, format notu, HDR, kanal ve örnekleme bilgisi saklanır.
Codec'i eksik olduğu için audio/video türü anlaşılamayan girdiler, storyboard ve
DRM işaretli akışlar elenir. None/bozuk sayılar bilinmiyor olur. Pozitif sonlu
sayısal dizgeler kabul edilir; bool/NaN/sonsuz/negatif/sıfır kabul edilmez.
Tam boyutlar float'a çevrilmeden korunur; savunmacı üst sınır 2^63−1 byte'tır.

Medya URL'leri, başlıklar içindeki kimlik doğrulama ve cookie'ler saklanmaz.
Güvenli literal ID karakterleri dışındaki değerler ve `best`, `bestaudio.2`
gibi yt-dlp seçici takma adları elenir. Çakışan aynı ID'ler belirsiz olduklarından
kullanılmaz. Gelecek indirme motoru URL'leri yeniden analiz ederek edinmelidir.

## Eşleştirme, sıralama ve öneri

- Muxed video/ses için tek gerçek ID; video-only için `video_id+audio_id`.
- MP4 video için H.264/HEVC/AV1 + AAC; WebM için VP8/VP9/AV1 + Opus/Vorbis.
  MP4 içinde Opus teknik olarak mümkün olsa da bu sürüm daha muhafazakâr
  uyumluluk politikası kullanır. Uygun karışık codec'ler MKV ile birleştirilir.
  Codec bilinmiyorsa uyumluluk uydurulmaz.
- Eşleştirme önce yt-dlp dil tercihini, ardından mevcut kapsayıcıyla uyumu,
  ardından ses bit hızını ve deterministik ID sırasını kullanır.
- Uyumlu ses yoksa video seçeneği bilgi için korunur, `available=False`,
  `format_expression=None` olur; sessiz video yanlışlıkla önerilmez.
- Video listesi çözünürlük ve FPS azalan sıradadır. Codec profili, HDR, FPS,
  bitrate ve dil farkları korunur. Aynı ID tekrarları kaldırılır; kalite alanları
  eşleşen farklı transport kopyalarında doğrudan HTTP ve bilinen boyut tercih
  edilir. Kalite kanıtı eksikse farklı ID'ler birleştirilmez.
- Günlük kullanım önerisi: kullanılabilir en yüksek ≤1080p, yoksa en düşük
  >1080p; o yükseklikte H.264/MP4, FPS ve basit işlem tercihi. Yükseklik
  bilinmiyorsa video önerisi yapılmaz. Ses önerisi dil tercihi ve bit hızına
  dayanır; farklı codec'lerin algısal kalitesi arasında kesin üstünlük iddiası yoktur.

Mevcut muxed kaynağın kapsayıcısı korunur. Video/audio birleştirmesi FFmpeg
gerektirir. HLS muxed/ses kaynakları için olası kapsayıcı işlemi muhafazakâr
olarak FFmpeg gerektiren remux ile işaretlenir. Bunlar henüz çalıştırılan işlemler değildir.

## Boyut hesabı

`estimate_stream`: pozitif gerçek filesize → filesize_approx → süre×bitrate×1000/8
→ bilinmiyor. `tbr` varsa toplamdır, aynı akışın `abr` değeri tekrar eklenmez.
`tbr` yoksa video-only vbr, audio-only abr kullanır; muxed için hem vbr hem abr
bilinmelidir. Eksik parça sıfır kabul edilmez. Ayrı akışlarda ikisinin boyutu
toplanır; biri bilinmiyorsa toplam da bilinmez. Her parça kesinse toplam kaynak
boyutu kesindir; herhangi bir tahmin varsa toplam tahminidir.

`download_size` kaynak akışların toplamıdır. `output_size` doğrudan kaynak için
aynıdır; birleştirme/remux için bilinmiyor tutulur. MP3 hedef çıktısı, süre ve
hedef bitrate üzerinden yaklaşık hesaplanır. MP3 seçimi kaynağın MP3 olduğunu
veya daha yüksek hedef bitrate'in kaynak kalitesini artırdığını göstermez.
Opus/WebM kaynağı `.opus` çıktısı için remux gerektirir; M4A/AAC kaynağı doğrudan
korunabilir. Canlı yayınların toplam boyutları bilinmiyor tutulur.

Birimler SI: KB=1000, MB=1,000,000, GB=1,000,000,000 byte. Gösterim yuvarlanır;
tam byte değeri modelde korunur. Tahminler “Yaklaşık”, bilinmeyenler “Boyut
bilinmiyor” olarak gösterilir. Kesinlik enum'u ve tahmin kaynağı ayrıca saklanır.
Dosya başlıkları, mux overhead, platformun yeniden kodlaması veya yeniden analiz
gerçek boyutu değiştirebilir; gelecekteki indirme ilerlemesi gerçek verilerle yenilenmelidir.

## Doğrulama sınırları

Deterministik fixture ile çıkarıcı → çocuk JSON → ana süreç → katalog ve mevcut
Qt metadata ekranı test edilir. yt-dlp'nin gerçek format seçicisiyle üretilen
ID ifadesi de medya indirmeden çalıştırılır. Bu testler canlı YouTube erişimi veya
FFmpeg medya işleme testi değildir. Canlı denemede proxy 403 engeli devam etti.
Faz 2.3 UI'si bu modelleri kullanır. Kullanıcı tercihlerinin kalıcılığı, gerçek
indirme/dönüştürme ve canlı platform erişiminin doğrulanması ertelenmiştir.
