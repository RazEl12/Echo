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
extra libraries. The njs module and the `-debug` variants are not built (see Known differences from the original image).


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

## Triage

The original image has 831 findings in Trivy and 799 rows in Grype (500 distinct CVEs).
Instead of listing every CVE, findings are grouped by what can be done about them. The
"upstream fix" column comes from the [nginx.org security advisories](https://nginx.org/en/security_advisories.html)
for nginx and from the [Debian security tracker](https://security-tracker.debian.org/) for
Debian packages, not only from the scanners (which show no fixed version for nginx at all).

| Finding | Component | Upstream fix | Action |
|---|---|---|---|
| CVE-2025-15467 (Critical) + 47 other libssl3 CVEs | libssl3 3.0.11 | Debian bookworm: 3.0.22-1~deb12u2 | **Bump (done).** One rebuild on current bookworm-slim fixes all of them |
| CVE-2026-97629 | nginx 1.25.5 | nginx 1.30.6 / 1.31.7. No 1.25.x release | **Backport (done)** + VEX |
| CVE-2026-93479 | nginx | nginx.org lists 1.30.0-1.30.5 and 1.31.2-1.31.6 as affected, fixed in 1.30.6 / 1.31.7 | Not applicable: 1.25.5 is outside the affected range. Scanners report it because the package name matches Debian's nginx package |
| CVE-2026-15176, 97205, 95101 | nginx 1.25.5 (inside the affected range) | nginx 1.30.6 / 1.31.7 | Not fixed. A backport would work the same way, see Residual risk |
| CVE-2023-44487 (High) | nginx 1.25.5 | Not listed in the nginx.org advisories. Debian's tracker lists no fix for Debian's own nginx 1.22.1 in bookworm | Not fixed. Could not confirm the status for upstream 1.25.5, see Residual risk |
| CVE-2023-50387 (High) | libsystemd0, libudev1 | Debian systemd 252.38 / 252.39 | Closed by the newer base image, no extra work |
| curl and libcurl4 CVEs | curl 7.88.1 | Some fixed by Debian updates, the rest unfixed | Newer base closed some. Removing curl from the image would close the rest (not done) |
| CVE-2026-5450 and similar in libc6, libxml2, libtiff6 | Debian libraries | Debian: no fix for bookworm, marked "no-dsa (minor issue)" for libc6. Grype lists 174 such "won't fix" rows in the baseline | Cannot be fixed here |

Only CVE-2026-5450 (libc6) was checked individually against the Debian tracker. The other
"won't fix" rows are taken from Grype's "won't fix" label.

**Severity differs between sources.** nginx.org rates CVE-2026-93479, 15176, 97205, 95101 and
97629 as medium, while Grype and Trivy list several of them as Critical or High.

**Why these two.** libssl3 is the library behind every TLS connection nginx makes, and it had
the most Critical findings of any package. Updating it fixed 48 CVEs at once, with no change to
nginx itself. CVE-2026-97629 is in nginx's own TLS code and its upstream fix is a small,
self-contained commit, so it is a clean backport that can be proven with a VEX statement.

**Most of the drop is from the base image.** Distinct CVEs fell from 500 to 248, but most of
that comes from building on a current `debian:bookworm-slim` (the original image is on
Debian 12.5), not from the two fixes above.

## Residual risk

**nginx CVEs left unfixed.** CVE-2026-15176, 97205 and 95101 affect 1.25.5 (nginx.org affected
ranges: 0.1.29-1.31.6, 0.8.11-1.31.6 and 1.25.0-1.31.6) and are fixed upstream in 1.30.6 / 1.31.7.
Each one needs a specific configuration. Per the Debian security tracker descriptions:

- CVE-2026-15176: a location that uses `alias` with `rewrite` and a `set` or `return` that
  references `$request_filename` (or `$request_filename` in an access log format).
- CVE-2026-97205: AIO enabled, and an SSI page with `include virtual`.
- CVE-2026-95101: HTTP/3 with `proxy_request_buffering on`.

The default configuration uses none of these, so the default image is not exposed, but a user
with a custom configuration could be. nginx.org rates all of them as medium. I could not open the
detailed F5 advisories, so the exact upstream wording of these conditions is not verified; the
conditions above come from the Debian tracker.

**CVE-2026-97629 is patched, but the VEX statement only covers this one CVE.** Its exposure
condition is `ssl_session_cache shared:name:size` without an explicit `ssl_session_ticket_key`
file (automatic key rotation, which is the code the patch fixes). The default configuration has
no TLS server at all.

**CVE-2023-44487 (HTTP/2 Rapid Reset): status not confirmed.** nginx.org lists no advisory for
it, so I could not confirm from nginx.org whether 1.25.5 is affected. Not fixed, no VEX statement.

**Debian libraries with no fix.** Findings in libc6 (for example CVE-2026-5450, which Debian
marks "no-dsa, minor issue"), libxml2, libtiff6 and the rest of curl are marked "won't fix"
(174 rows in the Grype baseline). They cannot be fixed here without another base image or
removing components.

**What I would do next**
- Backport the three remaining nginx fixes with the same patch method, or move to nginx 1.30.6.
- Remove `curl` if the image does not need it (not done, to stay a drop-in replacement).
- Rebuild regularly so new Debian updates are picked up, and scan on every build.
- Add VEX statements for findings confirmed not applicable (CVE-2026-93479).

## Compatibility test

**What "working correctly" means.** For the same request, the new image returns the same status,
the same headers and the same body as `nginx:1.25-bookworm`. `Date`, `Last-Modified` and `ETag`
are ignored because they change from request to request and say nothing about behavior.

**How it runs.** `make test` (see [`test/test_nginx.py`](test/test_nginx.py), Python with pytest)
starts both images as separate containers, sends each of them the same requests and compares the
answers. Any difference fails the test and the exit code is non-zero.

| Test | What it checks |
|---|---|
| `test_root` | `GET /`, the default welcome page |
| `test_not_found` | `GET` of a page that does not exist (404) |
| `test_head` | `HEAD /` |
| `test_custom_hello`, `test_custom_redirect` | A custom config ([`test/custom.conf`](test/custom.conf)) mounted into both images: a plain response and a 301 redirect |
| `test_post_small`, `test_post_too_large` | `POST` under and over `client_max_body_size` (200 and 413) |
| `test_malformed_request` | Raw garbage instead of HTTP. Only the status line is compared, because the headers contain `Date` |
| `test_https_hello` | `GET` over TLS with a self-signed certificate ([`test/ssl.conf`](test/ssl.conf), [`test/certs/`](test/certs)) |

**Checked by hand, not by the test.** `docker inspect` shows the same user, entrypoint, exposed
ports and stop signal in both images, and the `configure` flags are the same except `--with-cc-opt`
and `--with-ld-opt` (Debian's hardening flags, which I did not reproduce).

**Not covered.** `stream` and `mail` modules, HTTP/2 and HTTP/3, TLS session resumption (the code
CVE-2026-97629 changes), the entrypoint's template substitution, and behavior under load.

## Known differences from the original image

- The njs module and the `-debug` variants of the modules are not built.
- `--with-cc-opt` and `--with-ld-opt` (Debian's build flags) are not reproduced.
- The `NJS_VERSION` and `NJS_RELEASE` environment variables are not set, because njs is not built.
- Built and tested on arm64 only.
- TLS session resumption, `stream`, `mail`, HTTP/2 and HTTP/3 are not covered by the tests.

## What surprised me

- **The patch kept showing up in the scan.** After applying the backport, Trivy and Grype still
  reported CVE-2026-97629, because they compare the package name and version and do not look at
  the code in the image. The version string is unchanged, so nothing looked fixed. I first
  considered hard-coding a different version string so the scanner would think it was fixed, but
  that would be misleading: it hides the CVE without saying why. The honest way is a VEX statement
  that says the CVE is fixed and explains how (`vex.json`).
- **The image did not get smaller, and modules were missing.** My first build was 163 MB, much
  smaller than the original (278 MB). It turned out the original ships four dynamic modules
  (geoip, image_filter, njs, xslt) and about 36 more packages that they pull in. I added three of
  them to stay a drop-in replacement and the image grew to 282 MB, 4 MB larger than the original.
- **Most of the drop in findings comes from the base image.** Distinct CVEs fell from 500 to 248,
  but updating libssl3 alone fixed 48 of them, and curl and systemd findings were closed just by
  installing from a current Debian. The two fixes I chose are a small part of the drop.
- **A missing symlink broke `load_module`.** In the original image `/etc/nginx/modules` points to
  `/usr/lib/nginx/modules`. Without that link, `load_module modules/...` failed with "cannot open
  shared object file" even though the module files were there. One `ln -s` in the `Containerfile`
  fixed it.

## What I would do differently with more time

- Backport the three other nginx CVEs that affect 1.25.5 (CVE-2026-15176, 97205 and 95101) with
  the same patch method, keeping the shipped version at 1.25.5.
- Build the njs module and the `-debug` variants, and reproduce Debian's `cc-opt` / `ld-opt` flags.
- Add tests for TLS session resumption, `stream` and HTTP/2.
- Verify the checksum or signature of the nginx source tarball in `build/Dockerfile`.

## AI tools used

- **Gemini Pro:** used to plan the approach and to build the base of the project, which I
  controlled and understood before moving on. Later I also used it, with a strict prompt that
  allowed only primary sources, to cross-check the CVE facts against my own checks. It also
  hurt once: it produced a CVE patch that looked real but had no real upstream commit hash, so
  I rejected it and used the actual upstream commit (1916f26). Since then I check claims
  against primary sources instead of trusting generated patches or summaries.
- **Antigravity:** used next, for editing project files. It was sometimes misleading, and its
  credits ran out quickly, so I moved on to Claude Code.
- **Claude Code:** used for the rest. It explained each step, helped design the compatibility
  test, checked CVE facts against nginx.org and the Debian security tracker, and helped write the
  README. It also made mistakes, for example an early claim that Trivy never reported nginx, so I
  checked its claims against the scan reports.