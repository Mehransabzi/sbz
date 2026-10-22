# یکسان‌سازی دامنه و انتشار

انتشار از `.cpanel.yml` انجام می‌شود. این روال ابتدا نسخه پشتیبان سازگار از SQLite در `tmp/deployment-backups` می‌گیرد، مهاجرت‌ها و collectstatic را اجرا می‌کند و Passenger را راه‌اندازی مجدد می‌کند.

سپس `deployment/configure_https.py --document-root /home/sbzparti/public_html` یک بلوک مشخص‌شده را به ابتدای `.htaccess` موجود اضافه می‌کند. تنظیمات Passenger و دیگر تنظیمات هاست حفظ می‌شوند و از فایل قبلی نسخه پشتیبان گرفته می‌شود. نیازی به جایگزینی کل فایل نیست.

اسکریپت هر سه نسخه HTTP و www را با HEAD بررسی می‌کند: وضعیت ۳۰۱، مقصد اصلی، حفظ مسیر و پارامترها و بازشدن صفحه HTTPS بدون حلقه. فقط پس از تأیید، هدر HSTS با `max-age=31536000` روی پاسخ‌های HTTPS فعال می‌شود. در صورت شکست، فایل قبلی برگردانده می‌شود و انتشار خطا می‌دهد. `includeSubDomains` و `preload` فعال نمی‌شوند.

```sh
curl -sI http://sbzpart.ir/
curl -sI http://www.sbzpart.ir/
curl -sI https://www.sbzpart.ir/
curl -sI https://sbzpart.ir/
```

robots و sitemap در `/robots.txt` و `/sitemap.xml` قرار دارند. نقشه سایت در هر درخواست از کالاهای فعال و قابل‌نمایش و دسته‌های آن‌ها ساخته می‌شود؛ کالاهای مخفی صفحه عمومی ندارند و در نقشه نمی‌آیند. پس از همگام‌سازی، نیازی به ساخت دستی نقشه نیست.

آدرس `https://sbzpart.ir/sitemap.xml` باید در Search Console ثبت شود. ثبت موفق فقط پس از تأیید مالکیت حساب گوگل ممکن است. فایل نمونه `public_html.htaccess` صرفاً برای مرجع است؛ روش توصیه‌شده، اسکریپت حفظ تنظیمات موجود است.
