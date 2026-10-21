from django.contrib.auth.backends import ModelBackend


class SingleUserModelBackend(ModelBackend):
    """Keep direct user permissions while disabling Django group permissions."""

    def get_group_permissions(self, user_obj, obj=None):
        return set()
