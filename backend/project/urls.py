from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from api.urls import api_urls
from api.views import view_short_link

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api_urls)),
    path('s/<str:pk>', view_short_link, name='short-link'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
