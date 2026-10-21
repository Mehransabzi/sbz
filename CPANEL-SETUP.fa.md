# راه‌اندازی فروشگاه سبزی روی sbzpart.ir

این بسته برای نصب اولیه با اطلاعات فعلی فروشگاه است. آن را روی دیتابیس یک سایت فعال و دارای سفارش‌های جدید استخراج نکنید.
بسته حاوی اطلاعات مشتریان و کلیدهای محرمانه است؛ آن را داخل public_html یا یک لینک عمومی قرار ندهید.

## ۱. بررسی امکانات هاست

در cPanel باید Setup Python App و نسخه Python 3.12 وجود داشته باشد. Python 3.11 هم با Django 5.2 سازگار است، اما این پروژه محلی با 3.12 اجرا می‌شود.
اگر فقط Application Manager می‌بینید، تنظیمات این راهنما دقیقاً همان صفحه نیست؛ از پشتیبانی بخواهید اجرای Django با Passenger و Python 3.12 را فعال کند.
Terminal یا SSH برای فرمان‌های آماده‌سازی لازم است. هاست باید اجازه نوشتن SQLite و media، دسترسی خروجی HTTPS به GapGPT و چرتکه و اجرای فرایند پایتون برای همگام‌سازی را بدهد.
برای PDF، Pango و وابستگی‌های WeasyPrint باید در محیط محدودشده حساب شما موجود باشند؛ نصب pip به‌تنهایی کتابخانه‌های سیستم‌عامل را نصب نمی‌کند.

## ۲. دامنه و SSL

دامنه sbzpart.ir را در Domains به حساب هاست متصل کنید. DNS را طبق مشخصات شرکت هاست تنظیم کنید.
در SSL/TLS Status گواهی دامنه را فعال کنید. پس از معتبرشدن گواهی، در Domains گزینه Force HTTPS Redirect را فعال کنید.
ورود کاربران و پنل را از HTTPS انجام دهید؛ کوکی‌های نسخه سرور فقط روی HTTPS ارسال می‌شوند.
در مثال‌های بعد USER نام کاربری cPanel شما و public_html نمونه مسیر Document Root دامنه است. مسیر واقعی را از Domains بخوانید.

## ۳. ساخت برنامه Python

Software → Setup Python App → Create Application:

| گزینه | مقدار |
|---|---|
| Python version | 3.12 |
| Application root | sbz |
| Application URL | sbzpart.ir و مسیر / |
| Application startup file | passenger_wsgi.py |
| Application Entry point | application |

Create را بزنید. دستور فعال‌سازی محیط مجازی که خود cPanel نشان می‌دهد را نگه دارید؛ مسیر آن بین هاست‌ها فرق می‌کند.
اگر Environment Variables قبلی دارید، مقادیر متناقض DEBUG، SECRET_KEY و DJANGO_SETTINGS_MODULE را حذف یا با بسته هماهنگ کنید؛ متغیرهای پنل بر فایل .env اولویت دارند.

## ۴. بارگذاری ZIP

در File Manager به /home/USER/sbz بروید، ZIP را آپلود و همان‌جا Extract کنید.
اگر هنگام ساخت برنامه فایل نمونه passenger_wsgi.py ساخته شده است، آن را با فایل داخل ZIP جایگزین کنید.
فایل manage.py و پوشه‌های config، store، media، templates و staticfiles باید مستقیم داخل sbz باشند، نه یک پوشه تودرتوی دیگر.
در Settings فایل‌منیجر، Show Hidden Files را روشن کنید و وجود .env را بررسی کنید.
فایل .env بسته برای دامنه آماده شده است. DJANGO_SECRET_KEY آن مخصوص همین دیتابیس بسته است؛ آن را با نسخه محلی عوض نکنید.
حساب‌های فعلی مدیر و مشتریان، رمزهای عبور، سفارش‌ها و عکس‌ها منتقل می‌شوند؛ نیازی به ساخت مجدد همه کاربران نیست.
به علت تغییر کلید نسخه سرور، کاربران باید دوباره وارد شوند؛ رمز حساب‌ها تغییری نمی‌کند.

## ۵. نصب وابستگی‌ها

