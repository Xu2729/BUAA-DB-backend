import json
import random
from datetime import datetime
from enum import unique, Enum

import jwt
from django.core.mail import send_mail
from django.db import models
from django.db.models import QuerySet
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.utils.encoding import escape_uri_path
from django.views.decorators.http import require_http_methods
from pandas import DataFrame

from DBProject import settings
from DBProject.settings import EMAIL_HOST_USER, PASSWORD_CHAR_SET
from trade.models.User import ROLE_ADMIN, User


@unique
class ErrorCode(Enum):
    """
    api error code enumeration
    """
    SUCCESS_CODE = 200_00
    BAD_REQUEST_ERROR = 400_00
    INVALID_REQUEST_ARGUMENT_ERROR = 400_01
    INVALID_REQUEST_ARGS = 400_02
    REFUSE_ACCESS_ERROR = 403_00
    NOT_FOUND_ERROR = 404_00
    ITEM_NOT_FOUND_ERROR = 404_01
    ITEM_ALREADY_EXIST_ERROR = 404_02
    DUPLICATED_ERROR = 409_00


def _api_response(success, data) -> dict:
    return {'success': success, 'data': data}


def success_api_response(data=None) -> dict:
    """
    wrap a success response dict obj
    :param data: requested data
    :return: an api response dictionary
    """
    if data is None:
        data = {"success": True}
    return _api_response(True, data)


def failed_api_response(code, error_msg=None) -> dict:
    """
    wrap an failed response dict obj
    :param code: error code, refers to ErrorCode, can be an integer or a str (error name)
    :param error_msg: external error information
    :return: an api response dictionary
    """
    if isinstance(code, str):
        code = ErrorCode[code]
    elif isinstance(code, int):
        code = ErrorCode(code)
    if error_msg is None:
        error_msg = str(code)
    else:
        error_msg = str(code) + ': ' + error_msg
    status_code = code.value // 100
    detailed_code = code.value
    return _api_response(
        success=False,
        data={
            'code': status_code,
            'detailed_error_code': detailed_code,
            'error_msg': error_msg
        })


def response_wrapper(func):
    """
    decorate a given api-function, parse its return value from a dict to a HttpResponse
    :param func: an api-function
    :return: wrapped function
    """

    def _inner(*args, **kwargs):
        _response = func(*args, **kwargs)
        if isinstance(_response, dict):
            if _response['success']:
                _response = JsonResponse(_response['data'])
            else:
                status_code = _response.get("data").get("code")
                _response = JsonResponse(_response['data'])
                _response.status_code = status_code
        return _response

    return _inner


# pylint:disable=R0911
def require_jwt(admin=False, need_valid=False):
    """
    decorator to varify the request jwt token
    :param need_valid: need user valid
    :param admin: need admin authority
    :return: wrapped function
    """

    def decorator(view_func):
        def _wrapped_view(request: HttpRequest, *args, **kwargs):
            try:
                auth = request.META.get('HTTP_AUTHORIZATION').split(" ")
                if len(auth) != 2:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "无效的token")
            except AttributeError:
                return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "缺少AUTHORIZATION头")

            if auth[0] == "Bearer":
                try:
                    dic = jwt.decode(auth[1], settings.SECRET_KEY, algorithms='HS256')
                    username = dic.get("username", None)
                    role = dic.get("role", None)
                    valid = dic.get("valid", False)
                except jwt.ExpiredSignatureError:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "Token过期")
                except jwt.InvalidTokenError:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "无效的token")

                if username is None or role is None or valid is None:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "无效的token")

                if admin and role != ROLE_ADMIN:
                    return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "需要管理员权限")
                if need_valid and not valid:
                    return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "账号封禁中，无法进行该操作")

                return view_func(request, *args, **kwargs)
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "错误的AUTHORIZATION头")

        return _wrapped_view

    return decorator


def validate_request(func):
    """
    decorator to validate request with func
    :param func: check function
    :return: wrapped function
    """

    def decorator(function):
        def wrapper(request: HttpRequest, *args, **kwargs):
            if func(request):
                return function(request, *args, **kwargs)
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "不合法的请求")

        return wrapper

    return decorator


