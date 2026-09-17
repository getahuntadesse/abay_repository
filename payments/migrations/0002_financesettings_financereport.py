from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinanceSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("royalty_rate", models.DecimalField(decimal_places=2, default=Decimal("70.00"), help_text="Author royalty share of gross sale (%)", max_digits=5)),
                ("platform_rate", models.DecimalField(decimal_places=2, default=Decimal("30.00"), help_text="Platform (Abrehot) share of gross sale (%)", max_digits=5)),
                ("tax_rate_default", models.DecimalField(decimal_places=2, default=Decimal("10.00"), help_text="Default withholding tax on author royalty (%)", max_digits=5)),
                ("tax_rate_culture", models.DecimalField(decimal_places=2, default=Decimal("5.00"), help_text="Withholding tax for culture-related genres (%)", max_digits=5)),
                ("tax_threshold", models.DecimalField(decimal_places=2, default=Decimal("500.00"), help_text="Royalty amount above which tax applies (ETB)", max_digits=12)),
                ("culture_genres", models.TextField(default="culture,cultural,history,heritage,tradition,ethiopian,amharic,oromo,tigrinya,somali,african,folklore,mythology,traditional,language,literature,poetry,religious,spiritual,custom,ritual,celebration", help_text="Comma-separated genre keywords that use culture tax rate")),
                ("currency", models.CharField(default="ETB", max_length=8)),
                ("notes", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="finance_settings_updates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Finance settings",
                "verbose_name_plural": "Finance settings",
                "db_table": "finance_settings",
            },
        ),
        migrations.CreateModel(
            name="FinanceReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period_type", models.CharField(choices=[("weekly", "Weekly"), ("monthly", "Monthly"), ("annual", "Annual"), ("custom", "Custom")], max_length=20)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("total_gross", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total_royalty", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total_platform", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total_tax", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total_net_authors", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total_paid", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total_pending", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("purchase_count", models.PositiveIntegerField(default=0)),
                ("payment_count", models.PositiveIntegerField(default=0)),
                ("author_count", models.PositiveIntegerField(default=0)),
                ("royalty_rate_snapshot", models.DecimalField(decimal_places=2, default=Decimal("70.00"), max_digits=5)),
                ("platform_rate_snapshot", models.DecimalField(decimal_places=2, default=Decimal("30.00"), max_digits=5)),
                ("tax_threshold_snapshot", models.DecimalField(decimal_places=2, default=Decimal("500.00"), max_digits=12)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                ("generated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="finance_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "finance_reports",
                "ordering": ["-period_end", "-generated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="financereport",
            index=models.Index(fields=["period_type", "period_start", "period_end"], name="finance_rep_period__idx"),
        ),
    ]
