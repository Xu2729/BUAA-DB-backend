from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Avg
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from trade.exceptions import InvalidOrderByException, InvalidFilterException
from trade.file_util import s3_download_url
from trade.models.Log import Log
from trade.models.Comment import Comment
from trade.models.Shop import TYPE_PERSONAL, Shop
from trade.models.User import User
from trade.query_util import query_filter, query_order_by, query_page, filter_order_and_list
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, wrapped_api, require_jwt, require_item_exist, require_keys, get_user


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"type", "introduction", "name"})
def register_shop(request: HttpRequest):
    """
    [POST] /api/shop/register
    """
    user = get_user(request)
    if user.student is None:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "需要先进行学生认证才能开店")
    data = parse_data(request)
    filter_data(data, {"type", "introduction", "name"})
    data["owner"] = user
    shop = Shop.objects.create(**data)
    Log.objects.create(user=user, detail="用户注册店铺ID:{}".format(shop.id))
    return success_api_response({"id": shop.id})


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"student_id"})
@require_item_exist(Shop, "id", "query_id")
def add_shop_admin(request: HttpRequest, query_id):
    """
    [POST] /api/shop/shop_admin/<int:query_id>
    """
    user = get_user(request)
    shop = Shop.objects.get(id=query_id)
    if shop.owner.id != user.id:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "你不是店主，没有权限操作")
    if shop.type == TYPE_PERSONAL:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "个人店铺不能增加管理员")
    data = parse_data(request)
    try:
        new_admin = User.objects.get(student_id=data["student_id"])
        shop.admin.add(new_admin)
        shop.save()
        Log.objects.create(user=user, detail="店铺(ID:{})添加管理员ID:{}".format(shop.id, new_admin))
        return success_api_response()
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "用户不存在")


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
@require_keys({"student_id"})
@require_item_exist(Shop, "id", "query_id")
def delete_shop_admin(request: HttpRequest, query_id):
    """
    [DELETE] /api/shop/shop_admin/<int:query_id>
    """
    user = get_user(request)
    shop = Shop.objects.get(id=query_id)
    if shop.owner.id != user.id:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "你不是店主，没有权限操作")
    if shop.type == TYPE_PERSONAL:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "个人店铺不能删除管理员")
    data = parse_data(request)
    try:
        delete_admin = User.objects.get(student_id=data["student_id"])
        if not shop.admin.contains(delete_admin):
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不存在这个店铺管理员")
        shop.admin.remove(delete_admin)
        shop.save()
        Log.objects.create(user=user, detail="店铺(ID:{})添加管理员ID:{}".format(shop.id, delete_admin))
        return success_api_response()
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "用户不存在")


def user_info_to_dict(user: User) -> dict:
    data = {
        "id": user.id,
        "nickname": user.nickname,
        "student_id": None if user.student is None else user.student.id,
        "real_name": None if user.student is None else user.student.name,
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Shop, "id", "query_id")
def get_shop_detail(request: HttpRequest, query_id):
    """
    [GET] /api/shop/<int:query_id>
    """
    shop = Shop.objects.get(id=query_id)
    data = {
        "id": shop.id,
        "name": shop.name,
        "reg_time": shop.reg_time,
        "introduction": shop.introduction,
        "grade": get_shop_avg_grade(query_id),
        "type": shop.type,
        "owner": user_info_to_dict(shop.owner),
        "img_url": None if shop.image is None else s3_download_url(shop.image.oss_token),
    }
    if shop.type != TYPE_PERSONAL:
        data["admins"] = list(map(user_info_to_dict, shop.admin.all()))
    return success_api_response(data)


@response_wrapper
@require_jwt(need_valid=True)
@require_http_methods(["PUT"])
@require_keys({"introduction"})
@require_item_exist(Shop, "id", "query_id")
def update_shop_detail(request: HttpRequest, query_id):
    """
    [PUT] /api/shop/<int:query_id>
    """
    shop = Shop.objects.get(id=query_id)
    data = parse_data(request)
    filter_data(data, {"introduction"})
    user = get_user(request)
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    try:
        User.objects.filter(id=query_id).update(**data)
        Log.objects.create(user=user, detail="更新店铺信息ID:{}".format(shop.id))
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, str(exception))


def shop_to_dict(shop: Shop) -> dict:
    data = {
        "id": shop.id,
        "name": shop.name,
        "reg_time": shop.reg_time,
        "type": shop.type,
        "owner": user_info_to_dict(shop.owner),
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
@query_filter(fields=[("id", int), ("name", str), ("reg_time", str), ("type", int), ("owner__student__name", str),
                      ("owner__student_id", str), ("owner__student__id", str)])
@query_order_by(fields=["id", "reg_time", "owner__student_id"])
@query_page(default=10)
def list_shop(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/admin/shop/list
    """
    shops = Shop.objects.all()
    try:
        data = filter_order_and_list(shops, shop_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(User, "id", "query_id")
def list_user_shop(request: HttpRequest, query_id):
    """
    [GET] /api/shop/user_shop/<int:query_id>
    """
    user = User.objects.get(id=query_id)
    owner_shops = list(map(shop_to_dict, user.owner_shop.all()))
    admin_shops = list(map(shop_to_dict, user.admins_shop.all()))
    data = {
        "owner_shop": owner_shops,
        "admin_shop": admin_shops,
    }
    return success_api_response(data)


def get_shop_avg_grade(shop_id: int):
    comments = Comment.objects.filter(order__commodity__shop_id=shop_id)
    if not comments.exists():
        return None
    return comments.aggregate(Avg("grade"))["grade__avg"]


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Shop, "id", "query_id")
def get_shop_grade(request: HttpRequest, query_id):
    """
    [GET] /api/shop/avg_grade/<int:query_id>
    """
    avg = get_shop_avg_grade(query_id)
    return success_api_response({"grade": avg})


SHOP_DETAIL_API = wrapped_api({
    "GET": get_shop_detail,
    "PUT": update_shop_detail,
})

SHOP_ADMIN_API = wrapped_api({
    "POST": add_shop_admin,
    "DELETE": delete_shop_admin,
})
