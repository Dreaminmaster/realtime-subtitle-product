#!/usr/bin/env python3
"""Generate a deterministic Sparkle 2 appcast for one macOS architecture."""

from __future__ import annotations

import argparse
import html
from pathlib import Path


SPARKLE_NS = "http://www.andymatuschak.org/xml-namespaces/sparkle"


def render_appcast(*, version: str, architecture: str, download_url: str,
                   release_notes_url: str, signature: str, length: int) -> str:
    values = {
        "version": html.escape(version, quote=True),
        "architecture": html.escape(architecture, quote=True),
        "download_url": html.escape(download_url, quote=True),
        "release_notes_url": html.escape(release_notes_url, quote=True),
        "signature": html.escape(signature, quote=True),
        "length": int(length),
    }
    return """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="{namespace}">
  <channel>
    <title>Realtime Subtitle · macOS {architecture}</title>
    <link>https://github.com/Dreaminmaster/realtime-subtitle-product/releases</link>
    <description>Signed Realtime Subtitle updates for macOS {architecture}</description>
    <language>en</language>
    <item>
      <title>Realtime Subtitle {version}</title>
      <sparkle:version>{version}</sparkle:version>
      <sparkle:shortVersionString>{version}</sparkle:shortVersionString>
      <sparkle:minimumSystemVersion>13.0</sparkle:minimumSystemVersion>
      <sparkle:releaseNotesLink>{release_notes_url}</sparkle:releaseNotesLink>
      <pubDate>__PUB_DATE__</pubDate>
      <enclosure url="{download_url}"
                 length="{length}"
                 type="application/octet-stream"
                 sparkle:os="macos"
                 sparkle:edSignature="{signature}" />
    </item>
  </channel>
</rss>
""".format(namespace=SPARKLE_NS, **values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--architecture", choices=("arm64", "x86_64"), required=True)
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--release-notes-url", required=True)
    parser.add_argument("--signature", required=True)
    parser.add_argument("--length", required=True, type=int)
    parser.add_argument("--pub-date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    xml = render_appcast(
        version=args.version,
        architecture=args.architecture,
        download_url=args.download_url,
        release_notes_url=args.release_notes_url,
        signature=args.signature,
        length=args.length,
    ).replace("__PUB_DATE__", html.escape(args.pub_date))
    args.output.write_text(xml, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
