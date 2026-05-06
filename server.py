"""
WebZero event activation QR redirect counter.

What this server does:
  - Receives a request at /get/<slug>
  - Increments an in-memory + file-backed counter by 1
  - Immediately 302-redirects to the configured destination URL
  - Returns

What this server does NOT do:
  - Log IP addresses
  - Log User-Agent strings
  - Log timestamps of individual requests
  - Set cookies
  - Use device detection
  - Phone home anywhere

Verifiable: /destinations shows exactly where each route redirects.
Source code: https://github.com/CreedsCode/webzero-qr-redirect (publish this)

To add a new event/destination: add an entry to DESTINATIONS below,
redeploy, and generate new QR codes with generate_qr.py.
"""

import hashlib
import json
import os
import threading
from pathlib import Path

# Hash server.py at import time (before any request can trigger a swap attack).
# This is what /integrity returns — not a runtime re-hash.
_SOURCE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# DESTINATIONS — hardcoded whitelist. No open redirect possible.
#
# Add new event slugs here. Each slug becomes a /get/<slug> route.
# Verify all URLs are correct before deploying.
#
# Community / events:
#   WebZero Luma: https://luma.com/joinwebzero
#
# Zcash wallets:
#   Zodl (formerly Zashi): https://zodl.com
#   Cake Wallet:           https://cakewallet.com
# ---------------------------------------------------------------------------
DESTINATIONS: dict[str, str] = {
    # WebZero community
    "luma":         "https://luma.com/joinwebzero",
    "intern":       "https://www.youtube.com/watch?v=iik25wqIuFo&pp=ygUbcmljayByb2xsIGJ1dCBkaWZmZXJlbnQgdXJs",

    # Zodl (Zcash wallet)
    "zodl":         "https://zodl.com/download/",
    "zodl-ios":     "https://apps.apple.com/us/app/zodl-zcash-wallet/id1672392439",
    "zodl-android": "https://play.google.com/store/apps/details?id=co.electriccoin.zcash&hl=en-US&pli=1",
    "zodl-fdroid":  "https://f-droid.org/en/packages/co.electriccoin.zcash.foss/",

    # Cake Wallet
    "cake-ios":     "https://apps.apple.com/us/app/cake-wallet/id1334702542",
    "cake-android": "https://play.google.com/store/apps/details?id=com.cakewallet.cake_wallet",
    "cake-apk":     "https://github.com/cake-tech/cake_wallet/releases",
}

# ---------------------------------------------------------------------------
# Counter storage — one JSON file, one integer per destination.
# Replace with Redis or SQLite if you want persistence across restarts
# without relying on the filesystem (e.g. on Fly.io, Railway, etc.)
# ---------------------------------------------------------------------------
COUNTS_FILE = Path(os.environ.get("COUNTS_FILE", "counts.json"))
_lock = threading.Lock()


def _load() -> dict[str, int]:
    if COUNTS_FILE.exists():
        return json.loads(COUNTS_FILE.read_text())
    return {k: 0 for k in DESTINATIONS}


def _increment(key: str) -> None:
    with _lock:
        counts = _load()
        counts[key] = counts.get(key, 0) + 1
        COUNTS_FILE.write_text(json.dumps(counts, indent=2))


# ---------------------------------------------------------------------------
# App — no logging middleware added intentionally
# ---------------------------------------------------------------------------
app = FastAPI(
    title="WebZero QR Redirect Counter",
    description="Privacy-preserving event activation redirect counter. No PII collected.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # stats endpoint is public
    allow_methods=["GET"],
    allow_headers=[],
)

# Disable uvicorn's default access log by running with --no-access-log
# (see run instructions in README)


@app.get(
    "/get/{wallet}",
    summary="Redirect to official app store listing and count the referral",
    response_description="302 redirect to official app store URL",
)
def get_wallet(wallet: str) -> Response:
    """
    Increments the counter for `wallet` by 1, then redirects.
    Unknown wallet names return 404 — no open redirect.
    """
    if wallet not in DESTINATIONS:
        return Response(status_code=404, content=f"Unknown wallet: {wallet!r}")
    _increment(wallet)
    return RedirectResponse(url=DESTINATIONS[wallet], status_code=302)


@app.get(
    "/stats",
    summary="Public referral counts",
)
def stats() -> JSONResponse:
    """Returns total redirect counts per wallet. No PII exposed."""
    return JSONResponse(_load())


@app.get(
    "/destinations",
    summary="Publicly verify where each route redirects",
)
def destinations() -> JSONResponse:
    """
    Anyone can call this before scanning a QR to confirm the server
    will redirect to a legitimate, official app store URL.
    No trust required — read the source and verify yourself.
    """
    return JSONResponse(DESTINATIONS)


