FINANCE + TELEBIRR

1. Migrate:
   python manage.py migrate payments

2. Finance officer (role: finance / admin / maker):
   /payments/finance/settings/   -> set royalty %, tax %, threshold
   /payments/finance/reports/    -> weekly / monthly / annual reports

3. Book buyers pay with Telebirr only (purchase UI).

4. Author royalties:
   - Calculated using FinanceSettings rates (not .env)
   - Paid out via Telebirr only (process author payment)
   - After Telebirr succeeds, use Mark Paid on dashboard or POST
     /payments/author/<id>/mark-paid/

Rates are stored in finance_settings table — officers change them in the UI.
