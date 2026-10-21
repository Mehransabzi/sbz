from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SyncRun


class ChortkeStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, _request):
        latest = SyncRun.objects.first()
        return Response(
            {
                "configured": bool(settings.CHORTKE_ACCESS_TOKEN),
                "images_configured": bool(settings.CHORTKE_ACCESS_TOKEN),
                "last_sync": (
                    {
                        "status": latest.status,
                        "started_at": latest.started_at,
                        "finished_at": latest.finished_at,
                        "received_count": latest.received_count,
                        "saved_count": latest.saved_count,
                        "skipped_count": latest.skipped_count,
                    }
                    if latest
                    else None
                ),
            }
        )