@app.get(
    "/integrity",
    summary="Verify the running code matches the published source",
)
def integrity() -> JSONResponse:
    """
    Returns the SHA-256 of the running server.py and the git commit it was
    built from. Cross-check against the GitHub repo to confirm no tampering.

    Steps to verify:
      1. curl https://qr.joinwebzero.com/integrity
      2. curl -s https://raw.githubusercontent.com/CreedsCode/webzero-qr-redirect/<git_sha>/server.py | sha256sum
      3. The hashes must match.

    For Docker image verification (stronger — uses Rekor transparency log):
      cosign verify \\
        --certificate-identity-regexp="https://github.com/CreedsCode/webzero-qr-redirect/.*" \\
        --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \\
        ghcr.io/creedscode/webzero-qr-redirect:latest
    """
    sha256 = _SOURCE_HASH
    git_sha = os.environ.get("GIT_SHA", "unknown")

    repo = "https://github.com/CreedsCode/webzero-qr-redirect"  # update before deploying

    return JSONResponse({
        "server_py_sha256": sha256,
        "git_commit": git_sha,
        "source_url": f"{repo}/blob/{git_sha}/server.py",
        "raw_url": f"https://raw.githubusercontent.com/CreedsCode/webzero-qr-redirect/{git_sha}/server.py",
        "verify_hash_command": (
            f"curl -s https://raw.githubusercontent.com/CreedsCode/webzero-qr-redirect/{git_sha}/server.py"
            f" | sha256sum  # must equal {sha256[:16]}..."
        ),
        "verify_image_command": (
            "cosign verify"
            " --certificate-identity-regexp='https://github.com/CreedsCode/webzero-qr-redirect/.*'"
            " --certificate-oidc-issuer='https://token.actions.githubusercontent.com'"
            " ghcr.io/creedscode/webzero-qr-redirect:latest"
        ),
        "rekor_transparency_log": "https://rekor.sigstore.dev",
    })


_ZODL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Download Zodl — Zcash Wallet</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0a0a0a;
      color: #f0f0f0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }
    .card {
      background: #141414;
      border: 1px solid #2a2a2a;
      border-radius: 1.25rem;
      padding: 2.5rem 2rem;
      max-width: 420px;
      width: 100%;
      text-align: center;
    }
    .logo { font-size: 2.5rem; margin-bottom: 0.5rem; }
    h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }
    p  { color: #9a9a9a; font-size: 0.95rem; margin-bottom: 2rem; line-height: 1.5; }
    .btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      width: 100%;
      padding: 0.9rem 1.25rem;
      border-radius: 0.75rem;
      font-size: 1rem;
      font-weight: 600;
      text-decoration: none;
      color: #fff;
      margin-bottom: 0.875rem;
      transition: opacity 0.15s;
    }
    .btn:hover { opacity: 0.88; }
    .btn-ios     { background: #1c1c1e; border: 1px solid #3a3a3c; }
    .btn-android { background: #1a2a1a; border: 1px solid #2d4a2d; }
    .btn-fdroid  { background: #1a1a2a; border: 1px solid #2d2d4a; }
    .btn svg { flex-shrink: 0; width: 1.4rem; height: 1.4rem; }
    .footer { margin-top: 1.75rem; font-size: 0.8rem; color: #555; }
    .footer a { color: #777; text-decoration: none; }
    .footer a:hover { color: #aaa; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo" aria-label="Zodl">🔵</div>
    <h1>Get Zodl</h1>
    <p>The privacy-first Zcash wallet.<br>Choose your platform below.</p>

    <a class="btn btn-ios"
       href="/get/zodl-ios"
       rel="noopener noreferrer">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
      </svg>
      App Store (iOS)
    </a>

    <a class="btn btn-android"
       href="/get/zodl-android"
       rel="noopener noreferrer">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M17.523 15.341A7.021 7.021 0 0 0 19 11a7 7 0 0 0-14 0 7.021 7.021 0 0 0 1.477 4.341L5 21h14l-1.477-5.659zM12 6a5 5 0 1 1 0 10A5 5 0 0 1 12 6zm-1 3v2H9l3 4 3-4h-2V9h-2z"/>
      </svg>
      Google Play (Android)
    </a>

    <a class="btn btn-fdroid"
       href="/get/zodl-fdroid"
       rel="noopener noreferrer">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/>
      </svg>
      F-Droid (Android FOSS)
    </a>

    <div class="footer">
      Redirects tracked anonymously &mdash; no PII collected.<br>
      <a href="/destinations">Verify destinations</a> · <a href="/integrity">Verify code</a>
    </div>
  </div>
</body>
</html>"""


@app.get(
    "/zodl",
    summary="Zodl download page — links to iOS, Android, and F-Droid",
    response_class=HTMLResponse,
)
def zodl_download() -> HTMLResponse:
    """Serves a simple HTML page with download links for both Zodl app platforms."""
    return HTMLResponse(content=_ZODL_HTML)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
