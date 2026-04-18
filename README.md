# LyricsManager — Edición Audiófilo

Aplicación de escritorio para Windows que automatiza la búsqueda, sincronización y guardado de **letras** y **carátulas** en bibliotecas de música de alta resolución. Construida con PyQt6, pensada para colecciones FLAC/ALAC sin compromisos.

---

## ¿Qué hace?

### Letras
- Busca automáticamente en **LRCLIB** y **NetEase Cloud Music** con coincidencia por duración
- Prioridad de fuentes configurable desde Ajustes
- Guarda como **archivo `.lrc`** (misma carpeta o ruta personalizada) o **incrustado en los metadatos** del archivo de audio
- Soporte completo de **letras sincronizadas** (LRC con marcas de tiempo)
- Vista **Karaoke** — al reproducir, la línea activa se amplía y resalta en blanco; las demás se atenúan
- **Fetch en lote** para un álbum o carpeta completa desde el menú contextual, con iconos de estado por pista en tiempo real
- Opción para preferir letras sin marcas de tiempo (plain)

### Carátulas
- **Diálogo de búsqueda en streaming** — se abre al instante y muestra resultados uno a uno conforme llegan, desde **Cover Art Archive / MusicBrainz** e **iTunes**
- Prioridad de fuentes configurable
- Antes de guardar, un diálogo de **previsualización con slider de tamaño** (100 px hasta el original) permite elegir la resolución de salida con vista en vivo
- Guarda como **`cover.png`** junto al audio
- **Incrusta en metadatos** del archivo (bloque PICTURE en FLAC, APIC en ID3, covr en M4A)
- **Extrae carátula incrustada → `cover.png`** con el mismo flujo de previsualización/redimensionado
- Cero re-codificación cuando la fuente ya es PNG — los bytes se escriben directos
- Conversión JPEG→PNG automática cuando es necesario

### Explorador de biblioteca
- Escaneo recursivo de carpetas con soporte para FLAC, ALAC, MP3, AAC, OGG, WAV, AIFF, DSD (DSF/DFF), WMA
- Árbol **Artista → Álbum → Pista** con filtro en tiempo real
- Icono de disco codificado por calidad por pista:
  - 🟡 **DSD** (dorado oscuro)
  - 🟡 **Hi-Res** (dorado) — PCM ≥ 88,2 kHz o ≥ 24 bit
  - 🔵 **Lossless** (azul) — FLAC/ALAC 44,1/48 kHz 16 bit
  - 🟣 **MQA** (púrpura)
  - ⚫ **Lossy** (gris) — MP3, AAC, OGG…
- Iconos de estado de letras por pista durante operaciones en lote (buscando, encontrado sincronizado/plano, no encontrado)

### Metadatos
- Panel con miniatura de carátula, título, artista, álbum y año
- Badges de calidad, presencia de LRC y carátula
- Especificaciones técnicas: códec, frecuencia de muestreo, profundidad de bits, canales, bitrate, tamaño de archivo
- Sección de tags en bruto colapsable (▶/▼)

---

## Requisitos

| Dependencia | Versión mínima | Uso |
|---|---|---|
| Python | 3.11+ | Runtime |
| PyQt6 | 6.4 | Framework GUI |
| qtawesome | 1.3 | Iconos Font Awesome |
| mutagen | 1.46 | Lectura y escritura de metadatos de audio |
| Pillow | 10.0 | Procesado de imágenes / conversión a PNG |
| requests | 2.28 | Llamadas HTTP a APIs de letras y carátulas |
| sounddevice | 0.4.6 | Reproducción de audio |
| soundfile | 0.12.1 | Decodificación FLAC / WAV / AIFF |

---

## Instalación

```bash
# 1. Clonar
git clone https://github.com/rogerroca14/lyricsmanager.git
cd lyricsmanager

# 2. Entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Ejecutar
python main.py
```

