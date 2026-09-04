# macOS automatic updates

Realtime Subtitle embeds Sparkle 2.9.6 in macOS packages. The Python/PyQt
application talks to `SPUUpdater` and `SPUStandardUserDriver` through a minimal
Objective-C bridge; Sparkle owns the update UI, release notes, download,
EdDSA verification, installation, and relaunch.

## Product behavior

- **Realtime Subtitle → Check for Updates…** and **Settings → System →
  Software Updates** invoke the same Sparkle controller.
- Automatic checks and automatic download/install are enabled by default and
  remain user-configurable. The normal product flow is one quiet sequence:
  check, download, EdDSA verification, install, and relaunch. Sparkle keeps
  detailed stages in its diagnostic log; the application exposes only a
  concise update state or one actionable macOS prompt when consent is
  unavoidable.
- Apple Silicon reads `appcast-arm64.xml`; Intel reads
  `appcast-x86_64.xml`. Separate feeds prevent two same-version DMGs from
  competing during package selection. `appcast.xml` is also published as a
  conventional human-facing feed.
- Release notes are published as a versioned HTML asset and shown by Sparkle.
- `SUEnableSystemProfiling` is disabled. The updater does not send a hardware
  profile to the feed host.

## Trust chain

The official Sparkle archive is pinned by version and SHA-256 before it is
embedded. Every DMG enclosure is signed with Sparkle EdDSA and the public key
is embedded as `SUPublicEDKey`. Developer ID signing and Apple notarization are
separate controls: EdDSA authenticates the update payload to the installed
app, while Developer ID and notarization establish macOS platform trust.

Never commit private keys, certificates, passwords, or App Store Connect API
keys. Configure these GitHub Actions secrets:

| Secret | Purpose |
|---|---|
| `SPARKLE_ED25519_PRIVATE_KEY` | Base64 Sparkle Ed25519 private seed used by `sign_update` |
| `APPLE_DEVELOPER_CERTIFICATE_BASE64` | Base64 Developer ID Application `.p12` |
| `APPLE_DEVELOPER_CERTIFICATE_PASSWORD` | `.p12` password |
| `APPLE_SIGNING_IDENTITY` | Exact `Developer ID Application: …` identity |
| `APPLE_NOTARY_KEY_BASE64` | Base64 App Store Connect API `.p8` |
| `APPLE_NOTARY_KEY_ID` | API key ID |
| `APPLE_NOTARY_ISSUER_ID` | API issuer ID |

Until an Apple Developer Program identity is available, macOS bundles are
ad-hoc signed and the downloaded update is authenticated by Sparkle EdDSA.
This is the highest automated trust chain available to the project today and
does not create a second update system. The release job refuses to publish an
appcast when the Sparkle private key is absent. Developer ID signing and Apple
notarization can later be layered onto this same feed and installation flow.

An unsigned-by-Apple build may still be subject to Gatekeeper on first launch.
The updater must first attempt normal in-place installation. A manual prompt
or opening an already-downloaded, already-verified DMG is permitted only after
an observed macOS replacement failure; users must never be sent back to
GitHub to choose an architecture or download the release again.

## Release verification

1. Install version N in a writable Applications folder; do not run the update
   test from the read-only DMG.
2. Publish version N+1 with the Sparkle secret configured. Apple credentials
   are optional until the project enrolls in Apple Developer Program.
3. Open version N and use **Check for Updates…**.
4. Confirm the version, release notes, architecture-specific DMG, download,
   EdDSA verification, installation, relaunch, and new bundle version.
5. Always verify `codesign --verify --deep --strict`, both appcast XML files,
   both DMGs, and `SHA256SUMS.txt`. When Apple credentials are configured, also
   require `spctl --assess --type execute` and `xcrun stapler validate`.

## Unsigned-by-Apple validation

Release validation copies an older app bundle to a writable local directory,
points it at a loopback appcast, signs the new DMG enclosure with the same
Sparkle key used by Actions, and invokes the hidden `--update-smoke` trigger.
The test records whether Sparkle can download, authenticate, replace, and
relaunch the ad-hoc-signed bundle. A fallback is added only for the exact step
macOS is observed to block.

The full loopback regression was run on 2026-09-05 on Apple Silicon with an
ad-hoc-signed 2.11.99 application and a locally served 2.12.0 archive. Sparkle
found the architecture-specific update, downloaded it, logged a successful
EdDSA verification, and replaced the writable application bundle. Because the
PyQt UI executes through portable Python, Sparkle did not identify that
interpreter as the bundle executable to relaunch. The app therefore includes a
small dependency-free relaunch helper: after the bridge confirms that the
installed `CFBundleVersion` exactly matches the version Sparkle selected, the
GUI shuts down normally; the helper waits for that process to exit and asks
LaunchServices to reopen the replaced bundle. The observed old-process exit to
new-process launch interval was about two seconds.

The native launcher also sets `PYTHONDONTWRITEBYTECODE=1`. Without it, a first
Python launch can create `__pycache__` files inside `Contents/Resources` and
invalidate the signed bundle after packaging. CI now starts each architecture's
real application once and then repeats strict deep code-signature verification,
which fails if that launch added or changed any sealed bundle resource.

No macOS authorization prompt and no manual DMG step occurred in this test.
Sparkle also logged the expected code-signature mismatch between independently
ad-hoc-signed builds; this was non-fatal because the enclosure's EdDSA
signature was valid. Consequently the product has no manual install branch at
present. A verified-DMG fallback will be added only if a future regression on
a supported macOS version demonstrates an actual replacement failure.

## Primary sources and license

- Sparkle setup and security: <https://sparkle-project.org/documentation/>
- Programmatic updater setup: <https://sparkle-project.org/documentation/programmatic-setup/>
- Publishing and EdDSA signing: <https://sparkle-project.org/documentation/publishing/>
- Nested-code signing guidance: <https://sparkle-project.org/documentation/sandboxing/>
- Apple notarization workflow: <https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution>

Sparkle is MIT-licensed. The complete upstream license and bundled third-party
notices are copied to `Contents/Resources/ThirdPartyLicenses/Sparkle-LICENSE`
in every macOS application bundle.
