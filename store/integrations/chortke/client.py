from dataclasses import dataclass

import requests
from django.conf import settings


class ChortkeError(Exception):
    pass


@dataclass
class ChortkeClient:
    base_url: str = settings.CHORTKE_API_BASE_URL
    access_token: str = settings.CHORTKE_ACCESS_TOKEN

    def __post_init__(self):
        if not self.access_token:
            from store.controlpanel.models import SiteConfiguration
            self.access_token = SiteConfiguration.current().get_chortke_api_key() or settings.CHORTKE_ACCESS_TOKEN
        if not self.access_token:
            raise ChortkeError("CHORTKE_ACCESS_TOKEN را در فایل .env ریشه پروژه تنظیم کنید.")

    def _post(self, path, *, body):
        try:
            response = requests.post(
                f"{self.base_url}{path}",
                json=body,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=(8, 35),
            )
        except requests.RequestException as exc:
            raise ChortkeError(f"ارتباط با API چرتکه برقرار نشد: {exc}") from exc
        if not response.ok:
            raise ChortkeError(f"API چرتکه HTTP {response.status_code}: {response.text[:500]}")
        try:
            return response.json()
        except ValueError as exc:
            raise ChortkeError("پاسخ API چرتکه JSON معتبر نبود.") from exc

    def get_products(self):
        """Read every product page from Chortke's Bearer-authenticated API."""
        page_size = settings.CHORTKE_PAGE_SIZE
        products = []
        for page in range(1, 10000):
            response = self._post(
                "/v2/products/list",
                body={"limit": page_size, "page": page, "isProduct": 1},
            )
            records = response.get("products")
            if not isinstance(records, list):
                raise ChortkeError("فهرست کالاها در پاسخ /v2/products/list پیدا نشد.")
            products.extend(records)
            paginate = response.get("paginate") or {}
            if not paginate.get("hasNextPage", len(records) == page_size):
                return products
        raise ChortkeError("دریافت کالاها از حد صفحه‌های مجاز عبور کرد.")
