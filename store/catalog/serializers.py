from rest_framework import serializers

from store.accounts.permissions import can_view_prices

from .models import Product


class StorefrontProductSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source="display_description", read_only=True)
    id = serializers.CharField(source="chortke_code")
    nameEn = serializers.SerializerMethodField()
    oemCode = serializers.CharField(source="display_code")
    categoryLabel = serializers.CharField(source="category", allow_blank=True)
    category = serializers.CharField(allow_blank=True)
    price = serializers.SerializerMethodField()
    imageUrl = serializers.CharField(source="display_image_url", allow_blank=True)
    vehicleModelSummary = serializers.SerializerMethodField()
    compatibleVehicles = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    brandCountry = serializers.SerializerMethodField()
    specifications = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    reviewsCount = serializers.SerializerMethodField()
    isGenuine = serializers.SerializerMethodField()
    warrantyPeriod = serializers.SerializerMethodField()
    graphicType = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "nameEn", "oemCode", "category", "categoryLabel",
            "vehicleModelSummary", "specifications", "description", "features",
            "rating", "reviewsCount", "isGenuine", "warrantyPeriod",
            "graphicType", "imageUrl", "barcode", "unit", "price",
            "compatibleVehicles", "brand", "brandCountry",
        ]

    def get_nameEn(self, _obj):
        return ""

    def get_price(self, obj):
        request = self.context.get("request")
        return float(obj.sale_price) if request and can_view_prices(request.user) else None

    def get_vehicleModelSummary(self, _obj):
        return "برای استعلام سازگاری تماس بگیرید"

    def get_compatibleVehicles(self, _obj):
        return []

    def get_brand(self, _obj):
        return "ثبت نشده"

    def get_brandCountry(self, _obj):
        return "—"

    def get_specifications(self, obj):
        values = {"واحد": obj.unit} if obj.unit else {}
        if obj.accounting_code and obj.accounting_code != obj.chortke_code:
            values["کد حسابداری"] = obj.accounting_code
        if obj.barcode:
            values["بارکد"] = obj.barcode
        return values

    def get_features(self, obj):
        return [line.strip() for line in obj.display_description.splitlines() if line.strip()]

    def get_rating(self, _obj):
        return 0

    def get_reviewsCount(self, _obj):
        return 0

    def get_isGenuine(self, _obj):
        return False

    def get_warrantyPeriod(self, _obj):
        return "شرایط ضمانت هنگام سفارش هماهنگ می‌شود"

    def get_graphicType(self, obj):
        return "product"
