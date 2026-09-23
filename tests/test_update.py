import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from update import terms_date, update


class UpdateTest(unittest.TestCase):
    def test_effective_date_fallback(self):
        self.assertEqual(terms_date(b"Effective Date: January 22, 2026"), "20260122")
        with self.assertRaises(ValueError):
            terms_date(b"Last Updated: February 30, 2026")

    def test_version_and_terms_updates(self):
        payload = b"deb content"
        url = "https://lf16-larkversion-new-sign.larksuitecdn.com/obj/lark-version-sg/abc123/Lark-linux_x64-2.0.0.deb?x-expires=123&x-signature=test"
        metadata = {
            "data": {
                "version_number": "Linux-x64-deb@V2.0.0",
                "download_link": url,
                "hash": hashlib.md5(payload).hexdigest(),
            }
        }
        global_page = b"Last Updated: January 22, 2026; Effective Date: January 22, 2026"
        us_page = b"Last Updated: January 22, 2026"
        source = (
            "pkgver=1.0.0\npkgrel=3\n_licensever=20260122\n_licensever_us=20260122\nb2sums=('"
            + "0" * 128 + "' 'SKIP' 'SKIP')\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            pkgbuild = Path(directory) / "PKGBUILD"
            pkgbuild.write_text(source)

            def fetch(address, timeout):
                if "package_info" in address:
                    return io.BytesIO(json.dumps(metadata).encode())
                if "user-terms-of-service-us" in address:
                    return io.BytesIO(us_page)
                if "user-terms-of-service" in address:
                    return io.BytesIO(global_page)
                return io.BytesIO(payload)

            with patch("update.urlopen", side_effect=fetch):
                self.assertTrue(update(pkgbuild))
                self.assertFalse(update(pkgbuild))

            result = pkgbuild.read_text()
            self.assertIn("pkgver=2.0.0", result)
            self.assertIn("pkgrel=1", result)
            self.assertIn(hashlib.blake2b(payload).hexdigest(), result)
            self.assertIn("'SKIP'", result)
            self.assertEqual((Path(directory) / "Lark-linux_x64-2.0.0.deb").read_bytes(), payload)

            metadata["data"]["version_number"] = "Linux-x64-deb@V3.0.0"
            metadata["data"]["download_link"] = url.replace("2.0.0", "3.0.0")
            metadata["data"]["hash"] = "0" * 32
            with patch("update.urlopen", side_effect=fetch), self.assertRaises(ValueError):
                update(pkgbuild)
            self.assertEqual(pkgbuild.read_text(), result)
            self.assertFalse((Path(directory) / "Lark-linux_x64-3.0.0.deb").exists())

            metadata["data"]["version_number"] = "Linux-x64-deb@V2.0.0"
            metadata["data"]["download_link"] = url
            metadata["data"]["hash"] = hashlib.md5(payload).hexdigest()
            global_page = b"Last Updated: January 23, 2026"
            us_page = b"Last Updated: January 24, 2026"
            with patch("update.urlopen", side_effect=fetch):
                self.assertTrue(update(pkgbuild))
            result = pkgbuild.read_text()
            self.assertIn("pkgver=2.0.0\npkgrel=2", result)
            self.assertIn("_licensever=20260123", result)
            self.assertIn("_licensever_us=20260124", result)


if __name__ == "__main__":
    unittest.main()
