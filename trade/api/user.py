from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_http_methods

from trade.exceptions import InvalidOrderByException, InvalidFilterException
from trade.file_util import s3_download_url
from trade.models.Log import Log
from trade.models.User import User, ROLE_ADMIN, ROLE_NORMAL_USER
from trade.query_util import query_filter, query_order_by, query_page, filter_order_and_list
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, wrapped_api, require_jwt, require_item_exist, data_export, get_user


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(User, "id", "query_id")
def get_user_detail(request: HttpRequest, query_id):
    """
    [GET] /api/user/<int:query_id>
    """
    user = User.objects.get(id=query_id)
    data = {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "reg_time": user.reg_time,
        "phone_no": user.phone_no,
        "email": user.email,
        "signature": user.signature,
        "is_admin": user.role == ROLE_ADMIN,
        "student_id": None if user.student is None else user.student.id,
        "student__name": None if user.student is None else user.student.name,
        "img_url": None if user.image is None else s3_download_url(user.image.oss_token),
    }
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_item_exist(User, "id", "query_id")
def update_user_detail(request: HttpRequest, query_id):
    """
    [PUT] /api/user/<int:query_id>
    """
    data = parse_data(request)
    filter_data(data, {"nickname", "phone_no", "email", "signature"})
    if get_user(request).id != query_id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问")
    try:
        User.objects.filter(id=query_id).update(**data)
        Log.objects.create(user=get_user(request), detail="修改用户资料")
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, str(exception))


def user_to_dict(user: User) -> dict:
    data = {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "reg_time": user.reg_time,
        "phone_no": user.phone_no,
        "email": user.email,
        "role": user.role,
        "student_id": None if user.student is None else user.student.id,
        "valid": user.valid
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
@query_filter(fields=[("id", int), ("username", str), ("nickname", str), ("reg_time", str), ("phone_no", str),
                      ("email", str), ("student__id", str), ("student_id", str), ("role", int), ("valid", bool)])
@query_order_by(fields=["reg_time", "id", "student_id"])
@query_page(default=10)
def list_user(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/admin/user/list
    """
    users = User.objects.all()
    try:
        data = filter_order_and_list(users, user_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


def user_to_dict_export(user: User) -> dict:
    role_dict = {ROLE_ADMIN: "管理员", ROLE_NORMAL_USER: "普通用户"}
    data = {
        "用户ID": user.id,
        "登录用户名": user.username,
        "昵称": user.nickname,
        "注册时间": user.reg_time,
        "电话": user.phone_no,
        "邮箱": user.email,
        "角色": role_dict[user.role],
        "学号": None if user.student is None else user.student.id,
        "账号可用": user.valid
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
def export_user_list(request: HttpRequest):
    """
    [GET] /api/admin/user/list_csv
    """
    users = User.objects.all()
    columns = ["用户ID", "登录用户名", "昵称", "注册时间", "电话", "邮箱", "角色", "学号", "账号可用"]
    filename = "用户信息.csv"
    return data_export(query_set=users, columns=columns, model_to_dict=user_to_dict_export,
                       bom=request.GET.get("bom", None), filename=filename)


USER_DETAIL_API = wrapped_api({
    "GET": get_user_detail,
    "PUT": update_user_detail
})
