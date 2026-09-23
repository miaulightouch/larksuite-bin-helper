#!/usr/bin/env python3
"""Update larksuite-bin from Lark's public download metadata."""

import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

METADATA_URL = "https://www.larksuite.com/api/package_info?platform=10"
TERMS_URLS = {
    "_licensever": "https://www.larksuite.com/en_us/user-terms-of-service",
    "_licensever_us": "https://www.larksuite.com/en_us/user-terms-of-service-us",
}


def release(metadata):
    item = metadata["data"]
    match = re.fullmatch(r"Linux-x64-deb@V(\d+(?:\.\d+)+)", item["version_number"])
    if not match:
        raise ValueError("invalid Linux x64 version")
    version = match.group(1)
    url = item["download_link"]
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.path.endswith(f"/Lark-linux_x64-{version}.deb")
        or parsed.fragment
    ):
        raise ValueError("unexpected Linux x64 download URL")
    md5 = item["hash"].lower()
    if not re.fullmatch(r"[0-9a-f]{32}", md5):
        raise ValueError("invalid vendor MD5")
    return version, url, md5


def terms_date(page):
    content = html.unescape(page.decode("utf-8"))
    for label in ("Last Updated", "Effective Date"):
        _, found, following = content.partition(f"{label}:")
        if found:
            day, comma, year = following.lstrip().partition(",")
            if not comma:
                raise ValueError("terms date is malformed")
            return datetime.strptime(f"{day}, {year.lstrip()[:4]}", "%B %d, %Y").strftime("%Y%m%d")
    raise ValueError("terms date is missing")


def replace_one(text, pattern, replacement):
    result, count = re.subn(pattern, lambda _: replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"expected one PKGBUILD match for {pattern!r}; found {count}")
    return result


def field_value(pkgbuild, field):
    values = [line.split("=", 1)[1] for line in pkgbuild.splitlines() if line.startswith(f"{field}=")]
    if len(values) != 1:
        raise ValueError(f"expected one PKGBUILD value for {field}; found {len(values)}")
    return values[0]


def render(pkgbuild, version, pkgrel, dates, digest):
    pkgbuild = replace_one(pkgbuild, r"^pkgver=\d+(?:\.\d+)+$", f"pkgver={version}")
    pkgbuild = replace_one(pkgbuild, r"^pkgrel=\d+$", f"pkgrel={pkgrel}")
    for field, date in dates.items():
        pkgbuild = replace_one(pkgbuild, rf"^{field}=\d{{8}}$", f"{field}={date}")
    return replace_one(pkgbuild, r"^b2sums=\('[0-9a-f]{128}'", f"b2sums=('{digest}'")


def update(path):
    with urlopen(METADATA_URL, timeout=30) as response:
        version, url, vendor_md5 = release(json.load(response))
    dates = {}
    for field, terms_url in TERMS_URLS.items():
        with urlopen(terms_url, timeout=30) as response:
            dates[field] = terms_date(response.read())
    pkgbuild = path.read_text()
    current = field_value(pkgbuild, "pkgver")
    newer = tuple(map(int, version.split("."))) > tuple(map(int, current.split(".")))
    if not newer and version != current:
        raise ValueError("upstream version moved backwards")
    pkgrel = int(field_value(pkgbuild, "pkgrel"))
    previous_dates = {field: field_value(pkgbuild, field) for field in dates}
    if any(dates[field] < previous_dates[field] for field in dates):
        raise ValueError("terms date moved backwards")
    if not newer and dates == previous_dates:
        print(f"Already current: {current}-{pkgrel}; terms: {dates}")
        return False

    blake2b = hashlib.blake2b()
    md5 = hashlib.md5(usedforsecurity=False)
    download = path.parent / f"Lark-linux_x64-{version}.deb"
    with urlopen(url, timeout=120) as response, download.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            blake2b.update(chunk)
            md5.update(chunk)
            output.write(chunk)
    if md5.hexdigest() != vendor_md5:
        download.unlink()
        raise ValueError("download does not match Lark's MD5")

    next_rel = 1 if newer else pkgrel + 1
    path.write_text(render(pkgbuild, version, next_rel, dates, blake2b.hexdigest()))
    print(f"Updated {current}-{pkgrel} -> {version}-{next_rel}; terms: {dates}")
    return True


if __name__ == "__main__":
    update(Path(sys.argv[1]))
