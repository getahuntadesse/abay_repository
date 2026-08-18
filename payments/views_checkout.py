"""
Production checkout views.
Creates Purchase + gateway order and returns complete checkOutUrl for frontend.
"""
import json
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from books.models import Book
from .models import Purchase, Payment
from .services import TelebirrService, ChapaService, PayPalService

logger = logging.getLogger("payments")


def _create_author_payment(purchase: Purchase):
    """Create royalty Payment record after successful purchase (unchanged business logic)."""
    try:
        book = purchase.book
        author = book.author
        gross = purchase.amount
        royalty_rate = Decimal(str(getattr(settings, "ROYALTY_RATE", 70)))
        abrehot_rate = Decimal("100") - royalty_rate
        author_royalty = (gross * royalty_rate / Decimal("100")).quantize(Decimal("0.01"))
        abrehot_share = (gross * abrehot_rate / Decimal("100")).quantize(Decimal("0.01"))

        tax_rate = Decimal("10")
        culture_genres = {
            "culture", "cultural", "history", "heritage", "tradition",
            "ethiopian", "amharic", "oromo", "tigrinya", "literature", "poetry",
        }
        genre = (getattr(book, "genre", "") or "").lower()
        if any(g in genre for g in culture_genres):
            tax_rate = Decimal("5")

        tax_threshold = Decimal(str(getattr(settings, "TAX_THRESHOLD", 500)))
        tax_amount = Decimal("0.00")
        is_taxable = False
        if author_royalty >= tax_threshold:
            is_taxable = True
            tax_amount = (author_royalty * tax_rate / Decimal("100")).quantize(Decimal("0.01"))

        final_amount = author_royalty - tax_amount
        Payment.objects.create(
            book=book,
            author=author,
            purchase=purchase,
            gross_amount=gross,
            author_royalty=author_royalty,
            abrehot_share=abrehot_share,
            abrehot_share_rate=abrehot_rate,
            royalty_rate=royalty_rate,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            is_taxable=is_taxable,
            final_amount=final_amount,
            status="calculated",
        )
    except Exception as e:
        logger.exception("Author payment creation failed: %s", e)


