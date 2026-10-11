# RTX 5070 Ti GIF export comparison

Measured locally on October 10, 2026 with an NVIDIA GeForce RTX 5070 Ti,
driver 616.92. Two exports per mode, reversing the CPU/GPU order on the second
repeat. Each selected clip was 3 seconds, using High (1280px, 24 fps), Sierra
dithering, and automatic size fitting off. Times include palette generation,
GIF encoding, probing and saving, including GPU initialization and downloads.

| Generated source | CPU decoding, mean | NVIDIA decoding, mean |
| --- | ---: | ---: |
| 1080p H.264, 60 fps | 3.23 s | 3.48 s |
| 4K HEVC, 10-bit, 30 fps | 3.03 s | 3.27 s |

GPU decoding worked, but total GIF export was about 8% slower in these samples.
CPU and GPU exports for each source had identical SHA-256 hashes. Decoding on
the GPU did not change the selected quality or output in these checks.

These are short synthetic clips, not a general performance claim. Source codec,
motion, resolution, frame rate, CPU, driver, and other running applications can
change the result. Compare the elapsed time shown by the app using the same
selection and settings on your own clips. GPU decoding is optional and off by
default; the app automatically retries on CPU if it cannot use NVDEC.

The source clips were generated with FFmpeg's `testsrc2` filter and encoded as
H.264 (`libx264`) and 10-bit HEVC (`libx265`). No personal footage or identifying
machine information is included in this report.