def require_item_exist(model: models.Model, field: str, item: str):
    """
    decorator to check if the query item exist
    :param model: query model
    :param field: query model field
    :param item: request filed (defined in urls.py)
    :return: wrapped function
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            item_id = kwargs.get(item)
            kwargs.pop(item, None)
            if not model.objects.filter(**{field: item_id}).exists():
                return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "对象不存在")
            return func(request, item_id, *args, **kwargs)

        return wrapper

    return decorator


def require_item_miss(model: models.Model, field: str, item: str):
    """
    decorator to check if the query item not exist
    :param model: query model
    :param field: query model field
    :param item: request filed (defined in urls.py)
    :return: wrapped function
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            item_id = kwargs.get(item)
            kwargs.pop(item, None)
            if model.objects.filter(**{field: item_id}).exists():
                return failed_api_response(ErrorCode.ITEM_ALREADY_EXIST_ERROR, "对象已存在")
            return func(request, item_id, *args, **kwargs)

        return wrapper

    return decorator


def parse_data(request: HttpRequest):
    """
    parse request body and return a dict
    :param request: HttpRequest
    :return: request body dict if success else None
    """
    try:
        return json.loads(request.body.decode())
    except json.JSONDecodeError:
        return None


def require_keys(key_set: set):
    """
    decorator to check if request body contain keys
    :param key_set: key set
    :return: wrapped function
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            data = parse_data(request)
            if data is None:
                return failed_api_response(ErrorCode.BAD_REQUEST_ERROR)
            for key in key_set:
                if data.get(key, None) is None:
                    return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "缺少必要字段")
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def filter_data(data: dict, key_set: set) -> None:
    """
    pop key-value from the data whose key not in key_set
    :param data: origin dict
    :param key_set: key set
    :return: None
    """
    remove_keys: set = set()
    for key in data.keys():
        if key not in key_set:
            remove_keys.add(key)
    for key in remove_keys:
        data.pop(key, None)


def wrapped_api(api_dict: dict):
    """
    wrap apis together with 4 methods(get/post/put/delete)
    :param api_dict: dict as {'get': get_api, 'post': post_api ...}
    :return: an api
    """
    assert isinstance(api_dict, dict)
    api_dict = {k.upper(): v for k, v in api_dict.items()}
    assert set(api_dict.keys()).issubset(['GET', 'POST', 'PUT', 'DELETE'])

    @require_http_methods(api_dict.keys())
    def _api(request, *args, **kwargs):
        return api_dict[request.method](request, *args, **kwargs)

    return _api


def get_user(request: HttpRequest) -> User:
    """
    parse request token and return user
    :param request: HttpRequest
    :return: user
    """
    auth = request.META.get('HTTP_AUTHORIZATION').split(" ")
    dic = jwt.decode(auth[1], settings.SECRET_KEY, algorithms='HS256')
    username = dic.get("username", None)
    user = User.objects.get(username=username)
    return user


def data_export(query_set: QuerySet, columns: list[str], model_to_dict, bom: bool, filename: str) -> HttpResponse:
    """
    export data to csv and return response
    :param query_set: data to export
    :param columns: export csv header
    :param model_to_dict: function to parse model to dict
    :param bom: csv file has bom or not
    :param filename: filename
    :return: HttpResponse
    """
    records = {}
    for model in query_set:
        records[model.id] = model_to_dict(model)
    df = DataFrame.from_dict(records, columns=columns, orient="index")
    if bom:
        response = HttpResponse(df.to_csv(quoting=None, index=False, encoding="utf-8-sig"), charset="utf-8-sig")
    else:
        response = HttpResponse(df.to_csv(quoting=None, index=False, encoding="utf-8"))
    response["Content-Type"] = "application/octet-stream"
    response["Content-Disposition"] = "attachment;filename*=utf-8''{}".format(escape_uri_path(filename))
    return response


def make_random_password(length: int) -> str:
    """
    randomly generate passwords of length
    :param length: password length
    :return: random password
    """
    random.seed(int(datetime.utcnow().timestamp() * 1000))
    pwd = PASSWORD_CHAR_SET[random.randint(0, 61)]
    l = len(PASSWORD_CHAR_SET)
    for _ in range(length - 1):
        pwd += PASSWORD_CHAR_SET[random.randint(0, l - 1)]
    return pwd


def send_email(title: str, content: str, to_email: str) -> bool:
    """
    send email
    :param title: title
    :param content: content
    :param to_email: receiver email
    :return: success
    """
    try:
        send_mail(
            subject=title,
            message=content,
            from_email=EMAIL_HOST_USER,
            recipient_list=[to_email, ],
            fail_silently=False
        )
    except Exception as exception:
        print(exception)
        return False
    return True
