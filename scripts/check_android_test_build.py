"""Verify isolation of the generated local Android test build without printing secrets."""
from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
A = "{http://schemas.android.com/apk/res/android}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-url", default="https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com/")
    args = parser.parse_args()
    package = "ru.tarotsphere.app.test"
    app = ROOT / "android/app/build"
    manifest = ET.parse(app / "intermediates/merged_manifests/debug/processDebugManifest/AndroidManifest.xml").getroot()
    assert manifest.get("package") == package, "Test package must be separate"
    application = manifest.find("application")
    assert application.get(A + "debuggable") == "true"
    assert application.get(A + "allowBackup") == "false"
    activities = {node.get(A + "name") for node in application.findall("activity")}
    assert "com.vk.id.internal.auth.RedirectUriReceiverActivity" not in activities, "Production VK callback in test build"
    schemes = {node.get(A + "scheme") for node in application.findall(".//intent-filter/data")}
    assert schemes == {package + ".rustore.pay"}, "Unexpected callback schemes"
    for node in application.findall("provider"):
        assert node.get(A + "authorities", "").startswith(package + "."), "Shared provider authority"
        assert node.get(A + "name") != "ru.rustore.sdk.pay.RuStorePayContentProvider", "Pay auto-initializer present"
    config = (app / "generated/source/buildConfig/debug/ru/tarotsphere/app/BuildConfig.java").read_text()
    assert 'VK_AUTH_ENABLED = false;' in config
    assert 'RUSTORE_BILLING_CONFIGURED = false;' in config
    assert 'APP_RELEASE_CHANNEL = "debug";' in config
    data = (ROOT / "android/data/build/generated/source/buildConfig/debug/ru/tarotsphere/app/data/BuildConfig.java").read_text()
    expected = args.staging_url.rstrip('/') + '/'
    assert f'API_BASE_URL = "{expected}";' in data, "Wrong test API"
    metadata = json.loads((app / "outputs/apk/debug/output-metadata.json").read_text())
    assert metadata['applicationId'] == package
    for element in metadata['elements']:
        assert element['versionName'].endswith('-test')
        assert (app / "outputs/apk/debug" / element['outputFile']).is_file()
    print("PASS: separate package/storage/providers, staging API, no production VK callback, purchases disabled")


if __name__ == "__main__":
    main()
