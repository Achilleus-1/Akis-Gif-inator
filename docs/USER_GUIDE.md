# User guide

Aki's Gif-inator is a Product of Achilleus. The native app converts local MP4
and MKV videos to animated GIFs. It never uploads the video.

## Launch

For a configured source checkout, use `Start Akis Gif-inator.cmd`, or run
`python app.py` from an environment with the pinned requirements and FFmpeg on
PATH. A locally built `Akis-Gif-inator.exe` needs no separately installed Python
or FFmpeg. Keep the executable in a writable folder so exports can be saved.
The public source ZIP does not contain the executable or dependencies.

## Select and trim

Drop one MP4 or MKV, or choose a file. The whole video is initially selected.
Drag the blue handles on the thumbnail strip to move the start and end. Clicking
the strip seeks without changing the selection. Play selection previews only
that interval. Start and End fields accept exact seconds.

First 10 sec selects the beginning; Full video resets the range. Arrow keys
move the focused timeline handle by 0.1 seconds, Shift+Arrow by one second.
Tab switches from the first handle to the second. Original files are untouched.

If the native player cannot display a codec, thumbnails and FFmpeg export can
still work. The preview is muted; audio is not present in GIF output.

## Quality and size

High is the default: up to 1280px on the longest edge and 24 fps. Much higher
offers up to 1920px and 30 fps. Neither dimensions nor frame rate exceed the
source's measured values. Extra detail and above use Sierra dithering; Compact
and Balanced use Bayer dithering. GIF color palettes contain at most 256 colors.

Choose your destination's size budget. With Auto-fit size off, the app preserves
your selected detail and warns if the measured GIF exceeds the target. With it
on, the app tries fewer frames before reducing dimensions and palette colors.
It preserves selected duration even if the smallest result remains oversized.

Shorten selection to fit estimates a shorter clip using the last GIF's size.
Review the timeline and export again. The estimate is approximate because
different moments contain different motion and detail; the new size is checked.

## NVIDIA decoding

NVIDIA GPU decoding tries NVDEC on CUDA device 0, then retries the full export
on CPU if unavailable or unsupported. No CUDA toolkit installation is needed;
the GPU needs a compatible NVIDIA driver. GIF filters and encoding remain on
CPU. The footer and result show the actual mode, plus elapsed export time.

This switch does not improve resolution or palette quality. Compare the same
clip, detail and fitting settings with it on and off. It is off by default.
The video player's GPU activity is independent of export decoding.

## Glass and motion

Live glass enables the local OpenGL backdrop: moving Aero ribbons, refracted
panel edges, soft pointer reflections and click ripples. Text, controls and
videos remain native widgets and are not distorted. Rendering is capped at
20 fps and a maximum 1024px framebuffer dimension. It pauses while minimized
or inactive. Turn it off for still gradients; unsupported graphics fall back
automatically. Pointer positions are never recorded or transmitted.

## Save and cancel

Export GIF saves to `exports/` beside the app and starts the animated preview.
Filenames are unique. Open folder reveals the export; Save a copy opens a native
dialog. Cancel stops the current work. Closing the app stops work and cleans
intermediate files. Only completed GIFs are exposed in the output folder.

The app displays source and output filenames and full output paths locally.
Crop or redact these before sharing screenshots. Synthetic examples are used
in this repository's preview. See [privacy details](PRIVACY.md).
