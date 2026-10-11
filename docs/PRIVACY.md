# Privacy and storage

The running app makes no network requests, starts no local server, uses no
accounts and collects no telemetry. GitHub hosting and package installation
are separate installation/development activities, not conversion behavior.
The Windows installer contacts Python.org, PyPI's file host and, when needed,
Gyan's FFmpeg host to download pinned dependencies. These hosts can see normal
network metadata such as the IP address. No video is involved in installation.
No scheduled update service or background downloader is installed.

Videos are read from the selected local path. Source names, duration, dimensions,
frame rate and stream information remain in process memory. Intermediate palettes
and GIF candidates use a temporary directory, cleaned after work or app closure.
Finished GIFs are saved to `exports/` beside the application. A manually saved
copy is written only to the chosen location. Original videos are not modified.

Full output paths and filenames are displayed locally to help locate files.
They can reveal personal information if a screenshot is shared. Redact them
before posting a bug report. Application crashes or forced termination can leave
temporary files until the operating system removes them; no secure-erasure
guarantee is made.

Live glass uses pointer positions and click locations transiently inside this
window. These positions are not logged, saved or transmitted. The Dark mode boolean is stored locally using Qt settings (the Windows user
registry on Windows). No filenames, pointer history or credentials are stored
in that preference. GPU choices remain in memory.

The public preview uses a generated demo. Public source packaging follows a
file allowlist, excludes input/output media and caches, checks local user paths
and credential patterns, and uses the maintainer's public GitHub noreply identity.
License texts retain upstream attribution as required; these are public third-party
notices, not the maintainer's private contact details.
