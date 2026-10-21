from django.urls import path
from . import views
from store.support import views as support_views

app_name = "controlpanel"
urlpatterns = [
    path("products/<int:product_id>/image/", views.product_image, name="product-image"),
    path('support/',support_views.inbox,name='support-inbox'),
    path("stories/", views.daily_stories, name="daily-stories"),
    path("sync/report/", views.sync_report, name="sync-report"),
    path("sync/status/<int:run_id>/", views.sync_status, name="sync-status"),
    path("products/<int:product_id>/description/", views.product_description, name="product-description"),
    path("ai/customer-chats/delete-all/", views.delete_all_customer_chats, name="ai-customer-chats-delete-all"),
    path("ai/image-usage/", views.image_usage_report, name="image-usage"),
    path("ai/", views.ai_analysis, name="ai-analysis"),
    path("ai/customer-chats/", views.customer_ai_chats, name="ai-customer-chats"),
    path("ai/customer-chats/<int:conversation_id>/delete/", views.delete_customer_ai_chat, name="ai-customer-chat-delete"),
    path("customers/<int:profile_id>/debt/", views.customer_debt, name="customer-debt"),
    path("", views.dashboard, name="dashboard"),
    path("customers/", views.customers, name="customers"),
    path("products/", views.products, name="products"),
    path("products/<int:product_id>/visibility/", views.toggle_product_visibility, name="product-visibility"),
    path("orders/", views.orders, name="orders"), path("orders/<int:order_id>/invoice/", views.order_invoice, name="order-invoice"), path("orders/<int:order_id>/", views.order_detail, name="order-detail"),
    path("sync/", views.sync, name="sync"), path("settings/", views.site_settings, name="site-settings"),
    path("customers/<int:profile_id>/approval/", views.customer_approval, name="customer-approval"),
    path("orders/<int:order_id>/status/", views.order_status, name="order-status"),
]
