"""
Generate a self-signed certificate for local HTTPS development.
Run once:  python scripts/generate_local_cert.py
Creates:   certs/localhost.crt  and  certs/localhost.key
"""
from pathlib import Path

try:
    from OpenSSL import crypto
except ImportError:
    raise SystemExit("Install pyOpenSSL first:  pip install pyOpenSSL")

ROOT = Path(__file__).resolve().parent.parent
CERT_DIR = ROOT / "certs"
CERT_DIR.mkdir(exist_ok=True)
KEY_PATH = CERT_DIR / "localhost.key"
CRT_PATH = CERT_DIR / "localhost.crt"

key = crypto.PKey()
key.generate_key(crypto.TYPE_RSA, 2048)

cert = crypto.X509()
cert.get_subject().CN = "localhost"
cert.get_subject().O = "Abay Local Dev"
cert.set_serial_number(1000)
cert.gmtime_adj_notBefore(0)
cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)
cert.set_issuer(cert.get_subject())
cert.set_pubkey(key)
cert.add_extensions([
    crypto.X509Extension(b"subjectAltName", False, b"DNS:localhost,IP:127.0.0.1"),
])
cert.sign(key, "sha256")

KEY_PATH.write_bytes(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
CRT_PATH.write_bytes(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

print("Created:")
print(" ", KEY_PATH)
print(" ", CRT_PATH)
print()
print("Run HTTPS server with:")
print("  python manage.py runserver_plus --cert-file certs/localhost.crt --key-file certs/localhost.key 127.0.0.1:8000")
print()
print("Then open:  https://127.0.0.1:8000/")
print("(Accept the browser warning for the self-signed cert.)")
