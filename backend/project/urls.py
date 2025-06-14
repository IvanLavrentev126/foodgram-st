from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from app.views import MainUserViewSet, IngredientListAPIView, IngredientDetailAPIView, RecipeViewSet, view_short_link
from django.conf.urls.static import static

from project import settings

router = DefaultRouter()
router.register('', MainUserViewSet, basename='users')
router_secon = DefaultRouter()
router_secon.register('', RecipeViewSet, basename='recipes')
urlpatterns = [path('admin/', admin.site.urls),
               path('api/auth/', include('djoser.urls.authtoken')),
               path('api/users/', include(router.urls)),
               path('api/recipes/', include(router_secon.urls)),
               path('api/ingredients/<int:pk>/', IngredientDetailAPIView.as_view(), name='ingredient-detail'),
               path('api/ingredients/', IngredientListAPIView.as_view(), name='ingredient-list'),
               path('s/<str:pk>', view_short_link, name='short-link'),
               ] \
+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
