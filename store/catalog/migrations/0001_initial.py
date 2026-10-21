from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chortke_code", models.CharField(max_length=100, unique=True)),
                ("accounting_code", models.CharField(blank=True, max_length=100)),
                ("barcode", models.CharField(blank=True, max_length=128)),
                ("name", models.CharField(max_length=255)),
                ("category", models.CharField(blank=True, max_length=160)),
                ("description", models.TextField(blank=True)),
                ("unit", models.CharField(blank=True, max_length=32)),
                ("stock", models.DecimalField(decimal_places=3, default=0, max_digits=16)),
                ("sale_price", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("image_url", models.URLField(blank=True, max_length=1000)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("synced_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "کالا",
                "verbose_name_plural": "کالاها",
                "ordering": ["name", "chortke_code"],
                "indexes": [models.Index(fields=["is_active", "name"], name="catalog_prod_active_name")],
            },
        ),
    ]
