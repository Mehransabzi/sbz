from store.controlpanel.models import SiteConfiguration


def shop_contact(request):
    return {"shop_contact": SiteConfiguration.objects.first() or SiteConfiguration()}
