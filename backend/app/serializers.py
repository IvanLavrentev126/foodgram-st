import base64
import uuid

from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from rest_framework.exceptions import PermissionDenied
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers
from app.models import Recipe, RecipeIngredient, FavoriteRelation, ShoppingCartRelation, Ingredient, SubscriptionRelation
from django.db import transaction

User = get_user_model()


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
            return SubscriptionRelation.objects.filter(sender=self.context['request'].user, to=obj).exists()
        return False


class AvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('avatar',)


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
            return SubscriptionRelation.objects.filter(sender=self.context['request'].user, to=obj).exists()
        return False


class RecipeListSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    ingredients = IngredientRecipeSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'ingredients', 'is_favorited', 'is_in_shopping_cart', 'name', 'image', 'text',
            'cooking_time')

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        return user.favorites.filter(recipe=obj).exists() if not user.is_anonymous else False

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        return user.shopping_cart.filter(recipe=obj).exists() if not user.is_anonymous else False


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
    cooking_time = serializers.IntegerField()

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
        if instance.author != self.context['request'].user:
            raise PermissionDenied()
        if 'ingredients' not in validated_data:
            raise serializers.ValidationError()
        ingredients = validated_data.pop('ingredients')
        RecipeIngredient.objects.filter(recipe=instance).delete()
        self._add_ingredients(instance, ingredients)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        return RecipeListSerializer(instance,
                                    context={'request': self.context['request']}).data

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError
        ingredients_list = []
        for ingredient in value:
            if not ingredient.get('id') or (ingredient['id'] in ingredients_list):
                raise serializers.ValidationError
            else:
                ingredients_list.append(ingredient['id'])
        return value

    def _add_ingredients(self, recipe, ingredients):
        for ingredient in ingredients:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            )


class RecipeShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCartRelation
        fields = ('user', 'recipe')

    def to_representation(self, instance):
        return RecipeShortSerializer(instance.recipe,
                                     context={'request': self.context['request']}).data


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteRelation
        fields = ('user', 'recipe')

    def to_representation(self, instance):
        return RecipeShortSerializer(instance.recipe,
                                     context={'request': self.context['request']}).data


class SubscribedSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = RecipeShortSerializer(many=True, read_only=True)
    recipes_count = serializers.IntegerField(source='recipes.count', read_only=True)

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'recipes', 'recipes_count', 'avatar'
        )

    def get_is_subscribed(self, obj):
        if self.context['request'].user.is_authenticated:
            return SubscriptionRelation.objects.filter(sender=self.context['request'].user, to=obj).exists()
        return False
