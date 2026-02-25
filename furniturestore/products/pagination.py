from rest_framework.pagination import PageNumberPagination


class Pagination10(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class Pagination20(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
class Pagination30(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100
