import base64
import uuid

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django_filters import FilterSet, CharFilter, NumberFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from djoser.views import UserViewSet
from djoser.conf import settings

from app.models import ShortLink, Recipe, FavoriteRelation, ShoppingCartRelation, Ingredient, SubscriptionRelation
from app.serializers import (
    AvatarSerializer,
    CustomUserCreateSerializer,
    SubscribedSerializer,
    RecipeListSerializer,
    RecipeCreateUpdateSerializer,
    RecipeShortSerializer,
    IngredientSerializer
)

User = get_user_model()


class MainUserViewSet(UserViewSet):
    pagination_class = LimitOffsetPagination

    @action(detail=False, methods=['get'], url_path='subscriptions')
    def subscriptions(self, request):
        subscriptions = SubscriptionRelation.objects.filter(sender=request.user)
        page = self.paginate_queryset([sub.to for sub in subscriptions])
        if page != 0:
            serializer = SubscribedSerializer(page,
                                              many=True,
                                              context={'request': request})
            return self.get_paginated_response(serializer.data)
        else:
            serializer = SubscribedSerializer([sub.to for sub in subscriptions],
                                              many=True,
                                              context={'request': request})
            return Response(serializer.data)

    @action(detail=True, methods=['post', 'delete'], url_path='subscribe')
    def subscribe(self, request, id=None):
        user_to_follow = get_object_or_404(User, pk=id)
        current_user = request.user
        if not current_user.is_authenticated:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if request.method == 'POST':
            if current_user == user_to_follow:
                return Response(status=status.HTTP_409_CONFLICT)
            if SubscriptionRelation.objects.filter(sender=current_user, to=user_to_follow).exists():
                return Response(status=status.HTTP_208_ALREADY_REPORTED)
            SubscriptionRelation.objects.create(sender=current_user, to=user_to_follow)
            serializer = SubscribedSerializer(user_to_follow, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        if request.method == 'DELETE':
            follow_relation = SubscriptionRelation.objects.filter(sender=current_user, to=user_to_follow)
            if not follow_relation.exists():
                return Response(status=status.HTTP_404_NOT_FOUND)
            follow_relation.delete()
            return Response(status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = CustomUserCreateSerializer(request.user, context={'request': request})
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

    @action(detail=False, methods=['post'], url_path='set_password', permission_classes=[IsAuthenticated])
    def set_password(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        serializer = settings.SERIALIZERS.set_password(data=request.user.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(serializer.data["new_password"])
        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipePagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = 'limit'
    max_page_size = 100


class RecipeFilter(FilterSet):
    author = NumberFilter(field_name='author__id')
    is_in_shopping_cart = NumberFilter(method='filter_is_in_shopping_cart')
    is_favorited = NumberFilter(method='filter_is_favorited')

    class Meta:
        model = Recipe
        fields = ['author']

    def filter_is_in_shopping_cart(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(shopping_cart_recipe__user=user)
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(favorites__user=user)
        return queryset


class IngredientFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Ingredient
        fields = ['name']


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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_serializer_class(self):
        return RecipeListSerializer if self.action.lower() == 'get' else RecipeCreateUpdateSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, mees, pk=None):
        inst = ShortLink.objects.create(recipe_id=pk)
        return Response({'short-link': reverse('short-link', kwargs={'pk': inst.id})})

    @action(detail=True, methods=['post', 'delete'], url_path='favorite')
    def favorite(self, request, pk=None):
        recipe = Recipe.objects.get(pk=pk)
        if request.method == 'DELETE':
            favorite = request.user.favorites.filter(recipe=recipe).first()
            if not favorite:
                return Response({'error': 'Recipe not in favorites'}, status=status.HTTP_400_BAD_REQUEST)
            favorite.delete()
            return Response(status=status.HTTP_200_OK)
        if request.method == 'POST':
            obj, created = FavoriteRelation.objects.get_or_create(user=request.user, recipe=recipe)
            if not created:
                return Response({'error': 'Recipe already in favorites'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = RecipeShortSerializer(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post', 'delete'], url_path='shopping_cart')
    def shopping_cart(self, request, pk=None):
        recipe = Recipe.objects.get(pk=pk)
        if request.method == 'DELETE':
            deleted_count, _ = request.user.shopping_cart.filter(recipe=recipe).delete()
            if deleted_count == 0:
                return Response({'error': 'Recipe not in shopping cart'}, status=status.HTTP_400_BAD_REQUEST)
            return Response(status=status.HTTP_200_OK)
        if request.method == 'POST':
            obj, created = ShoppingCartRelation.objects.get_or_create(user=request.user, recipe=recipe)
            if not created:
                return Response({'error': 'Recipe already in shopping cart'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = RecipeShortSerializer(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)


def view_short_link(request, pk):
    return redirect('recipes-detail', pk=ShortLink.objects.get(recipe_id=pk).id)