در Terminal، ابتدا دستور activation نمایش‌داده‌شده در Setup Python App را عیناً اجرا کنید، سپس:

```bash
cd /home/USER/sbz
export DJANGO_SETTINGS_MODULE=config.cpanel
python --version
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
python -c "from passenger_wsgi import application; print('WSGI ready')"
python -c "from weasyprint import HTML; print('PDF dependencies ready')"
chmod 600 .env db.sqlite3
```

اگر نصب WeasyPrint یا دستور آخر خطای Pango/libgobject داد، متن خطا را به هاست بدهید. کتابخانه سیستمی را نمی‌توان صرفاً با pip جایگزین کرد.
check --deploy ممکن است درباره HSTS و HTTPS redirect هشدار دهد. در این بسته هدایت HTTPS توسط cPanel انجام می‌شود و HSTS تا تأیید SSL خاموش است.
به‌طور پیش‌فرض هدر proxy مورد اعتماد نیست؛ اگر پشت CDN/proxy هستید و هاست تأیید کرد هدر X-Forwarded-Proto را خودش جایگزین می‌کند، DJANGO_TRUST_PROXY_SSL_HEADER=true را در .env تنظیم و برنامه را Restart کنید.

## ۶. نمایش استایل‌ها و عکس‌ها

برنامه بیرون public_html است؛ فقط staticfiles و media باید از وب در دسترس باشند.
اگر Document Root دامنه /home/USER/public_html است و هنوز پوشه‌ای با نام static یا media داخل آن ندارید:

```bash
ln -s /home/USER/sbz/staticfiles /home/USER/public_html/static
ln -s /home/USER/sbz/media /home/USER/public_html/media
```

اگر دامنه Document Root دیگری دارد، همان مسیر واقعی را جای public_html بگذارید.
اگر پوشه static یا media از قبل هست، حذف یا روی آن overwrite نکنید؛ ابتدا محتویات و تنظیمات سایت قبلی را بررسی کنید.
اگر هاست symlink را مسدود کرده یا 403 می‌دهد، از پشتیبانی بخواهید /static/ را به /home/USER/sbz/staticfiles و /media/ را به /home/USER/sbz/media متصل کند.
فقط کپی‌کردن media کافی نیست؛ عکس‌های آپلودی بعدی هم باید از همین مسیر قابل نمایش باشند.
در بسته، فایل .htaccess برای staticfiles و media قرار دارد تا Passenger این مسیرها را به Django نفرستد؛ اجرای پسوندهای برنامه در media نیز بسته می‌شود.
اگر هاست اجازه دستورهای .htaccess را نمی‌دهد، از پشتیبانی بخواهید همین محدودیت‌ها را در تنظیمات وب‌سرور اعمال کند.
کل پروژه، .env و db.sqlite3 را به public_html منتقل نکنید. هیچ پوشه‌ای را chmod 777 نکنید.

## ۷. راه‌اندازی نهایی

در Setup Python App روی Restart بزنید. این نشانی‌ها را بررسی کنید:

```text
https://sbzpart.ir/
https://sbzpart.ir/catalog/
https://sbzpart.ir/panel/
https://sbzpart.ir/api/health/
https://sbzpart.ir/static/storefront/media/favicon.png
```

در پنل با حساب مدیر فعلی وارد شوید. یک عکس کالا را ببینید، جستجوی محصولات را انجام دهید، PDF یک سفارش را دانلود کنید و همگام‌سازی چرتکه را بررسی کنید.
برای بررسی فرمان همگام‌سازی از Terminal، پس از activation و export متغیر تنظیمات:

```bash
python manage.py sync_chortke_products
```

اگر اجرای فرایند پس‌زمینه در هاست مسدود باشد، دکمه همگام‌سازی پنل کار نخواهد کرد؛ از هاست اجرای worker را بخواهید یا با برنامه‌ریزی خودتان فرمان بالا را اجرا کنید.
بعد از Extract، ZIP را از هاست حذف کنید؛ فایل حاوی اطلاعات خصوصی است.

## خطاهای رایج

