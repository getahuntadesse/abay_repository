# Security Remediation Report — Abay Repository / Abrehot Library

**Reference:** Ethio telecom Security Assessment Report (12 September 2026)  
**Target:** https://abay.abrehot.org.et  
**Remediation package:** Application code + operational runbook  

This document maps **every** assessment finding to a concrete fix. Application issues are fixed in code. Infrastructure issues (SSH) require actions on the host; exact commands are included below.

---

## Executive status

| ID | Finding | Severity | Remediation |
|----|---------|----------|-------------|
| 6.1 | Stored XSS | Critical | **Code fixed** + media purge + CSP |
| 6.2 | Unrestricted file upload | High | **Code fixed** (magic bytes + whitelist) |
| 6.3 | Weak Django admin credentials | Critical | **Obfuscated admin URL**, IP allowlist, password rotation, 2FA |
| 6.4 | Auth brute-force not enforced | High | **Code fixed** (IP + username lockout 15 min) + Nginx rate limit sample |
| 6.5 | Internet-exposed SSH | High | **Ops runbook** (firewall / VPN) |
| 6.6 | Outdated OpenSSH | High | **Ops runbook** (vendor upgrade) |

---

## 6.1 Stored XSS (Critical) — FIXED

### Problem
Authors uploaded SVG/HTML under `/media/`; browsers executed scripts in the site origin.

### Application controls
1. **Cover images:** only `.jpg` / `.jpeg` / `.png`  
   - Extension check  
   - Magic-byte signature (`FF D8 FF` / `89 PNG`)  
   - `imghdr` confirmation  
   - Explicit block of `.svg`, `.html`, scripts  
2. **Manuscripts:** only `.pdf` / `.epub` with magic bytes (`%PDF`, ZIP)  
3. **Model validators** on `Book.file`, `cover_image`, `sample_file`  
4. **`/media/` responses:**  
   - `Content-Security-Policy: default-src 'none'; sandbox`  
   - `X-Content-Type-Options: nosniff`  
   - HTML/SVG content types forced to download / blocked  
5. **Secure media view** refuses blocked extensions even if files exist on disk  

### Files
- `books/utils/secure_upload.py`  
- `books/views.py` (`upload_book`, `edit_book`, revision submit)  
- `books/models.py` (validators)  
- `core/middleware.py`  
- `config/views.py` (`secure_media_serve`)  

### One-time cleanup (required)

```bash
python manage.py purge_dangerous_media --dry-run
python manage.py purge_dangerous_media
```

---

## 6.2 Unrestricted file upload (High) — FIXED

### Problem
Server trusted client Content-Type and extension only; HTML/PHP could be stored and served.

### Application controls
- Server-side **magic-byte** validation (never trust client MIME)  
- Strict extension whitelist  
- Malicious content pattern scan in file head  
- Filename sanitization (no path traversal)  
- Size limits: book ≤ 50 MB, cover ≤ 5 MB  
- Settings: `ALLOWED_UPLOAD_EXTENSIONS`, `ALLOWED_UPLOAD_MIME_TYPES`  

Same code paths as 6.1 for upload, edit, and revision.

---

## 6.3 Weak credentials on Django admin (Critical) — FIXED + OPS

### Problem
Public `/admin/` with weak password → full takeover.

### Application controls
1. Admin moved off `/admin/` to configurable path:

```env
ADMIN_URL_PATH=secure-abay-admin
```

Use a **long random** value in production, e.g. `admin-xK9mQ2pL7wR4`.

2. Requests to `/admin/` **do not** load Django admin (redirect/404).  
3. Optional IP allowlist:

```env
ADMIN_ALLOWED_IPS=196.188.10.5,10.0.0.8
```

4. Access attempts logged by `AdminPathSecurityMiddleware`.  
5. Existing **email 2FA** should be enabled for all staff accounts.

### Mandatory operational steps

