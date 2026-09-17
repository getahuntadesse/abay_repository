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
