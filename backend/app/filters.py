from django.db.models import Exists, OuterRef
from django_filters import FilterSet, CharFilter, NumberFilter

from app.models import Recipe, Ingredient


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
            return Recipe.objects.filter(shopping_cart_recipe__user=user).annotate(
                is_favorited=Exists(
                    user.favorites.filter(recipe_id=OuterRef('id'))
                ),
                is_in_shopping_cart=Exists(
                    user.shopping_cart.filter(recipe_id=OuterRef('id'))
                )
            )
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return Recipe.objects.filter(favorites__user=user).annotate(
                is_favorited=Exists(
                    user.favorites.filter(recipe_id=OuterRef('id'))
                ),
                is_in_shopping_cart=Exists(
                    user.shopping_cart.filter(recipe_id=OuterRef('id'))
                )
            )
        return queryset


class IngredientFilter(FilterSet):
    name = CharFilter(lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ['name']
