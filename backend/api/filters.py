from app.models import Ingredient, Recipe
from django_filters import CharFilter, FilterSet, NumberFilter


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
            return queryset.filter(shoppingcartrelation__user=user)
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(favoriterelation__user=user)
        return queryset


class IngredientFilter(FilterSet):
    name = CharFilter(lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ['name']
