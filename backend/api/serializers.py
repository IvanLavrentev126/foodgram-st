import base64
import logging
import uuid

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

from app.models import (
    FavoriteRelation,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCartRelation,
    Subscription,
)
from constants import subscribed_user_recipe_limit

User = get_user_model()

logger = logging.getLogger(__name__)


class CustomUserCreateSerializer(UserCreateSerializer):
    email = serializers.EmailField(required=True, validators=[UniqueValidator(queryset=User.objects.all())])

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'password', 'username', 'first_name', 'last_name')


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'avatar', 'is_subscribed')

    def get_is_subscribed(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and user.sender.filter(to=obj).exists()


class AvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(required=True, allow_null=False, allow_blank=False)

    class Meta:
        model = User
        fields = ['avatar']

    def validate(self, data):
        if not data.get('avatar'):
            raise serializers.ValidationError('No avatar data provided')
        return data

    def update(self, instance, validated_data):
        avatar = validated_data.get('avatar')
        if ';base64,' in avatar:
            try:
                extension, avatar_data = avatar.split(';base64,')
                extension = extension.split('/')[-1]
                file_name = f'{uuid.uuid4()}.{extension}'
                file_content = ContentFile(base64.b64decode(avatar_data))
                instance.avatar.save(file_name, file_content)
            except Exception:
                raise ValidationError('Invalid avatar data format')
        else:
            instance.avatar = avatar
            instance.save()
        return instance


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientRecipeSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeListSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    ingredients = IngredientRecipeSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True
    )
    is_favorited = serializers.BooleanField(read_only=True)
    is_in_shopping_cart = serializers.BooleanField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart', 'name',
            'image', 'text', 'cooking_time'
        )


class RecipeIngredientWriteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField()


class BaseImageSerializerField(serializers.Field):
    def to_internal_value(self, data):
        try:
            format_, imgstr = data.split(';base64,')
            ext = format_.split('/')[-1]
            return ContentFile(base64.b64decode(imgstr), name=f'{uuid.uuid4()}.{ext}')
        except Exception:
            raise serializers.ValidationError()


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientWriteSerializer(many=True, required=True, allow_empty=False)
    image = BaseImageSerializerField()

    class Meta:
        model = Recipe
        fields = ('ingredients', 'image', 'name', 'text', 'cooking_time')

    @transaction.atomic
    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        image = validated_data.pop('image', None)

        recipe = super().create({
            **validated_data,
            'author': self.context['request'].user,
            'image': image
        })

        self._add_ingredients(recipe, ingredients)

        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        # здесь можно проверку добавить, чтобы тест не падал, но он некорректный
        ingredients = validated_data.pop('ingredients')
        RecipeIngredient.objects.filter(recipe=instance).delete()
        self._add_ingredients(instance, ingredients)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        user = self.context['request'].user
        instance.is_favorited = user.favoriterelation.filter(recipe=instance).exists()
        instance.is_in_shopping_cart = user.shoppingcartrelation.filter(recipe=instance).exists()
        return RecipeListSerializer(
            instance,
            context={'request': self.context['request']}
        ).data

    def validate_ingredients(self, value):
        if not value or len(value) < 1:
            raise serializers.ValidationError('Ингредиенты не могут быть пустыми')

        ingredients_list = set()
        for ingredient in value:
            if not ingredient.get('id'):
                raise serializers.ValidationError('ID ингредиента обязателен')
            if ingredient['id'] in ingredients_list:
                raise serializers.ValidationError('Ингредиенты не должны повторяться')
            if ingredient.get('amount', 0) < 1:
                raise serializers.ValidationError('Количество ингредиента должно быть больше 0')
            ingredients_list.add(ingredient['id'])
        return value

    def _add_ingredients(self, recipe, ingredients):
        recipe_ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            )
            for ingredient in ingredients
        ]
        RecipeIngredient.objects.bulk_create(recipe_ingredients)


class RecipeShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCartRelation
        fields = ['user', 'recipe']

    def validate(self, data):
        user = data['user']
        recipe = data['recipe']
        if ShoppingCartRelation.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError('Рецепт уже добавлен в корзину.')
        return data

    def to_representation(self, instance):
        return RecipeShortSerializer(
            instance.recipe,
            context={'request': self.context['request']}).data


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ('sender', 'to')

    def validate(self, data):
        request = self.context.get('request')
        sender = data.get('sender')
        to = data.get('to')

        if sender == to:
            raise ValidationError('Нельзя подписаться на самого себя')

        if request and request.method == 'POST':
            if Subscription.objects.filter(sender=sender, to=to).exists():
                raise ValidationError('Вы уже подписаны на этого пользователя')

        if request and request.method == 'DELETE':
            if not Subscription.objects.filter(sender=sender, to=to).exists():
                raise ValidationError('Вы не подписаны на этого пользователя')

        return data


class FavoriteRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteRelation
        fields = ['user', 'recipe']

    def validate(self, data):
        user = data['user']
        recipe = data['recipe']
        if FavoriteRelation.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError('Рецепт уже добавлен в избранное.')
        return data

    def to_representation(self, instance):
        return RecipeShortSerializer(instance.recipe,
                                     context={'request': self.context['request']}).data


class SubscribedSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'recipes', 'recipes_count', 'avatar'
        )

    def get_is_subscribed(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and user.sender.filter(to=obj).exists()

    def get_recipes(self, obj):
        limit = self.context['request'].query_params.get('recipes_limit', subscribed_user_recipe_limit)
        if isinstance(limit, str):
            if not limit.isdigit():
                limit = subscribed_user_recipe_limit
            limit = int(limit)
        recipes = obj.recipes.all()[:limit]
        return RecipeShortSerializer(recipes, many=True, context=self.context).data
