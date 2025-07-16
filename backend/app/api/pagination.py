from ..constants import recipe_page_size
from rest_framework.pagination import PageNumberPagination


class RecipePagination(PageNumberPagination):
    page_size = recipe_page_size
    page_size_query_param = 'limit'
    max_page_size = 100
