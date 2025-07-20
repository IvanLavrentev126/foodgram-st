from api.views import IngredientViewSet, MainUserViewSet, RecipeViewSet
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('users', MainUserViewSet, basename='users')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('ingredients', IngredientViewSet, basename='ingredients')

api_urls = [
    path('auth/', include('djoser.urls.authtoken')),
    path('', include(router.urls)),
]