> **Nota Windows:** `sounddevice` requiere el redistribuible de Visual C++. Descárgalo desde [Microsoft](https://aka.ms/vs/17/release/vc_redist.x64.exe) si la reproducción falla al primer arranque.

---

## Estructura del proyecto

```
lyricsmanager/
├── main.py                       # Punto de entrada — QApplication, tema, idioma
├── config.py                     # Persistencia de ajustes en JSON (%APPDATA%\LyricsManager)
├── requirements.txt
├── assets/
│   └── check.svg                 # Checkmark blanco para los checkboxes
├── core/
│   ├── metadata.py               # read_metadata(), embed_artwork/lyrics, AudioQuality
│   ├── music_scanner.py          # Escaneo recursivo de directorios
│   ├── lyrics_manager.py         # fetch_lyrics() — orquestación multifuente
│   └── artwork_manager.py        # ArtworkResult, fetch/save/embed carátulas
├── services/
│   ├── lrclib.py                 # API REST de LRCLIB
│   ├── netease.py                # API de NetEase Cloud Music
│   ├── musicbrainz.py            # Búsqueda de releases en MusicBrainz
│   ├── coverart.py               # Descarga desde Cover Art Archive
│   └── itunes.py                 # iTunes Search API
├── ui/
│   ├── theme.py                  # Stylesheet oscuro + helpers de badges, build_stylesheet()
│   ├── main_window.py            # QMainWindow — barra, menú, layout, workers
│   ├── library_view.py           # Panel árbol con iconos de calidad y estado
│   ├── metadata_view.py          # Panel de información de pista con carátula
│   ├── lyrics_view.py            # Panel de letras — vista karaoke + controles de player
│   ├── artwork_view.py           # Panel de carátula — incrustada + botones de acción
│   ├── artwork_search_dialog.py  # Diálogo de búsqueda en streaming con cards
│   ├── artwork_save_dialog.py    # Diálogo de previsualización y redimensionado
│   ├── settings_dialog.py        # Diálogo de ajustes con pestañas
│   ├── workers.py                # Workers QThread: Scan, Metadata, Lyrics, Artwork, Batch
│   └── player.py                 # AudioPlayer — streaming sounddevice, gestión de dispositivos
├── i18n/
│   ├── __init__.py               # t(key) lookup + set_language()
│   └── strings.py                # Diccionarios completos EN + ES
└── utils/
    └── helpers.py                # AUDIO_EXTENSIONS, format_duration, parse_lrc, etc.
```

---

## Formatos soportados

| Formato | Lectura | Letras | Carátula |
|---------|---------|--------|----------|
| FLAC    | ✅ | ✅ | ✅ |
| ALAC (M4A) | ✅ | ✅ | ✅ |
| MP3     | ✅ | ✅ (ID3) | ✅ (APIC) |
| AAC (M4A) | ✅ | ✅ | ✅ |
| OGG Vorbis | ✅ | ✅ | ✅ |
| WAV     | ✅ | — | — |
| AIFF    | ✅ | — | — |
| DSD (DSF/DFF) | ✅ | — | — |
| WMA     | ✅ | — | — |

---

## Configuración

Los ajustes se guardan en `%APPDATA%\LyricsManager\settings.json`. Valores por defecto:

```json
{
  "lyrics_save_mode": "lrc",
  "lrc_output_mode": "same_folder",
  "prefer_plain_lyrics": false,
  "lyrics_sources": ["lrclib", "netease"],
  "artwork_save_cover_png": true,
  "artwork_embed_metadata": false,
  "artwork_overwrite": false,
  "artwork_resize_cover": false,
  "artwork_cover_max_size": 600,
  "artwork_sources": ["coverart", "itunes"],
  "hires_sample_rate_threshold": 88200,
  "hires_bit_depth_threshold": 24,
  "audio_output_device": null,
  "language": "es"
}
```

---

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+O` | Abrir carpeta de biblioteca |
| `Ctrl+L` | Buscar letras para la pista actual |
| `Ctrl+I` | Buscar carátula para la pista actual |
| `Ctrl+,` | Abrir Ajustes |
| `Ctrl+Q` | Salir |

---

## Notas técnicas

- Todas las llamadas de red corren en **workers QThread** — la UI nunca se bloquea.
- `BatchLyricsWorker` emite `track_started / track_done / track_failed` por pista para actualizar el árbol en tiempo real.
- `ArtworkStreamWorker` emite `result_found(ArtworkResult)` por cada resultado; el diálogo inserta cards conforme llegan.
- `ArtworkSaveDialog` aplica un debounce de 120 ms antes de re-renderizar la vista previa de redimensionado.
- El stylesheet se construye en el arranque mediante `build_stylesheet(base_dir)`, que resuelve la ruta de `assets/check.svg` para mostrar el checkmark blanco en los checkboxes.

---

## Licencia

MIT — ver `LICENSE` para más detalles.
