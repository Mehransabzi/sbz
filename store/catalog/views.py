from .search.engine import search_products
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from .models import Product
from .serializers import StorefrontProductSerializer


class ProductListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = StorefrontProductSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True, is_visible=True)
        query = self.request.query_params.get("q", "").strip()
        category = self.request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__iexact=category)
        return search_products(query, queryset=queryset) if query else queryset


from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from store.accounts.permissions import can_view_prices


@api_view(["GET"])
@permission_classes([AllowAny])
def cart_products(request):
    if not can_view_prices(request.user):
        return Response({"detail": "دسترسی به سبد خرید نیازمند حساب تأییدشده است."}, status=403)
    codes = list(dict.fromkeys(request.query_params.getlist("code")))
    if len(codes) > 100 or any(len(code) > 100 for code in codes):
        return Response({"detail": "تعداد یا کد کالا نامعتبر است."}, status=400)
    rows = Product.objects.filter(chortke_code__in=codes, is_active=True, is_visible=True)
    response = Response({"products": [{"code": p.chortke_code, "name": p.name, "price": str(p.sale_price), "unit": p.unit or "عدد", "image": p.display_image_url} for p in rows]})
    response["Cache-Control"] = "private, no-store"
    return response
