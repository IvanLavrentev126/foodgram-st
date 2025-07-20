import base64
import logging
import uuid

from app.models import (
    FavoriteRelation,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCartRelation,
    Subscription,
)
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

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
        if self.context['request'].user.is_authenticated:
            return Subscription.objects.filter(sender=self.context['request'].user, to=obj).exists()
        return False


class AvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(required=True, allow_null=False, allow_blank=False)

    class Meta:
        model = User
        fields = ['avatar']

    def validate(self, data):
        if not data.get('avatar'):
            raise serializers.ValidationError("No avatar data provided")
        return data

    def update(self, instance, validated_data):
        avatar = validated_data.get('avatar')
        if ';base64,' in avatar:
            try:
                extension, avatar_data = avatar.split(';base64,')
                extension = extension.split("/")[-1]
                file_name = f"{uuid.uuid4()}.{extension}"
                file_content = ContentFile(base64.b64decode(avatar_data))
                instance.avatar.save(file_name, file_content)
            except Exception as e:
                raise ValidationError("Invalid avatar data format")
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


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        if self.context['request'].user.is_authenticated:
            return Subscription.objects.filter(sender=self.context['request'].user, to=obj).exists()
        return False


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
            'id', 'author', 'ingredients', 'is_favorited', 'is_in_shopping_cart', 'name', 'image', 'text',
            'cooking_time')


class RecipeIngredientWriteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField()


class BaseImageSerializerField(serializers.Field):
    def to_internal_value(self, data):
        try:
            format_, imgstr = data.split(';base64,')
            ext = format_.split('/')[-1]
            return ContentFile(base64.b64decode(imgstr), name=f'{uuid.uuid4()}.{ext}')
        except:
            raise serializers.ValidationError()


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientWriteSerializer(many=True)
    image = BaseImageSerializerField()

    class Meta:
        model = Recipe
        fields = ('ingredients', 'image', 'name', 'text', 'cooking_time')

    @transaction.atomic
    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        image = validated_data.pop('image')

        recipe = Recipe.objects.create(
            author=self.context['request'].user,
            image=image,
            **validated_data
        )
        self._add_ingredients(recipe, ingredients)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        self.partial = False
        if 'ingredients' not in validated_data:
            raise serializers.ValidationError
        ingredients = validated_data.pop('ingredients')
        RecipeIngredient.objects.filter(recipe=instance).delete()
        self._add_ingredients(instance, ingredients)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        user = self.context['request'].user
        instance.is_favorited = user.favoriterelation.filter(recipe=instance).exists()
        instance.is_in_shopping_cart = user.shoppingcartrelation.filter(recipe=instance).exists()
        return RecipeListSerializer(instance,
                                    context={'request': self.context['request']}).data

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError
        ingredients_list = []
        if len(value) < 1:
            raise serializers.ValidationError
        for ingredient in value:
            if not ingredient.get('id') or (ingredient['id'] in ingredients_list) or ingredient.get('amount', 0) < 1:
                raise serializers.ValidationError
            ingredients_list.append(ingredient['id'])
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
            raise ValidationError("Нельзя подписаться на самого себя")

        if request and request.method == 'POST':
            if Subscription.objects.filter(sender=sender, to=to).exists():
                raise ValidationError("Вы уже подписаны на этого пользователя")

        if request and request.method == 'DELETE':
            if not Subscription.objects.filter(sender=sender, to=to).exists():
                raise ValidationError("Вы не подписаны на этого пользователя")

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
        if self.context['request'].user.is_authenticated:
            return Subscription.objects.filter(sender=self.context['request'].user, to=obj).exists()
        return False

    def get_recipes(self, obj):
        recipes = obj.recipes.all()
        recipes_limit = self.context.get('request').query_params.get('recipes_limit') if self.context.get(
            'request') else None
        if recipes_limit and recipes_limit.isdigit():
            recipes = recipes[:int(recipes_limit)]
        serializer = RecipeShortSerializer(recipes, many=True, read_only=True, context=self.context)
        return serializer.data
