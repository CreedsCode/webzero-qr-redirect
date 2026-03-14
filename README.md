# webzero-qr-redirect

*Privacy-preserving QR redirect counter for WebZero event activations. Counts scans without collecting any personal data — no IPs, no cookies, no timestamps. Drop a QR at any event, measure adoption, and prove the server does exactly what it says.*

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](#license)
[![Build](https://img.shields.io/github/actions/workflow/status/CreedsCode/webzero-qr-redirect/release.yml?label=build)](https://github.com/CreedsCode/webzero-qr-redirect/actions)
[![Image](https://img.shields.io/badge/ghcr.io-latest-blue)](https://github.com/CreedsCode/webzero-qr-redirect/pkgs/container/webzero-qr-redirect)

---

## What it does

You print QR codes for an event. When someone scans one, the server increments a counter and immediately redirects to the destination — no middleman UI, no account, no tracking.

```
scan QR → /get/luma → counter++ → 302 → luma.com/joinwebzero
```

Anyone can verify exactly where each QR leads before scanning. Anyone can check the live counts. Anyone can confirm the server code hasn't been tampered with.

---

## Current destinations

| Slug | Destination |
|------|-------------|
| `luma` | https://luma.com/joinwebzero |
| `zodl-android` | Zodl (Zcash wallet) on Google Play |
| `zodl-ios` | Zodl (Zcash wallet) on App Store |
| `cake-android` | Cake Wallet on Google Play |
| `cake-ios` | Cake Wallet on App Store |

To add a destination for a new event: add one line to `DESTINATIONS` in `server.py`, redeploy, and run `generate_qr.py`.

---

## Features

- **Zero PII collected** — no IP addresses, no User-Agent strings, no cookies, no timestamps, ever
- **No open redirect** — only hardcoded destinations can be reached; unknown slugs return 404
- **Publicly verifiable** — `/destinations` lists every URL the server can redirect to; `/integrity` exposes the SHA-256 of the running code
- **Signed Docker images** — every build is signed with cosign and recorded in the [Rekor](https://rekor.sigstore.dev) public transparency log
- **QR code generator** — generates print-ready PNG and SVG QR codes in one command; generate all slugs or just the ones you need
- **Event-ready** — add any new slug + URL for each activation, generate QRs, deploy once

---

## Quick Start

### Run with Docker (recommended)

```bash
docker run -p 8000:8000 -v webzero-data:/app/data \
  ghcr.io/creescode/webzero-qr-redirect:latest
```

Counts persist in the `webzero-data` volume across restarts.

### Run locally

```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --no-access-log
```

> `--no-access-log` is required — without it uvicorn logs IP addresses.

---

## Generate QR codes

```bash
# All slugs
python generate_qr.py --base-url https://qr.joinwebzero.com

# Just the slugs you need for this event
python generate_qr.py --base-url https://qr.joinwebzero.com --slugs luma zodl-android
```

Output per slug: `qr/<slug>.png` and `qr/<slug>.svg`. Use SVG for print.

---

## Adding a new event

1. Add an entry to `DESTINATIONS` in `server.py`:
   ```python
   "my-event": "https://lu.ma/my-event-page",
   ```
2. Add the same slug to `DEFAULT_SLUGS` in `generate_qr.py`
3. Redeploy (`git push` triggers the GitHub Actions build)
4. Generate QR codes:
   ```bash
   python generate_qr.py --base-url https://qr.joinwebzero.com --slugs my-event
   ```

---

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /get/{slug}` | Increments counter and redirects. Returns 404 for unknown slugs. |
| `GET /stats` | JSON object with cumulative redirect counts per slug. |
| `GET /destinations` | JSON object mapping slugs to their hardcoded destination URLs. |
| `GET /integrity` | SHA-256 of the running `server.py` and the git commit it was built from. |
| `GET /health` | `{"status": "ok"}` |

---

## Verification

### Verify the running code matches the source

```bash
./verify.sh https://qr.joinwebzero.com
```

1. Fetches `/integrity` — gets the SHA-256 of the running `server.py` and the git commit SHA
2. Downloads `server.py` at that commit from GitHub and hashes it locally
3. Compares — they must match

### Verify the Docker image

```bash
./verify.sh https://qr.joinwebzero.com --image
```

Also verifies the image signature in Rekor, confirming it was built by GitHub Actions from this repo.

<details>
<summary>Manual steps (no script)</summary>

```bash
# 1. Get the running server's hash
curl https://qr.joinwebzero.com/integrity | jq .

# 2. Hash the source at that commit yourself
GIT_SHA=<git_commit from above>
curl -s "https://raw.githubusercontent.com/CreedsCode/webzero-qr-redirect/${GIT_SHA}/server.py" | sha256sum

# 3. The two SHA-256 values must match.
```

</details>

---

## Deployment

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COUNTS_FILE` | `counts.json` | Path to JSON file storing counts. Mount a volume here. |
| `GIT_SHA` | `unknown` | Injected automatically by GitHub Actions. |

### Docker Compose

```yaml
services:
  webzero-qr:
    image: ghcr.io/creescode/webzero-qr-redirect:latest
    ports:
      - "8000:8000"
    volumes:
      - webzero-data:/app/data

volumes:
  webzero-data:
```

---

## What this server does NOT do

- Log IP addresses
- Log User-Agent strings
- Log timestamps of individual requests
- Set cookies
- Use device detection or fingerprinting
- Phone home to any third party

These aren't configurable options — they're architectural properties of the code. Read `server.py` and verify yourself.

---

## Security considerations

This server eliminates server-side tracking. It does not eliminate all attack vectors. Know what remains.

### Residual attack vectors

| Vector | Risk | Mitigation |
|--------|------|------------|
| **QR sticker swap** | Attacker places a sticker QR over the legitimate one, redirecting to a phishing or malicious URL | Physical inspection before and during every event (see below) |
| **DNS hijack** | `qr.joinwebzero.com` resolves to a different server running different code | Run `./verify.sh https://qr.joinwebzero.com` to confirm the live code matches this repo |
| **HTTPS stripping** | QR encodes `http://` instead of `https://`, enabling MITM | QR codes must always encode `https://`. Verify with any QR reader before printing. |
| **Compromised image** | The deployed Docker image was tampered with after signing | Verify the image signature: `./verify.sh https://qr.joinwebzero.com --image` |
| **Destination drift** | A hardcoded URL (e.g. an app store link) later redirects somewhere unexpected | Spot-check `/destinations` before each event and follow each URL manually |
| **Printed URL mismatch** | The human-readable URL printed under the QR doesn't match what the QR actually encodes | Scan every printed QR with an independent reader and confirm the encoded URL matches the label |

### Physical QR code verification protocol

QR sticker swaps are a real attack. They require no technical skill and are effective because most people scan without thinking. Treat printed QR codes as a physical security surface.

**Before the event (print check):**
- [ ] Scan every printed QR code with an independent reader
- [ ] Confirm the encoded URL is `https://qr.joinwebzero.com/get/<slug>` — not an IP address, not HTTP, not a URL shortener
- [ ] Confirm the human-readable label under the QR matches the encoded URL
- [ ] Visit `https://qr.joinwebzero.com/destinations` and confirm every slug maps to a known, legitimate URL

**At the venue (staff check-in):**
- [ ] Inspect all printed QR codes and standees for stickers or physical damage before doors open
- [ ] Re-scan any QR that looks slightly different from the others (different finish, slightly raised surface, color shift)
- [ ] Assign one staff member to do a sweep if the venue is large

**During the event (ongoing):**
- [ ] Staff should do a visual pass every 60–90 minutes, especially for high-traffic QR placements
- [ ] If a QR is found tampered with: remove it immediately, do not replace it on the spot without re-verifying

**For guests — what to tell them:**

> "Before you scan, check that the URL encoded in the QR starts with `https://qr.joinwebzero.com`. You can verify where it leads at `qr.joinwebzero.com/destinations` before visiting."

The `/destinations` endpoint exists precisely so guests don't have to trust the QR or the staff — they can verify the server's behavior themselves.

---

## License

MIT
