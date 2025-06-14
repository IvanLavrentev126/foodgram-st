import random
import string
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import models


def create_random_string(length=8):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    avatar = models.ImageField(null=True, blank=True)
    REQUIRED_FIELDS = ('username',)
    USERNAME_FIELD = 'email'


User = get_user_model()


class SubscriptionRelation(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sub_sender')
    to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sub_to')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['sender', 'to'], name='unique_sub')]


class Ingredient(models.Model):
    name = models.CharField(max_length=128, verbose_name='Название')
    measurement_unit = models.CharField(max_length=64, verbose_name='Единица измерения')


class Recipe(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipes')
    name = models.CharField(max_length=256)
    image = models.ImageField()
    text = models.TextField()
    cooking_time = models.PositiveSmallIntegerField()
    ingredients = models.ManyToManyField('Ingredient', through='RecipeIngredient', related_name='recipes')
    pub_date = models.DateTimeField(auto_now_add=True)


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='recipe_ingredients')
    ingredient = models.ForeignKey('Ingredient', on_delete=models.CASCADE, related_name='recipe_ingredients')
    amount = models.PositiveSmallIntegerField()


class FavoriteRelation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='favorites')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'recipe'], name='unique_favorite')]


class ShoppingCartRelation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shopping_cart')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='shopping_cart_recipe')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'recipe'], name='unique_shopping_cart')]


class ShortLink(models.Model):
    id = models.CharField(max_length=8, primary_key=True, default=create_random_string)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
