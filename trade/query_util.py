import ast
from typing import List, Tuple, Type, Dict, Callable

from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import Model, Q, QuerySet
from django.http import HttpRequest

from trade.exceptions import InvalidFilterException, InvalidOrderByException
from trade.util import ErrorCode, failed_api_response, success_api_response


def query_filter(fields: List[Tuple[str, Type]], custom: Dict[str, Callable] = None):
    """parse filters in query string

    Args:
        fields (List[Tuple[str, Type]]): a list containing tuples of fields' name and types
        custom (List[str]): a list containing field names and corresponding handler

    Example of Usage:
        @response_wrapper
        @require_GET
        @query_filter(fields=[("student_id", str)])
        def list_items(request: HttpRequest, *args, **kwargs):
            item_filter = kwargs.get("filter")
            items = Model.objects.filter(student_filter)
            # wrap ...
            return data

    Query String:
        pattern: field__cmp=value
        example: name__exact, date__le, number__gt
        example uri: ?name__exact=abc&date__le=114514
            corresponding dict:
            {
                'name__exact': 'abc',
                'date__le': '114514'
            }
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            separator = "__"
            if custom is not None:
                custom_fields = custom.keys()
            else:
                custom_fields = []
            q_now = Q()
            query_dict = request.GET.dict()
            for field in fields:
                field_name = field[0]
                type_attr = field[1]
                query_set = [(key, query_dict.get(key))
                             for key in query_dict.keys() if key.startswith(field_name + separator)]
                for query in query_set:
                    key: str = query[0]
                    if type_attr is not str:
                        try:
                            value = type_attr(ast.literal_eval(query[1]))
                        except ValueError:
                            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                                       "Sorry, {} should be {}.".format(field_name, type_attr.__name__))
                    else:
                        value = query[1]
                    if field[0] in custom_fields:
                        item_filter = custom.get(field[0])(key, value)
                    else:
                        if key.endswith("ne"):
                            item_filter = ~Q(**{key[0:-2] + "exact": value})
                        else:
                            item_filter = Q(**{key: value})
                    q_now &= item_filter
            kwargs.update({"filter": q_now})
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def query_order_by(fields=List[str]):
    """parse order_by filter in query string
    '-' prefix means reverse.

    Example of Usage:
        @response_wrapper
        @require_GET
        @query_order_by(fields=["name"])
        def list_items(request: HttpRequest, *args, **kwargs):
            item_orders = kwargs.get("order_by")
            items = Model.objects.all()
            for item_order in item_orders:
                items = items.order_by(item_order)
            # wrap ...
            return data

    Query String:
        pattern: order_by=field
        example: order_by=name, order_by=-number
        example uri: ?order_by=name+date+-number
            corresponding dict:
            {
                'order_by': 'name date -number'
            }
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            allowed_fields: set = {""}
            for field in fields:
                allowed_fields.add(field)
                allowed_fields.add("-" + field)
            query_dict = request.GET.dict()
            order_by = query_dict.get("order_by")
            if order_by is None:
                return func(request, *args, **kwargs)
            order_by_values = order_by.split("*")
            for order_by_value in order_by_values:
                if order_by_value not in allowed_fields:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                               "Sorry, it is not valid to order by {}.".format(order_by_value))
            kwargs.update({"order_by": order_by_values})
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def query_page(default: int = 10):
    """parse page information in query string

    Args:
        default (int, optional): default value of page_size. Defaults to 10.

    Example of Usage:
        @response_wrapper
        @require_GET
        @query_page(default=20)
        def list_items(request: HttpRequest, *args, **kwargs):
            items = Model.objects.all()
            page = kwargs.get("page")
            page_size = kwargs.get("page_size")
            paginator = Paginator(items, page_size)
            page_all = paginator.num_pages
            total_count = paginator.count
            if page > page_all:
                return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                           "Sorry, max page number is {}.".format(page_all))
            data = {
                "total_count": total_count
                "page_all": num_pages,
                "page_now": page,
                "items":[...]
            }
            return success_api_response(data)

    Query String:
        pattern: page=int, page_size=int
        example: page=5&page_size=15, page=7, page_size=20
        example uri: ?page=1&page_size=114514
            corresponding dict:
            {
                'page': '1',
                'page_size': '114514'
            }
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            page = 1
            page_size = default
            query_dict = request.GET.dict()
            page_value = query_dict.get("page")
            if page_value is not None:
                try:
                    page = int(page_value)
                    if page <= 0:
                        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                                   "Sorry, page should be positive.")
                except ValueError:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                               "Sorry, page should be integer.")
            page_size_value = query_dict.get("page_size")
            if page_size_value is not None:
                try:
                    page_size = int(page_size_value)
                    if page_size <= 0:
                        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                                   "Sorry, page_size should be positive.")
                except ValueError:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                               "Sorry, page_size should be integer.")
            elif page_value is None:
                page_size = 10000000
            kwargs.update({
                "page": page,
                "page_size": page_size
            })
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def default_distinct_helper(request: HttpRequest, model: Model, distinct_field, *args, **kwargs):
    """
    Args:
        request (HttpRequest): [description]
        model (Model): [description]
        distinct_field ([type]): [description]
    """
    model_filter = kwargs.get("filter")
    if model_filter is None:
        model_instances = model.objects.all()
    else:
        try:
            model_instances = model.objects.filter(model_filter)
        except FieldError:
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                       "Unsupported Filter Method.")
    model_instances = model_instances.order_by(
        distinct_field).distinct(distinct_field)
    distinct_data = list(
        model_instances.values_list(distinct_field, flat=True))
    return_data = {distinct_field: distinct_data}
    return success_api_response(return_data)


def query_distinct(fields: List[str], model: Model = None, func=None):
    """parse distinct information in query string
    The result will be filtered first.
    ** NEVER use it before query_filter **

    Args:
        fields (List[str]): valid field names
        model (Model): model for default distinct helper function
        func (Callable): custom callable object to deal with distinct query

    Example of Usage:
        @response_wrapper
        @require_GET
        @query_filter(fields)
        @query_distinct(fields=["field"],func=model_distinct_helper)
        def list_items(request: HttpRequest, *args, **kwargs):
            pass

        def model_distinct_helper(request: HttpRequest, distinct_field, *args, *kwargs):
            distinct_instances = model.objects.order_by(distinct_field).distinct(distinct_field)
            distinct_data = list(distinct_instances.values_list(distinct_field,flat=True))
            return success_api_response(distinct_data)

    Query String:
        pattern: distinct=field
        example: distinct=department
        example uri: ?name__eq=abc&distinct=department
            corresponding dict:
            {
                'name__eq': 'abc', // will be parsed as filter
                'distinct': 'department' // will be parsed as distinct query
            }
    """

    def decorator(function):
        def wrapper(request: HttpRequest, *args, **kwargs):
            query_dict = request.GET.dict()
            query_value = query_dict.get("distinct")
            if query_value is None:
                return function(request, *args, **kwargs)
            distinct_value = query_value
            if distinct_value not in fields:
                return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS,
                                           "Sorry, distinct value \"{}\" is not valid.".format(distinct_value))
            if func is None:
                return default_distinct_helper(request, model, distinct_value, *args, **kwargs)
            return func(request, distinct_value, *args, **kwargs)

        return wrapper

    return decorator


def filter_order_and_list(query_set: QuerySet, model_to_dict, **kwargs) -> dict:
    """
    filter and order a query_set and return the given page data
    :param query_set: query set needed to filter and order
    :param model_to_dict: a function to map model to dict
    :param kwargs: kwargs from origin function
    :return: a data dict
    """
    my_filter = kwargs.get("filter")
    tot_count = query_set.count()
    try:
        query_set = query_set.filter(my_filter)
    except FieldError:
        raise InvalidFilterException() from FieldError
    filter_count = query_set.count()
    order_by = kwargs.get("order_by")
    try:
        if order_by is not None:
            query_set = query_set.order_by(*order_by)
        else:
            query_set = query_set.order_by("-id")
    except FieldError:
        raise InvalidOrderByException() from FieldError
    page = kwargs.get("page")
    page_size = kwargs.get("page_size")
    paginator = Paginator(query_set, page_size)
    page_all = paginator.num_pages
    if page > page_all:
        data_list = []
    else:
        data_list = list(map(model_to_dict, paginator.get_page(page).object_list))
    data = {
        "tot_count": tot_count,
        "filter_count": filter_count,
        "page_all": page_all,
        "page": page,
        "data": data_list
    }
    return data
