import base64
import uuid

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from djoser.views import UserViewSet
from django.db.models import Exists, OuterRef, Value, Count, BooleanField

from app.filters import IngredientFilter, RecipeFilter
from app.models import Recipe, FavoriteRelation, Ingredient, Subscription
from app.pagination import RecipePagination
from app.serializers import (
    AvatarSerializer,
    SubscribedSerializer,
    RecipeListSerializer,
    RecipeCreateUpdateSerializer,
    RecipeShortSerializer,
    IngredientSerializer, ShoppingCartSerializer, FavoriteRelationSerializer, SubscriptionSerializer, UserSerializer
)
from app.permissions import IsNotSelf, IsNotSubscribed, IsSubscribed, IsRecipeOwner, IsNotAlreadyInFavorites, \
    IsNotAlreadyInCart, IsInFavorites, IsInCart
import logging

User = get_user_model()

logger = logging.getLogger(__name__)


class MainUserViewSet(UserViewSet):
    pagination_class = LimitOffsetPagination

    def get_permissions(self):
        if self.action == 'subscribe':
            if self.request.method == 'DELETE':
                return [IsAuthenticated(), IsNotSelf(), IsSubscribed()]
            if self.request.method == 'POST':
                return [IsAuthenticated(), IsNotSelf(), IsNotSubscribed()]
        if self.action in ['list', 'retrieve', 'create']:
            return []
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='subscriptions')
    def subscriptions(self, request):
        subscriptions = Subscription.objects.filter(sender=request.user).annotate(
            recipes_count=Count('to__recipes'))
        users = [sub.to for sub in subscriptions]

        page = self.paginate_queryset(users)
        if page is not None:
            serializer = SubscribedSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = SubscribedSerializer(
            users,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post', 'delete'], url_path='subscribe',
            permission_classes=[IsAuthenticated, IsNotSelf, IsNotSubscribed | IsSubscribed])
    def subscribe(self, request, id=None):
        user_to_follow = get_object_or_404(User, pk=id)

        if request.method == 'POST':
            subscribe_serializer = SubscriptionSerializer(data={'sender': request.user.id, 'to': user_to_follow.id})
            subscribe_serializer.is_valid(raise_exception=True)
            subscribe_serializer.save()
            serializer = SubscribedSerializer(user_to_follow, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            Subscription.objects.filter(sender=request.user, to=user_to_follow).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'put', 'delete'], url_path='me/avatar', permission_classes=[IsAuthenticated])
    def me_avatar(self, request):
        if request.method == 'GET':
            serializer = AvatarSerializer(request.user)
            return Response(serializer.data)
        if request.method == 'PUT':
            avatar_data = request.data.get('avatar')
            user = request.user
            if not avatar_data:
                return Response({'error': 'No avatar data provided'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                extension, avatar_data = avatar_data.split(';base64,')
                extension = extension.split("/")[-1]
            except:
                return Response({'error': 'Invalid avatar data format'}, status=status.HTTP_400_BAD_REQUEST)
            if avatar_data:
                user.avatar.save(str(uuid.uuid4()) + '.' + extension, ContentFile(base64.b64decode(avatar_data)))
                user.save()
            avatar = None
            if user.avatar:
                avatar = request.build_absolute_uri(user.avatar.url)
            return Response({'avatar': avatar}, status=status.HTTP_200_OK)
        if request.method == 'DELETE':
            if request.user.is_authenticated and request.user.avatar:
                request.user.avatar.delete()
                request.user.save()
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({'error': 'Аватар не найден'}, status=status.HTTP_404_NOT_FOUND)


class IngredientListAPIView(generics.ListAPIView):
    serializer_class = IngredientSerializer
    queryset = Ingredient.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_class = IngredientFilter


class IngredientDetailAPIView(generics.RetrieveAPIView):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeListSerializer
    pagination_class = RecipePagination
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = RecipeFilter

    def get_permissions(self):
        if self.action in ['create']:
            return [IsAuthenticated()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsRecipeOwner()]
        if self.action == 'favorite':
            if self.request.method == 'POST':
                return [IsAuthenticated(), IsNotAlreadyInFavorites()]
            return [IsAuthenticated(), IsInFavorites()]
        if self.action == 'shopping_cart':
            if self.request.method == 'POST':
                return [IsAuthenticated(), IsNotAlreadyInCart()]
            return [IsAuthenticated(), IsInCart()]
        return super().get_permissions()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    # def update(self, request, *args, **kwargs):
    #     instance = self.get_object()
    #     if instance.author != request.user:
    #         raise PermissionDenied()
    #     return super().update(request, args, kwargs)
    def get_serializer_class(self):
        if self.action.lower() in ['list', 'retrieve']:
            return RecipeListSerializer
        else:
            return RecipeCreateUpdateSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action.lower() in ['list', 'retrieve']:
            return self._get_get_queryset(queryset)
        else:
            return queryset

    def _get_get_queryset(self, queryset):
        user = self.request.user

        if user.is_authenticated:

            queryset = queryset.annotate(
                is_favorited=Exists(
                    user.favorites.filter(recipe_id=OuterRef('id'))
                ),
                is_in_shopping_cart=Exists(
                    user.shopping_cart.filter(recipe_id=OuterRef('id'))
                )
            )
        else:
            queryset = queryset.annotate(
                is_favorited=Value(False, output_field=BooleanField()),
                is_in_shopping_cart=Value(False, output_field=BooleanField())
            )
        logger.warning(queryset.query)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, mees, pk=None):
        inst = Recipe.objects.get(pk=pk)
        return Response({'short-link': reverse('short-link', kwargs={'pk': inst.short_link})})

    @action(detail=True, methods=['post', 'delete'], url_path='favorite')
    def favorite(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == 'POST':
            favorite_serializer = FavoriteRelationSerializer(data={'user': request.user.pk, 'recipe': recipe.pk})
            favorite_serializer.is_valid(raise_exception=True)
            favorite_serializer.save()
            serializer = RecipeShortSerializer(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            FavoriteRelation.objects.filter(user=request.user, recipe=recipe).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'], url_path='shopping_cart')
    def shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == 'POST':
            shopping_cart_serializer = ShoppingCartSerializer(data={'user': request.user.pk, 'recipe': recipe.pk})
            shopping_cart_serializer.is_valid(raise_exception=True)
            shopping_cart_serializer.save()
            serializer = RecipeShortSerializer(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            request.user.shopping_cart.filter(recipe_id=pk).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='download_shopping_cart')
    def download_shopping_cart(self, request):
        ingredients = request.user.shopping_cart.all().values_list(
            'recipe__recipe_ingredients__ingredient__name',
            'recipe__recipe_ingredients__ingredient__measurement_unit',
            'recipe__recipe_ingredients__amount'
        )

        shopping_list = {}
        for name, unit, amount in ingredients:
            if name not in shopping_list:
                shopping_list[name] = {'amount': 0, 'unit': unit}
            shopping_list[name]['amount'] += amount

        text_content = "Список покупок:\n\n"
        for name, data in shopping_list.items():
            text_content += f"{name} - {data['amount']} {data['unit']}\n"

        response = Response(text_content, content_type='text/plain', status=status.HTTP_200_OK)
        response['Content-Disposition'] = 'attachment; filename="shopping_list.txt"'
        return response


def view_short_link(request, pk):
    return redirect('recipes-detail', pk=Recipe.objects.get(short_link=pk).pk)