@login_required
@require_POST
def create_order(request):
    """
    Unified create-order endpoint.
    Frontend posts: { book_id, payment_method, phone_number? }
    Backend returns: { success, checkOutUrl, merch_order_id / reference }
    Frontend opens checkOutUrl (target=_blank or same window).
    """
    try:
        if request.content_type and "application/json" in request.content_type:
            body = json.loads(request.body.decode() or "{}")
        else:
            body = request.POST

        book_id = body.get("book_id") or body.get("bookId")
        payment_method = (body.get("payment_method") or body.get("paymentMethod") or "telebirr").lower()
        phone = body.get("phone_number") or body.get("phone") or getattr(request.user, "phone", "") or ""

        if not book_id:
            return JsonResponse({"success": False, "error": "book_id required"}, status=400)

        book = get_object_or_404(Book, id=book_id, status="published")
        user = request.user

        if Purchase.objects.filter(user=user, book=book, status="completed").exists():
            return JsonResponse({"success": False, "error": "You already own this book."}, status=400)

        amount = book.price if book.price and book.price > 0 else Decimal("0.00")

        # Free book – complete immediately
        if amount == Decimal("0.00"):
            purchase = Purchase.objects.create(
                user=user,
                book=book,
                amount=amount,
                status="completed",
                payment_method=payment_method,
                completed_at=timezone.now(),
                transaction_reference="FREE-READ",
                purchase_reference="FREE-READ",
            )
            _create_author_payment(purchase)
            return JsonResponse({
                "success": True,
                "free": True,
                "message": "Book unlocked",
                "read_url": f"/books/{book.id}/read/",
            })

        merch_order_id = f"ABY{uuid.uuid4().hex[:14].upper()}"
        purchase = Purchase.objects.create(
            user=user,
            book=book,
            amount=amount,
            status="pending",
            payment_method=payment_method,
            transaction_reference=merch_order_id,
            purchase_reference=merch_order_id,
        )

        title = f"Book: {book.title}"[:120]
        base = getattr(settings, "BASE_URL", "").rstrip("/")

        if payment_method == "telebirr":
            svc = TelebirrService()
            ok, result = svc.create_order(
                title=title,
                amount=str(amount),
                merch_order_id=merch_order_id,
                notify_url=f"{base}/payments/telebirr/notify/",
                return_url=f"{base}/payments/return/?ref={merch_order_id}",
            )
            if not ok:
                purchase.status = "failed"
                purchase.save(update_fields=["status"])
                return JsonResponse({"success": False, "error": result.get("error", "Telebirr error")}, status=400)
            return JsonResponse({
                "success": True,
                "checkOutUrl": result["checkOutUrl"],
                "merch_order_id": merch_order_id,
                "payment_method": "telebirr",
            })

        if payment_method == "chapa":
            svc = ChapaService()
            first = getattr(user, "first_name", "") or user.username
            last = getattr(user, "last_name", "") or ""
            email = getattr(user, "email", "") or f"{user.username}@abay.local"
            ok, result = svc.initialize(
                amount=str(amount),
                email=email,
                first_name=first,
                last_name=last,
                phone=phone,
                tx_ref=merch_order_id,
                title="Abay Book",
                description=title,
                callback_url=f"{base}/payments/chapa/callback/",
                return_url=f"{base}/payments/return/?ref={merch_order_id}",
            )
            if not ok:
                purchase.status = "failed"
                purchase.save(update_fields=["status"])
                return JsonResponse({"success": False, "error": result.get("error", "Chapa error")}, status=400)
            return JsonResponse({
                "success": True,
                "checkOutUrl": result["checkOutUrl"],
                "merch_order_id": merch_order_id,
                "payment_method": "chapa",
            })

        if payment_method == "paypal":
            svc = PayPalService()
            ok, result = svc.create_order(
                amount=str(amount),
                description=title,
                custom_id=merch_order_id,
                return_url=f"{base}/payments/paypal/return/?ref={merch_order_id}",
                cancel_url=f"{base}/payments/return/?ref={merch_order_id}&cancelled=1",
            )
            if not ok:
                purchase.status = "failed"
                purchase.save(update_fields=["status"])
                return JsonResponse({"success": False, "error": result.get("error", "PayPal error")}, status=400)
            # store PayPal order id for capture
            purchase.transaction_id = result.get("order_id") or purchase.transaction_id
            purchase.save(update_fields=["transaction_id"])
            return JsonResponse({
                "success": True,
                "checkOutUrl": result["checkOutUrl"],
                "merch_order_id": merch_order_id,
                "payment_method": "paypal",
            })

        purchase.status = "failed"
        purchase.save(update_fields=["status"])
        return JsonResponse({"success": False, "error": f"Unsupported payment_method: {payment_method}"}, status=400)

    except Exception as e:
        logger.exception("create_order error")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def telebirr_notify(request):
    """Async payment notification from Telebirr SuperApp."""
    try:
        payload = json.loads(request.body.decode() or "{}")
    except Exception:
        payload = request.POST.dict()

    logger.info("Telebirr notify: %s", payload)
    svc = TelebirrService()
    if not svc.verify_notify(payload):
        logger.warning("Invalid Telebirr notify signature")
        return HttpResponse("INVALID SIGNATURE", status=400)

    merch_order_id = payload.get("merch_order_id")
    trade_status = (payload.get("trade_status") or "").lower()
    if not merch_order_id:
        return HttpResponse("MISSING ORDER", status=400)

    try:
        purchase = Purchase.objects.get(purchase_reference=merch_order_id)
    except Purchase.DoesNotExist:
        logger.error("Purchase not found for %s", merch_order_id)
        return HttpResponse("ORDER NOT FOUND", status=404)

    if purchase.status == "completed":
        return HttpResponse("OK")

    if trade_status in ("completed", "pay_success", "success"):
        purchase.status = "completed"
        purchase.completed_at = timezone.now()
        purchase.transaction_reference = payload.get("payment_order_id") or payload.get("trans_id") or merch_order_id
        purchase.save()
        _create_author_payment(purchase)
        logger.info("Purchase %s completed via Telebirr", merch_order_id)
    elif trade_status in ("failure", "failed", "expired"):
        purchase.status = "failed"
        purchase.save(update_fields=["status"])

    return HttpResponse("OK")