```bash
# 1. Set unique path in .env and restart
# 2. Rotate password
python manage.py changepassword <admin_username>
# 3. Enable 2FA in the account security settings
# 4. Confirm /admin/ is dead and only /<ADMIN_URL_PATH>/ works
```

Password policy already requires ≥10 characters, upper/lower, digit, special (see `core/validators.py`).

---

## 6.4 Authentication brute-force (High) — FIXED

### Problem
Unlimited password attempts on `/accounts/login/`.

### Application controls
- Max attempts: **5** (configurable `LOGIN_MAX_ATTEMPTS`)  
- Lockout duration: **900 seconds (15 min)** (`LOGIN_LOCKOUT_SECONDS`)  
- Counters: **per IP** and **per username**  
- Existing IP block after repeated abuse  

### Nginx (recommended)

See `deploy/nginx_abay_security.conf.sample` — `limit_req` on `/accounts/login/`.

### MFA
Keep 2FA enabled for admin, finance, maker, checker roles.

---

## 6.5 Internet-exposed SSH (High) — OPERATIONS

### Problem
TCP/22 open to the Internet.

### Required host actions (not Django)

```bash
# Ubuntu UFW example — replace with your office/VPN IP
sudo ufw allow from YOUR.TRUSTED.IP.ADDRESS to any port 22 proto tcp
sudo ufw deny 22/tcp
sudo ufw reload
sudo ufw status

# Or cloud security group: allow 22 only from admin IPs
```

Prefer **VPN or bastion**; disable public SSH if not needed.  
Use **key-based auth**, disable password authentication in `sshd_config`:

```
PasswordAuthentication no
PermitRootLogin no
```

---

## 6.6 Outdated OpenSSH (High) — OPERATIONS

### Problem
OpenSSH 8.9p1 reported; keep vendor-supported packages current.

```bash
sudo apt update
sudo apt install --only-upgrade openssh-server openssh-client
ssh -V
# Reboot if kernel/security updates require it
```

Subscribe to Ubuntu security notices for the server release.

---

## Deploy checklist

1. Deploy this code package to production.  
2. Update `.env`:

```env
DEBUG=False
ADMIN_URL_PATH=<long-random-secret>
ADMIN_ALLOWED_IPS=<optional-comma-ips>
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCKOUT_SECONDS=900
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
```

3. `python manage.py purge_dangerous_media`  
4. Rotate admin passwords + enable 2FA  
5. Apply Nginx sample rules  
6. Restrict SSH (6.5) and upgrade OpenSSH (6.6)  
7. Restart Gunicorn + Nginx  

### Verification

| Test | Expected |
|------|----------|
| Upload cover `.svg` / `.html` | Rejected |
| Upload book `.php` renamed | Rejected (magic bytes) |
| Open `/admin/` | Not Django admin |
| Open `/<ADMIN_URL_PATH>/` | Admin (after auth) |
| 6 wrong passwords | Locked ~15 minutes |
| `nmap` port 22 from internet | Filtered/closed for untrusted IPs |

---

## Files in this remediation

| Path | Role |
|------|------|
| `books/utils/secure_upload.py` | Magic-byte validators |
| `books/views.py` | Upload/edit/revision validation |
| `books/models.py` | Field validators |
| `books/management/commands/purge_dangerous_media.py` | Cleanup command |
| `core/middleware.py` | Media CSP / nosniff |
| `config/views.py` | Secure media serve |
| `config/urls.py` | Admin path + media route |
| `config/settings.py` | Whitelist, admin path, lockout |
| `config/admin_security.py` | Admin IP allowlist middleware |
| `accounts/views.py` | Login lockout |
| `deploy/nginx_abay_security.conf.sample` | Edge hardening |
| `SECURITY_UPDATE_README.md` | This document |

---

## Residual risk

- SSH and OpenSSH require **server operator** action; application code cannot close port 22.  
- Payment flows were out of scope of the original assessment; keep Telebirr credentials and HTTPS notify URLs locked down.  
- Schedule retest with Ethio telecom after deployment to close findings formally.