- 500/503: لاگ Passenger در Setup Python App و بخش Errors را بررسی کنید؛ Python انتخابی، نصب requirements و فایل startup را کنترل کنید. برای رفع خطا DEBUG را عمومی روشن نکنید.
- DisallowedHost: DJANGO_ALLOWED_HOSTS در .env باید sbzpart.ir,www.sbzpart.ir باشد؛ آدرس را بدون https و / وارد کنید.
- CSRF 403: از HTTPS وارد شوید و DJANGO_CSRF_TRUSTED_ORIGINS را بررسی کنید. این مقدار باید شامل https:// باشد.
- استایل یا عکس 404/403: collectstatic، اتصال مسیرهای static/media و مجوز خواندن وب‌سرور را بررسی کنید.
- readonly database: فایل db.sqlite3 و پوشه sbz باید برای کاربر اجرای برنامه قابل نوشتن باشند؛ SQLite کنار دیتابیس فایل journal می‌سازد.
- خطای database is locked در بار بالا: SQLite این بسته برای انتقال اولیه حفظ شده؛ پیش از افزایش بار، مهاجرت برنامه‌ریزی‌شده به PostgreSQL/MySQL لازم است.
- نصب موفق ولی دانلود PDF ناموفق: کتابخانه‌های Pango/libgobject را با پشتیبانی هاست بررسی کنید.

## منابع رسمی

- https://docs.cloudlinux.com/cloudlinuxos/lve_manager/#python-selector
- https://docs.cpanel.net/cpanel/software/application-manager/
- https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- https://doc.courtbouillon.org/weasyprint/v67.0/first_steps.html
- https://www.phusionpassenger.com/docs/references/config_reference/apache/


## به‌روزرسانی خودکار کد از GitHub

مخزن پروژه: `https://github.com/Mehransabzi/sbz`، شاخهٔ `main`.
مخزن فعلی عمومی است؛ کد و تاریخچهٔ فایل‌های commitشده برای همه قابل مشاهده است. `.env`، پایگاه داده و `media` در Git نیستند.

در cPanel → **Git Version Control** → **Create**، آدرس HTTPS بالا را وارد کنید و مخزن را در مسیری بیرون از `public_html` و بیرون از پوشهٔ برنامه، مثلاً `/home/USER/repositories/sbz`، clone کنید. مسیر clone نباید `/home/USER/sbz` باشد؛ آن مسیر پوشهٔ اجرای برنامه است.

در تب **Manage → Pull or Deploy** ابتدا **Update from Remote** و سپس **Deploy HEAD Commit** را بزنید. فایل `.cpanel.yml` در ریشهٔ شاخهٔ `main`، فایل‌های commitشده را با `git archive` به `/home/sbzparti/sbz` استخراج می‌کند، مهاجرت‌ها و `collectstatic` را اجرا می‌کند و Passenger را Restart می‌کند. فایل `.env`، `db.sqlite3`، `media` و `staticfiles` روی هاست حفظ می‌شوند. بررسی کنید قابلیت Git Deployment در هاست برای مخزن فعال باشد.

پس از استقرار نخستین نسخه، بررسی کنید فایل `/home/sbzparti/sbz/.env`، پایگاه داده، تصاویر محصولات و لینک‌های `public_html/static` و `public_html/media` هنوز در مسیرهای بالا هستند. `.cpanel.yml` عمداً پوشهٔ `tmp` را از rsync حذف می‌کند و فقط `tmp/restart.txt` را به‌روز می‌کند.

اگر در `requirements.txt` وابستگی جدید یا نسخهٔ تازه اضافه شد، یک‌بار با محیط مجازی cPanel وابستگی‌ها را نصب کنید؛ Deployment عمداً در هر انتشار pip را اجرا نمی‌کند:

```bash
source /home/sbzparti/virtualenv/sbz/3.12/bin/activate
cd /home/sbzparti/sbz
python -m pip install -r requirements.txt --timeout 180 --retries 10
```

برای هر تغییر: روی رایانه `git add`، `git commit` و `git push`؛ سپس در cPanel **Update from Remote** و **Deploy HEAD Commit**. پس از انتشار، `/api/health/` را باز کنید. اگر دستور Deploy در cPanel وجود ندارد یا اجرا نشد، هاست باید Git deployment و اجرای `.cpanel.yml` را فعال کند.
