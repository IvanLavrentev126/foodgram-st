from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission

User = get_user_model()


class IsRecipeOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        return obj.author == request.user
