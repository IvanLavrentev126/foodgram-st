from django.contrib import admin
from django.contrib.auth import get_user_model

from app.models import Ingredient, Recipe, RecipeIngredient, FavoriteRelation, ShoppingCartRelation

User = get_user_model()
admin.site.register(User)
admin.site.register(Ingredient)
admin.site.register(Recipe)
admin.site.register(RecipeIngredient)
admin.site.register(FavoriteRelation)
admin.site.register(ShoppingCartRelation)
