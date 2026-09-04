from xml.etree import ElementTree

from tools.generate_sparkle_appcast import SPARKLE_NS, render_appcast


def test_appcast_contains_signed_arch_specific_release():
    xml = render_appcast(
        version="2.12.0",
        architecture="arm64",
        download_url="https://example.invalid/RealtimeSubtitle-2.12.0-macos-arm64.dmg",
        release_notes_url="https://example.invalid/notes.html",
        signature="signature+/=",
        length=12345,
    ).replace("__PUB_DATE__", "Wed, 02 Sep 2026 12:00:00 +0000")
    root = ElementTree.fromstring(xml)
    enclosure = root.find("./channel/item/enclosure")
    assert enclosure is not None
    assert enclosure.attrib[f"{{{SPARKLE_NS}}}edSignature"] == "signature+/="
    assert enclosure.attrib["length"] == "12345"
    version = root.find(f"./channel/item/{{{SPARKLE_NS}}}version")
    assert version.text == "2.12.0"
    assert "arm64" in root.findtext("./channel/title")
