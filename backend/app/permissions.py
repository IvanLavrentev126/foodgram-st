from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission

from app.models import FavoriteRelation, Subscription, Recipe, ShoppingCartRelation

User = get_user_model()


class GenericAPIException(APIException):
    """
    raises API exceptions with custom messages and custom status codes
    """
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail, status_code=None):
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class IsNotSelf(BasePermission):
    """Проверяет, что пользователь не пытается выполнить действие с самим собой"""

    def has_permission(self, request, view):
        if view.action in ['subscribe']:
            user_to_follow = get_object_or_404(User, pk=view.kwargs.get('id'))
            if request.user == user_to_follow:
                raise GenericAPIException('')
        return True


class IsNotSubscribed(BasePermission):
    """Проверяет, что пользователь еще не подписан"""

    def has_permission(self, request, view):
        if view.action == 'subscribe' and request.method == 'POST':
            user_to_follow = get_object_or_404(User, pk=view.kwargs.get('id'))
            if Subscription.objects.filter(
                    sender=request.user,
                    to=user_to_follow
            ).exists():
                raise GenericAPIException('')
        if view.action == 'subscribe' and request.method == 'DELETE':
            user_to_follow = get_object_or_404(User, pk=view.kwargs.get('id'))
            if not Subscription.objects.filter(
                    sender=request.user,
                    to=user_to_follow
            ).exists():
                raise GenericAPIException('')
        return True


class IsSubscribed(BasePermission):
    """Проверяет, что пользователь подписан"""

    def has_permission(self, request, view):
        if view.action == 'subscribe' and request.method == 'DELETE':
            user_to_follow = get_object_or_404(User, pk=view.kwargs.get('id'))
            if not Subscription.objects.filter(
                sender=request.user,
                to=user_to_follow
            ).exists():
                raise GenericAPIException('')
        return True


class HasAvatar(BasePermission):
    """Проверяет, что у пользователя есть аватар для удаления"""

    def has_permission(self, request, view):
        if view.action == 'me_avatar' and request.method == 'DELETE':
            return request.user.avatar
        return True


class IsRecipeOwner(BasePermission):
    """Проверяет, что пользователь является автором рецепта"""

    def has_object_permission(self, request, view, obj):
        return obj.author == request.user


class IsNotAlreadyInFavorites(BasePermission):
    """Проверяет, что рецепта еще нет в избранном"""

    def has_permission(self, request, view):
        if view.action == 'favorite' and request.method == 'POST':
            recipe = get_object_or_404(Recipe, pk=view.kwargs.get('pk'))
            if FavoriteRelation.objects.filter(
                user=request.user,
                recipe=recipe
            ).exists():
                raise GenericAPIException('')
        return True


class IsInFavorites(BasePermission):
    """Проверяет, что рецепт есть в избранном"""

    def has_permission(self, request, view):
        if view.action == 'favorite' and request.method == 'DELETE':
            recipe = get_object_or_404(Recipe, pk=view.kwargs.get('pk'))
            if not FavoriteRelation.objects.filter(
                    user=request.user,
                    recipe=recipe
            ).exists():
                raise GenericAPIException('')
        return True


class IsNotAlreadyInCart(BasePermission):
    """Проверяет, что рецепта еще нет в корзине"""

    def has_permission(self, request, view):
        if view.action == 'shopping_cart' and request.method == 'POST':
            recipe = get_object_or_404(Recipe, pk=view.kwargs.get('pk'))
            if ShoppingCartRelation.objects.filter(
                user=request.user,
                recipe=recipe
            ).exists():
                raise GenericAPIException('')
        return True


class IsInCart(BasePermission):
    """Проверяет, что рецепт есть в корзине"""

    def has_permission(self, request, view):
        if view.action == 'shopping_cart' and request.method == 'DELETE':
            recipe = get_object_or_404(Recipe, pk=view.kwargs.get('pk'))
            if not request.user.shopping_cart.filter(recipe=recipe).exists():
                raise GenericAPIException('')
        return True
