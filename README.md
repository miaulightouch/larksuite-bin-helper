# larksuite-bin-helper

Daily (03:17 UTC), or on manual dispatch, the GitHub Action
checks Lark's
[Linux package metadata](https://www.larksuite.com/api/package_info?platform=10)
and the Last Updated dates on both official terms pages. When the package or
either date changes, it checks Lark's MD5, updates `PKGBUILD`, regenerates
`.SRCINFO`, builds the package, then
commits and pushes to the [larksuite-bin AUR repository](https://aur.archlinux.org/packages/larksuite-bin).
The two dates become separate license filename suffixes. A terms-only change
increments `pkgrel`.

Publish the revised `PKGBUILD` and `download-lark.sh` to AUR first. Then publish
this directory as a GitHub repository with the workflow on its default branch.
Add the repository secret `AUR_SSH_PRIVATE_KEY` containing a dedicated SSH
private key whose public key is registered on the AUR maintainer account. The workflow
verifies the AUR host's [published Ed25519 fingerprint](https://aur.archlinux.org/)
before using the key. Run **Update AUR** manually once after setup.

Run `python3 -m unittest discover -s tests` to check the updater locally.
