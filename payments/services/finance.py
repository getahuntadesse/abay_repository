"""Finance settings + report generation (officer-configurable rates)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.db.models import Count, Q, Sum
from django.utils import timezone


def get_finance_settings():
    from payments.models import FinanceSettings
    return FinanceSettings.get_solo()


def tax_rate_for_book(book, fin=None) -> Decimal:
    fin = fin or get_finance_settings()
    genre = ""
    try:
        if book and getattr(book, "genre", None):
            genre = (book.genre.name or "").lower()
    except Exception:
        genre = ""
    keywords = fin.genre_keywords()
    if genre and any(k in genre for k in keywords):
        return Decimal(str(fin.tax_rate_culture))
    return Decimal(str(fin.tax_rate_default))


def compute_royalty_breakdown(gross_amount, book=None, fin=None) -> Dict[str, Any]:
    """Compute royalty / platform / tax / net from current FinanceSettings."""
    fin = fin or get_finance_settings()
    gross = Decimal(str(gross_amount or 0))
    royalty_rate = Decimal(str(fin.royalty_rate))
    platform_rate = Decimal("100.00") - royalty_rate
    author_royalty = (gross * royalty_rate / Decimal("100")).quantize(Decimal("0.01"))
    platform_share = (gross * platform_rate / Decimal("100")).quantize(Decimal("0.01"))
    tax_rate = tax_rate_for_book(book, fin) if book is not None else Decimal(str(fin.tax_rate_default))
    threshold = Decimal(str(fin.tax_threshold))
    is_taxable = author_royalty >= threshold
    tax_amount = (author_royalty * tax_rate / Decimal("100")).quantize(Decimal("0.01")) if is_taxable else Decimal("0.00")
    final_amount = (author_royalty - tax_amount).quantize(Decimal("0.01"))
    return {
        "gross_amount": gross,
        "royalty_rate": royalty_rate,
        "platform_rate": platform_rate,
        "author_royalty": author_royalty,
        "abrehot_share": platform_share,
        "abrehot_share_rate": platform_rate,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "is_taxable": is_taxable,
        "final_amount": final_amount,
        "tax_threshold": threshold,
    }


def _period_bounds(period_type: str, ref: Optional[date] = None) -> Tuple[date, date, str]:
    ref = ref or timezone.localdate()
    if period_type == "weekly":
        start = ref - timedelta(days=ref.weekday())  # Monday
        end = start + timedelta(days=6)
        title = f"Weekly report {start.isoformat()} – {end.isoformat()}"
    elif period_type == "monthly":
        start = ref.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
        title = f"Monthly report {start.strftime('%B %Y')}"
    elif period_type == "annual":
        start = ref.replace(month=1, day=1)
        end = ref.replace(month=12, day=31)
        title = f"Annual report {start.year}"
    else:
        start = ref.replace(day=1)
        end = ref
        title = f"Custom report {start} – {end}"
    return start, end, title


def generate_finance_report(
    period_type: str,
    user=None,
    ref_date: Optional[date] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
):
    """Build and persist a FinanceReport for the given period."""
    from payments.models import FinanceReport, Payment, Purchase

    fin = get_finance_settings()
    if start and end:
        period_start, period_end = start, end
        title = f"{period_type.title()} report {period_start} – {period_end}"
    else:
        period_start, period_end, title = _period_bounds(period_type, ref_date)

    # Inclusive end-of-day
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(period_end, datetime.max.time()), tz)

    purchases = Purchase.objects.filter(
        status="completed",
        completed_at__gte=start_dt,
        completed_at__lte=end_dt,
    )
    payments = Payment.objects.filter(
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    )

    total_gross = purchases.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
    total_royalty = payments.aggregate(t=Sum("author_royalty"))["t"] or Decimal("0.00")
    total_platform = payments.aggregate(t=Sum("abrehot_share"))["t"] or Decimal("0.00")
    total_tax = payments.aggregate(t=Sum("tax_amount"))["t"] or Decimal("0.00")
    total_net = payments.aggregate(t=Sum("final_amount"))["t"] or Decimal("0.00")
    total_paid = payments.filter(status="paid").aggregate(t=Sum("final_amount"))["t"] or Decimal("0.00")
    total_pending = payments.filter(status__in=["calculated", "pending"]).aggregate(
        t=Sum("final_amount")
    )["t"] or Decimal("0.00")

    author_rows = list(
        payments.values("author_id", "author__username", "author__email")
        .annotate(
            royalty=Sum("author_royalty"),
            tax=Sum("tax_amount"),
            net=Sum("final_amount"),
            count=Count("id"),
        )
        .order_by("-net")
    )
    for row in author_rows:
        for k in ("royalty", "tax", "net"):
            if row.get(k) is not None:
                row[k] = str(row[k])

    # Daily series of gross sales
    daily = {}
    for p in purchases.only("amount", "completed_at"):
        if not p.completed_at:
            continue
        d = timezone.localtime(p.completed_at).date().isoformat()
        daily[d] = str(Decimal(daily.get(d, "0")) + Decimal(str(p.amount)))

    report = FinanceReport.objects.create(
        period_type=period_type if period_type in ("weekly", "monthly", "annual", "custom") else "custom",
        period_start=period_start,
        period_end=period_end,
        title=title,
        total_gross=total_gross,
        total_royalty=total_royalty,
        total_platform=total_platform,
        total_tax=total_tax,
        total_net_authors=total_net,
        total_paid=total_paid,
        total_pending=total_pending,
        purchase_count=purchases.count(),
        payment_count=payments.count(),
        author_count=len(author_rows),
        royalty_rate_snapshot=fin.royalty_rate,
        platform_rate_snapshot=fin.platform_rate,
        tax_threshold_snapshot=fin.tax_threshold,
        details={
            "authors": author_rows,
            "daily_gross": daily,
            "rates": {
                "royalty_rate": str(fin.royalty_rate),
                "platform_rate": str(fin.platform_rate),
                "tax_rate_default": str(fin.tax_rate_default),
                "tax_rate_culture": str(fin.tax_rate_culture),
                "tax_threshold": str(fin.tax_threshold),
            },
        },
        generated_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return report



def notify_author_royalty_paid(author, total_amount, transaction_reference, payment_count=1):
    """In-app notification + email when royalty is recorded as paid."""
    import logging
    logger = logging.getLogger(__name__)
    total_s = str(total_amount)
    title = "Royalty payment recorded"
    message = (
        f"Your royalty payment of {total_s} ETB has been recorded by finance "
        f"({payment_count} payment row(s)). Reference: {transaction_reference}."
    )
    try:
        from notifications.models import Notification
        Notification.objects.create(
            user=author,
            type="success",
            title=title,
            message=message,
            link="/payments/author/",
        )
    except Exception as e:
        logger.warning("In-app notification failed: %s", e)
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        email = getattr(author, "email", None)
        if email:
            send_mail(
                subject=f"[Abay] {title}",
                message=message + "\n\nYou can review your payments in the author payments section.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None) or "noreply@abay.local",
                recipient_list=[email],
                fail_silently=True,
            )
    except Exception as e:
        logger.warning("Royalty email failed: %s", e)


def report_to_csv_bytes(report) -> bytes:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Finance Report", report.title or ""])
    w.writerow(["Period", f"{report.period_start} to {report.period_end}"])
    w.writerow(["Type", report.period_type])
    w.writerow([])
    w.writerow(["Metric", "Amount (ETB)"])
    w.writerow(["Gross sales", report.total_gross])
    w.writerow(["Author royalty", report.total_royalty])
    w.writerow(["Platform share", report.total_platform])
    w.writerow(["Tax withheld", report.total_tax])
    w.writerow(["Net to authors", report.total_net_authors])
    w.writerow(["Paid out", report.total_paid])
    w.writerow(["Pending", report.total_pending])
    w.writerow(["Purchases", report.purchase_count])
    w.writerow(["Authors", report.author_count])
    w.writerow([])
    w.writerow(["Author", "Payments", "Royalty", "Tax", "Net"])
    for a in (report.details or {}).get("authors") or []:
        w.writerow([
            a.get("author__username") or a.get("author_id"),
            a.get("count"),
            a.get("royalty"),
            a.get("tax"),
            a.get("net"),
        ])
    return buf.getvalue().encode("utf-8-sig")


def report_to_pdf_bytes(report) -> bytes:
    """Minimal single-page PDF without external deps."""
    lines = [
        report.title or "Finance Report",
        f"Period: {report.period_start} to {report.period_end} ({report.period_type})",
        "",
        f"Gross sales: {report.total_gross} ETB",
        f"Author royalty: {report.total_royalty} ETB",
        f"Platform share: {report.total_platform} ETB",
        f"Tax withheld: {report.total_tax} ETB",
        f"Net to authors: {report.total_net_authors} ETB",
        f"Paid out: {report.total_paid} ETB",
        f"Pending: {report.total_pending} ETB",
        f"Purchases: {report.purchase_count}  Authors: {report.author_count}",
        "",
        "By author:",
    ]
    for a in (report.details or {}).get("authors") or []:
        lines.append(
            f"  {a.get('author__username') or a.get('author_id')}: "
            f"net {a.get('net')} (royalty {a.get('royalty')}, tax {a.get('tax')})"
        )
    return _simple_pdf("\n".join(lines))


def _simple_pdf(text: str) -> bytes:
    # Very small PDF 1.4 text document
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    y = 800
    content_lines = ["BT", "/F1 11 Tf", "50 800 Td", "14 TL"]
    first = True
    for line in text.splitlines()[:60]:
        safe = esc(line[:110])
        if first:
            content_lines.append(f"({safe}) Tj")
            first = False
        else:
            content_lines.append(f"T* ({safe}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objs = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode() + stream + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for o in objs:
        offsets.append(len(out))
        out.extend(o)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)