def _chapa_signature_headers(request):
    """Read Chapa signature headers (case-insensitive via META)."""
    chapa_sig = (
        request.headers.get("Chapa-Signature")
        or request.headers.get("chapa-signature")
        or request.META.get("HTTP_CHAPA_SIGNATURE")
        or ""
    )
    x_chapa_sig = (
        request.headers.get("x-chapa-signature")
        or request.headers.get("X-Chapa-Signature")
        or request.META.get("HTTP_X_CHAPA_SIGNATURE")
        or ""
    )
    return chapa_sig.strip(), x_chapa_sig.strip()


def _complete_chapa_purchase(tx_ref: str, svc: ChapaService):
    """
    Re-verify with Chapa API then mark Purchase completed.
    Returns (HttpResponse/JsonResponse).
    """
    ok, result = svc.verify(tx_ref)
    logger.info("Chapa API verify tx_ref=%s ok=%s result=%s", tx_ref, ok, result)

    try:
        purchase = Purchase.objects.get(purchase_reference=tx_ref)
    except Purchase.DoesNotExist:
        # also try transaction_reference
        purchase = Purchase.objects.filter(transaction_reference=tx_ref).first()
        if not purchase:
            return JsonResponse({"error": "order not found"}, status=404)

    if purchase.status == "completed":
        return JsonResponse({"status": "already_completed", "tx_ref": tx_ref})

    status = (result.get("status") or "").lower()
    if ok and status in ("success", "successful", "completed"):
        purchase.status = "completed"
        purchase.completed_at = timezone.now()
        if result.get("reference"):
            purchase.transaction_reference = str(result["reference"])
        purchase.save()
        _create_author_payment(purchase)
        logger.info("Purchase %s completed via Chapa", tx_ref)
        return JsonResponse({"status": "completed", "tx_ref": tx_ref})

    if status in ("pending", "processing") or (ok and not status):
        return JsonResponse({"status": "pending", "tx_ref": tx_ref})

    # Failed verification / failed payment — only mark failed if API says so
    if status in ("failed", "cancelled", "canceled"):
        purchase.status = "failed"
        purchase.save(update_fields=["status"])
        return JsonResponse({"status": "failed", "detail": result.get("error"), "tx_ref": tx_ref})

    return JsonResponse(
        {"status": "unverified", "detail": result.get("error"), "tx_ref": tx_ref},
        status=400 if not ok else 200,
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def chapa_callback(request):
    """
    Chapa return URL + optional webhook (GET/POST).

    POST webhooks: require valid Chapa-Signature / x-chapa-signature (HMAC).
    Always re-verify the transaction with Chapa's verify API before completing.
    """
    raw_body = request.body or b""
    svc = ChapaService()

    if request.method == "POST" and raw_body:
        chapa_sig, x_chapa_sig = _chapa_signature_headers(request)
        # Production: require at least one signature header on POST
        require_sig = not getattr(settings, "DEBUG", False) or bool(
            getattr(settings, "CHAPA_REQUIRE_WEBHOOK_SIGNATURE", True)
        )
        if require_sig:
            if not chapa_sig and not x_chapa_sig:
                logger.warning("Chapa POST without signature headers")
                return JsonResponse({"error": "missing signature"}, status=401)
            if not svc.verify_webhook(raw_body, chapa_sig, x_chapa_sig):
                logger.warning("Chapa webhook rejected: invalid signature")
                return JsonResponse({"error": "invalid signature"}, status=401)

    tx_ref = (
        request.GET.get("trx_ref")
        or request.GET.get("tx_ref")
        or request.POST.get("tx_ref")
        or request.POST.get("trx_ref")
    )
    if not tx_ref and raw_body:
        tx_ref = svc.extract_tx_ref_from_webhook(raw_body)
    if not tx_ref:
        return JsonResponse({"error": "tx_ref required"}, status=400)

    return _complete_chapa_purchase(tx_ref, svc)


@csrf_exempt
@require_POST
def chapa_webhook(request):
    """
    Dedicated Chapa webhook endpoint (POST only).

    Configure in Chapa dashboard:
      URL:  https://your-domain/payments/chapa/webhook/
      Secret hash: same value as CHAPA_WEBHOOK_SECRET or CHAPA_SECRET_KEY

    Steps:
      1. Verify Chapa-Signature / x-chapa-signature (HMAC-SHA256)
      2. Parse tx_ref from body
      3. Call Chapa verify API
      4. Mark Purchase completed
    """
    raw_body = request.body or b""
    svc = ChapaService()
    chapa_sig, x_chapa_sig = _chapa_signature_headers(request)

    if not chapa_sig and not x_chapa_sig:
        logger.warning("Chapa webhook: missing signature headers")
        return JsonResponse({"error": "missing signature"}, status=401)

    if not svc.verify_webhook(raw_body, chapa_sig, x_chapa_sig):
        logger.warning("Chapa webhook: invalid signature")
        return JsonResponse({"error": "invalid signature"}, status=401)

    tx_ref = svc.extract_tx_ref_from_webhook(raw_body)
    if not tx_ref:
        # fallback form fields
        tx_ref = request.POST.get("tx_ref") or request.POST.get("trx_ref")
    if not tx_ref:
        logger.error("Chapa webhook: no tx_ref in body")
        return JsonResponse({"error": "tx_ref required"}, status=400)

    logger.info("Chapa webhook accepted for tx_ref=%s", tx_ref)
    return _complete_chapa_purchase(tx_ref, svc)


@login_required
def paypal_return(request):
    """User returns from PayPal approve page – capture the order."""
    ref = request.GET.get("ref")
    token = request.GET.get("token")  # PayPal order id
    if not ref:
        return redirect("books:list")

    try:
        purchase = Purchase.objects.get(purchase_reference=ref, user=request.user)
    except Purchase.DoesNotExist:
        return redirect("books:list")

    if purchase.status == "completed":
        return redirect(f"/books/{purchase.book_id}/read/")

    order_id = token or purchase.transaction_id
    if not order_id:
        return redirect(f"/payments/return/?ref={ref}&error=missing_order")

    svc = PayPalService()
    ok, data = svc.capture_order(order_id)
    if ok:
        purchase.status = "completed"
        purchase.completed_at = timezone.now()
        purchase.transaction_reference = order_id
        purchase.save()
        _create_author_payment(purchase)
        return redirect(f"/books/{purchase.book_id}/read/")
    else:
        purchase.status = "failed"
        purchase.save(update_fields=["status"])
        return redirect(f"/payments/return/?ref={ref}&error=capture_failed")


@login_required
def payment_return(request):
    """Generic return page after gateway redirect."""
    ref = request.GET.get("ref")
    cancelled = request.GET.get("cancelled")
    if not ref:
        return redirect("/")
    try:
        purchase = Purchase.objects.get(purchase_reference=ref, user=request.user)
    except Purchase.DoesNotExist:
        return redirect("/")

    if purchase.status == "completed":
        return redirect(f"/books/{purchase.book_id}/read/")

    # Optional: query Telebirr / Chapa status if still pending
    if not cancelled:
        if purchase.payment_method == "telebirr":
            svc = TelebirrService()
            ok, data = svc.query_order(ref)
            status = (data.get("order_status") or data.get("trade_status") or "").upper()
            if ok and status in ("PAY_SUCCESS", "COMPLETED", "SUCCESS"):
                purchase.status = "completed"
                purchase.completed_at = timezone.now()
                purchase.save()
                _create_author_payment(purchase)
                return redirect(f"/books/{purchase.book_id}/read/")

        if purchase.payment_method == "chapa":
            svc = ChapaService()
            ok, data = svc.verify(ref)
            status = (data.get("status") or "").lower() if isinstance(data, dict) else ""
            # SDK may return nested data
            if ok and status in ("success", "successful", "completed"):
                purchase.status = "completed"
                purchase.completed_at = timezone.now()
                purchase.save()
                _create_author_payment(purchase)
                return redirect(f"/books/{purchase.book_id}/read/")
            # also check nested
            if ok and isinstance(data, dict):
                inner = data.get("data") or data.get("raw") or {}
                if isinstance(inner, dict) and (inner.get("status") or "").lower() in ("success", "successful"):
                    purchase.status = "completed"
                    purchase.completed_at = timezone.now()
                    purchase.save()
                    _create_author_payment(purchase)
                    return redirect(f"/books/{purchase.book_id}/read/")

    if cancelled:
        purchase.status = "failed"
        purchase.save(update_fields=["status"])

    return redirect(f"/books/{purchase.book_id}/")


@login_required
@require_POST
def paypal_create_order_js(request):
    """
    PayPal Standard JS SDK — createOrder server callback.
    Body: { book_id }
    Returns: { id: "<paypal_order_id>" }  (required by PayPal Buttons)
    """
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        body = request.POST
    book_id = body.get("book_id") or body.get("bookId")
    if not book_id:
        return JsonResponse({"error": "book_id required"}, status=400)
    book = get_object_or_404(Book, id=book_id, status="published")
    user = request.user
    if Purchase.objects.filter(user=user, book=book, status="completed").exists():
        return JsonResponse({"error": "You already own this book."}, status=400)
    amount = book.price if book.price and book.price > 0 else Decimal("0.00")
    if amount == Decimal("0.00"):
        return JsonResponse({"error": "Free book — no PayPal charge"}, status=400)

    merch_order_id = f"ABY{uuid.uuid4().hex[:14].upper()}"
    purchase = Purchase.objects.create(
        user=user,
        book=book,
        amount=amount,
        status="pending",
        payment_method="paypal",
        transaction_reference=merch_order_id,
        purchase_reference=merch_order_id,
    )
    svc = PayPalService()
    # Convert ETB display to USD for PayPal if needed — use amount as configured currency
    ok, result = svc.create_order_for_js_sdk(
        amount=str(amount),
        description=f"Book: {book.title}"[:120],
        custom_id=merch_order_id,
    )
    if not ok:
        purchase.status = "failed"
        purchase.save(update_fields=["status"])
        return JsonResponse({"error": result.get("error", "PayPal create failed")}, status=400)
    order_id = result.get("order_id") or result.get("id")
    purchase.transaction_id = order_id
    purchase.save(update_fields=["transaction_id"])
    return JsonResponse({"id": order_id, "merch_order_id": merch_order_id})


@login_required
@require_POST
def paypal_capture_order_js(request):
    """
    PayPal Standard JS SDK — onApprove server callback.
    Body: { orderID, book_id? }
    Captures payment and marks Purchase completed → read_url
    """
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        body = request.POST
    order_id = body.get("orderID") or body.get("order_id") or body.get("token")
    if not order_id:
        return JsonResponse({"error": "orderID required"}, status=400)

    purchase = (
        Purchase.objects.filter(transaction_id=order_id, user=request.user)
        .order_by("-created_at")
        .first()
    )
    if not purchase:
        # fallback custom_id search after get_order
        purchase = Purchase.objects.filter(
            user=request.user, payment_method="paypal", status="pending"
        ).order_by("-created_at").first()

    svc = PayPalService()
    ok, data = svc.capture_order(order_id)
    if not ok:
        if purchase:
            purchase.status = "failed"
            purchase.save(update_fields=["status"])
        return JsonResponse({"error": data.get("error", "Capture failed"), "raw": data.get("raw")}, status=400)

    if purchase:
        purchase.status = "completed"
        purchase.completed_at = timezone.now()
        purchase.transaction_reference = order_id
        purchase.save()
        _create_author_payment(purchase)
        return JsonResponse({
            "success": True,
            "status": "COMPLETED",
            "read_url": f"/books/{purchase.book_id}/read/",
            "book_id": purchase.book_id,
        })
    return JsonResponse({"success": True, "status": "COMPLETED"})

