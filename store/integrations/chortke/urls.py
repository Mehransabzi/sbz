from django.urls import path

from .views import ChortkeStatusView

urlpatterns = [path("status/", ChortkeStatusView.as_view(), name="chortke-status")]
