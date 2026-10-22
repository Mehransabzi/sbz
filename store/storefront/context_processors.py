from store.controlpanel.models import Announcement, SiteConfiguration


def shop_contact(request):
    return {"shop_contact": SiteConfiguration.objects.first() or SiteConfiguration()}


def announcements(request):
    if request.path.startswith(("/panel/", "/admin/")):
        return {}
    return {"site_announcements": Announcement.objects.filter(is_active=True)}
