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
from fastapi.responses import RedirectResponse, JSONResponse
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

    # Zcash wallets
    "zodl-android": "https://play.google.com/store/apps/details?id=co.electriccoin.android",
    "zodl-ios":     "https://apps.apple.com/app/zashi-zcash-wallet/id1672423317",
    "cake-android": "https://play.google.com/store/apps/details?id=com.cakewallet.cake_wallet",
    "cake-ios":     "https://apps.apple.com/app/cake-wallet-xmr-monero/id1334702542",
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
        ghcr.io/CreedsCode/webzero-qr-redirect:latest
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
            " ghcr.io/CreedsCode/webzero-qr-redirect:latest"
        ),
        "rekor_transparency_log": "https://rekor.sigstore.dev",
    })


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
