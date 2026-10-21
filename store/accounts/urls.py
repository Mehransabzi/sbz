from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("profile/orders/<str:order_number>/invoice/", views.invoice_download, name="invoice-download"),
    path("register/", views.register, name="register"),
    path("login/", views.CustomerLoginView.as_view(), name="login"),
    path("logout/", views.CustomerLogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("profile/orders/<str:order_number>/", views.profile_order, name="profile-order"),
    path("password/change/", views.CustomerPasswordChangeView.as_view(), name="password-change"),
    path("password/changed/", views.password_change_done, name="password-change-done"),
]
