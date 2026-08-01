#!/usr/bin/env python3
"""Emit an alert only when Practenture TLS is near expiry or invalid."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import socket
import ssl


def verified_context() -> ssl.SSLContext:
    default_paths = ssl.get_default_verify_paths()
    if default_paths.cafile or default_paths.capath:
        return ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def certificate_expiry(hostname: str, port: int, timeout: float) -> datetime:
    context = verified_context()
    with socket.create_connection((hostname, port), timeout=timeout) as connection:
        with context.wrap_socket(connection, server_hostname=hostname) as tls_socket:
            certificate = tls_socket.getpeercert()
    if not certificate:
        raise RuntimeError("the server did not provide a verifiable certificate")
    not_after = certificate.get("notAfter")
    if not isinstance(not_after, str):
        raise RuntimeError("the server certificate did not include notAfter")
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), tz=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", default="practenture.com")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--warn-days", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    try:
        expiry = certificate_expiry(args.hostname, args.port, args.timeout)
        remaining_seconds = (expiry - datetime.now(timezone.utc)).total_seconds()
        remaining_days = remaining_seconds / 86_400
        if remaining_days <= args.warn_days:
            print(
                f"TLS ALERT: {args.hostname} expires at {expiry.isoformat()} "
                f"({remaining_days:.1f} days remaining). Verify Certbot renewal and "
                "the certificate served by Nginx now."
            )
    except Exception as exc:
        print(
            f"TLS ALERT: could not validate {args.hostname}:{args.port}: "
            f"{type(exc).__name__}: {exc}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
