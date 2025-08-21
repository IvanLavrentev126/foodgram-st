from rest_framework.pagination import PageNumberPagination

from constants import recipe_max_page_size, recipe_page_size


class RecipePagination(PageNumberPagination):
    page_size = recipe_page_size
    page_size_query_param = 'limit'
    max_page_size = recipe_max_page_size
