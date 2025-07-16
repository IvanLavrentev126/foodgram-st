import logging

from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Count, Exists, OuterRef, Value, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from app.api.filters import IngredientFilter, RecipeFilter
from app.api.pagination import RecipePagination
from app.api.permissions import IsRecipeOwner
from app.api.serializers import (AvatarSerializer, FavoriteRelationSerializer,
                                 IngredientSerializer,
                                 RecipeCreateUpdateSerializer,
                                 RecipeListSerializer, RecipeShortSerializer,
                                 ShoppingCartSerializer, SubscribedSerializer,
                                 SubscriptionSerializer, UserSerializer)
from app.models import FavoriteRelation, Ingredient, Recipe, Subscription

User = get_user_model()

logger = logging.getLogger(__name__)


class MainUserViewSet(UserViewSet):
    pagination_class = LimitOffsetPagination

    def get_permissions(self):  # todo мб надо передалать
        if self.action in ['list', 'retrieve', 'create']:
            return []
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='subscriptions', permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        users = User.objects.filter(
            subscribed_to__sender=request.user
        ).annotate(
            recipes_count=Count('recipes')
        ).prefetch_related('recipes')

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
            permission_classes=[IsAuthenticated])
    def subscribe(self, request, id=None):
        if request.method == 'POST':
            user_to_follow = get_object_or_404(
                User.objects.annotate(recipes_count=Count('recipes')),
                pk=id
            )
            subscribe_serializer = SubscriptionSerializer(data={
                'sender': request.user.id,
                'to': user_to_follow.id
            })
            subscribe_serializer.is_valid(raise_exception=True)
            subscribe_serializer.save()
            serializer = SubscribedSerializer(
                user_to_follow,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            # Ты можешь удалить подписку/рецепт за один запрос в БД (сейчас много лишних запросов).
            # Просто фильтруй queryset по ID пользователя и автора/рецепта и удаляй полученный queryset
            # .delete() возвращает тебе количество удаленных записей -> если ничего не удалилось,
            # можешь сообщать пользователю об ошибке
            #
            # Проверь подобное во всем проекте
            #
            # FIXME  У тебя тогда не будут проходить несколько тестов в Postman на удаление - но это нормально,
            # FIXME  их не успели обновить к новому проекту
            deleted_count, _ = Subscription.objects.filter(
                sender=request.user,
                to_id=id
            ).delete()

            if deleted_count == 0:
                return Response(
                    {'detail': 'Подписка не найдена.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'put', 'delete'], url_path='me/avatar', permission_classes=[IsAuthenticated])
    def me_avatar(self, request):
        user = request.user

        if request.method == 'GET':
            serializer = AvatarSerializer(user)
            return Response(serializer.data)

        if request.method == 'PUT':
            serializer = AvatarSerializer(user, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        if request.method == 'DELETE':
            if user.avatar:
                user.avatar.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = IngredientFilter


class RecipeViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeListSerializer
    pagination_class = RecipePagination
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = RecipeFilter

    def get_permissions(self):
        if self.action in ['create', 'favorite', 'shopping_cart']:
            return [IsAuthenticated()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsRecipeOwner()]
        return super().get_permissions()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_serializer_class(self):
        if self.action.lower() in ['list', 'retrieve']:
            return RecipeListSerializer
        else:
            return RecipeCreateUpdateSerializer

    def get_queryset(self):
        queryset = Recipe.objects.all().select_related('author').prefetch_related('ingredients')
        if self.action.lower() in ['list', 'retrieve']:
            return self._list_retrieve_queryset_builder(queryset)
        else:
            return queryset

    def _list_retrieve_queryset_builder(self, queryset):
        user = self.request.user
        if user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    user.favoriterelation.filter(recipe_id=OuterRef('id'))
                ),
                is_in_shopping_cart=Exists(
                    user.shoppingcartrelation.filter(recipe_id=OuterRef('id'))
                )
            )
        else:
            queryset = queryset.annotate(
                is_favorited=Value(False, output_field=BooleanField()),
                is_in_shopping_cart=Value(False, output_field=BooleanField())
            )
        return queryset

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        inst = get_object_or_404(Recipe, pk=pk)
        return Response({'short-link': reverse('short-link', kwargs={'pk': inst.short_link})})

    @action(detail=True, methods=['post', 'delete'], url_path='favorite')
    def favorite(self, request, pk=None):

        if request.method == 'POST':
            recipe = get_object_or_404(Recipe, pk=pk)
            favorite_serializer = FavoriteRelationSerializer(data={'user': request.user.pk, 'recipe': recipe.pk})
            favorite_serializer.is_valid(raise_exception=True)
            favorite_serializer.save()
            serializer = RecipeShortSerializer(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            deleted_count, _ = FavoriteRelation.objects.filter(user=request.user,
                                                               recipe_id=pk).delete()
            if deleted_count == 0:
                return Response(
                    {'detail': 'Рецепт не найден.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'], url_path='shopping_cart')
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            recipe = get_object_or_404(Recipe, pk=pk)
            shopping_cart_serializer = ShoppingCartSerializer(data={'user': request.user.pk, 'recipe': recipe.pk})
            shopping_cart_serializer.is_valid(raise_exception=True)
            shopping_cart_serializer.save()
            serializer = RecipeShortSerializer(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            deleted_count, _ = request.user.shoppingcartrelation.filter(recipe_id=pk).delete()
            if deleted_count == 0:
                return Response(
                    {'detail': 'Рецепт не найден.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='download_shopping_cart')
    def download_shopping_cart(self, request):
        ingredients = request.user.shoppingcartrelation.all().values(
            'recipe__recipe_ingredients__ingredient__name',
            'recipe__recipe_ingredients__ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('recipe__recipe_ingredients__amount')
        ).order_by('recipe__recipe_ingredients__ingredient__name')

        text_content = "Список покупок:\n\n"
        for item in ingredients:
            name = item['recipe__recipe_ingredients__ingredient__name']
            unit = item['recipe__recipe_ingredients__ingredient__measurement_unit']
            amount = item['total_amount']
            text_content += f"{name} - {amount} {unit}\n"

        return self._create_shopping_list_response(text_content)

    def _create_shopping_list_response(self, content):
        response = Response(content, content_type='text/plain', status=status.HTTP_200_OK)
        response['Content-Disposition'] = 'attachment; filename="shopping_list.txt"'
        return response


def view_short_link(request, pk):
    return redirect('recipes-detail', pk=get_object_or_404(Recipe, short_link=pk).pk)
