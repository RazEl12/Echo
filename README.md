# Patched nginx 1.25.5: drop-in replacement for nginx:1.25-bookworm

nginx 1.25.5 built from source on `debian:bookworm-slim`, with two CVEs fixed:
one by a backported upstream patch, one by a dependency version bump.

## Build and test

Requirements: Docker, Python 3 with `pytest` (`pip install pytest`).

```bash
make build   # builds the .deb from source (nginx-builder), then the final image
make test    # starts the original and the new image, compares their responses
```

`make test` does not build anything, so run `make build` first.
`make clean` removes the built images.

Notes:
- The image is tagged `custom-nginx:latest` and `custom-nginx:<timestamp>`.
- Built and tested on arm64 (Apple Silicon). The `.deb` file name contains the
  architecture, so the build also works on amd64.

## Image size

| Image | Size |
|---|---|
| `nginx:1.25-bookworm` (original) | 278 MB |
| `custom-nginx:latest` (this repo) | 282 MB |

The new image is about 4 MB larger. It builds the same set of modules as the
original, including the dynamic modules geoip, image_filter and xslt, which pull in
extra libraries. The njs module and the `-debug` variants are not built (see Limitations).


## CVEs fixed

| CVE | Severity | Component | Fix method | Evidence |
|---|---|---|---|---|
| CVE-2025-15467 | Critical | libssl3 (OpenSSL 3.0) | Version bump | [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2025-15467) |
| CVE-2026-97629 | High | nginx 1.25.5 | Backport | [Upstream commit](https://github.com/nginx/nginx/commit/1916f26e6ca49296568633d309777e36527e5bb2) |

**CVE-2025-15467 (version bump).** When OpenSSL parses a CMS (Auth)EnvelopedData message that
uses an AEAD cipher such as AES-GCM, it copies the IV into a fixed-size stack buffer without
checking its length, before any authentication. The result can be a crash or possibly remote
code execution. The original image ships libssl3 3.0.11; the new image is built on the
current `debian:bookworm-slim`, which has a fixed version. The `Containerfile` fails the
build if the installed libssl3 is older than `LIBSSL3_MIN_VERSION` (`3.0.18-1~deb12u2`), so
the fix cannot be lost silently when the base image changes. nginx does not normally parse
untrusted CMS messages, so the practical exposure is low, but the library is shared by
everything in the image and the fix is a plain package update.

**CVE-2026-97629 (backport).** Each nginx worker keeps a copy of the TLS session ticket keys
with three slots. On key rotation only two slots were synced from shared memory, so the
third kept uninitialized key material. The upstream commit syncs all slots
(`keys->nelts * sizeof(ngx_ssl_ticket_key_t)` instead of `2 * sizeof(...)`). It is saved as
`build/patches/CVE-2026-97629.patch` and applied to the 1.25.5 source in `build/Dockerfile`
before compiling. A backport was needed because the fix exists upstream but not in 1.25.5,
and the shipped version must stay 1.25.5 to remain a drop-in replacement.

## VEX: proving the backport to scanners

The backport does not change the version string (still `1.25.5-1`), and Trivy and Grype match
by package name and version, so they keep reporting CVE-2026-97629. `vex.json` (OpenVEX)
declares it `fixed` for `pkg:deb/debian/nginx@1.25.5-1`. Scanning with `--vex` makes it disappear:

| Scan | Without VEX | With `vex.json` |
|---|---|---|
| Grype (nginx findings) | 8, includes CVE-2026-97629 | 7, CVE-2026-97629 gone |
| Trivy (total) | 482 | 481, CVE-2026-97629 gone |

```bash
grype custom-nginx:latest --vex vex.json
trivy image --vex vex.json custom-nginx:latest
```

Reports are in `scans/before/` (original image) and `scans/after/` (this image).