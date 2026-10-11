# Troubleshooting

## FFmpeg missing in a source checkout

Install FFmpeg/FFprobe from a provider you trust and make both available on PATH,
or place them in `bin/` with their required libraries. Restart the app afterwards.
For a standalone local build, pass `build.py --ffmpeg-dir` with the binary folder.
The app does not download codecs or run an installer for you.

## GPU mode says CPU instead

That is automatic fallback, not a failed export. Check the result notice. GPU
decoding requires a working NVIDIA driver and a codec/pixel format the decoder
and download path support. Unusual formats and some rotated videos may use
CPU. The checkbox is independent of the Live glass appearance switch.

## GPU mode is slower

Palette generation, resizing, dithering and GIF encoding still use CPU. GPU
initialization and frame transfers can outweigh decoding savings, especially
for short clips. Use the elapsed export times to compare the same selection.

## GIF is too large or text is soft

Leave Auto-fit size off to preserve detail; shorten the clip or choose a larger
budget. When size fitting is on, dimensions and frame rate can drop below the
chosen preset. The result shows the actual output. Tiny source text and color
gradients are subject to GIF's limited palette and sharing-site processing.

## Still glass is shown

Live OpenGL rendering is unavailable, disabled, or running headlessly. The still
Aero design is the intended fallback and does not affect conversion. Shader
animation pauses when the window is inactive or minimized.

## Preview cannot play the source

Native playback and FFmpeg export use different pipelines. Use timeline
thumbnails and exact times; try exporting a short clip. Invalid or corrupt files
may fail in both. The app only selects a non-cover-art video track.

## Saving fails

The app needs permission to write its `exports/` directory. Move the local
executable to a writable folder. Save a copy needs a writable destination too.
Avoid protected system folders. Preserve your original video while troubleshooting.

Report bugs with the version, OS, source codec and a synthetic reproducer. Remove
personal filenames and paths. Do not upload a private video or a memory dump.
