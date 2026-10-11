# Security

For sensitive reports, use [private vulnerability reporting](https://github.com/Achilleus-1/Akis-Gif-inator/security/advisories/new)
when available, or the maintainer's public [contact links](https://linktr.ee/achilleus_).
Do not post credentials, private videos, local paths or unredacted dumps publicly.

Fixes target the latest release and `main`. There is no guaranteed response or
patch schedule. Include the version, OS, affected codec and reproduction with
synthetic data. Media parsers process untrusted input; use current dependencies.

The app uses local files and FFmpeg subprocesses without a shell, restricts input
protocols to file/pipe, validates clip/settings values, and writes completed
outputs atomically. It does not run a server, download media or collect telemetry.
Native video playback has its own decoder pipeline. These measures are not an
independent security audit or a guarantee that every malformed file is safe.
