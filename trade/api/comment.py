from django.db.models import Avg
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST

from trade.exceptions import InvalidOrderByException, InvalidFilterException
from trade.file_util import s3_download_url
from trade.models.Comment import Order, Comment
from trade.models.Commodity import Commodity
from trade.models.status import ORDER_STATUS_CONFIRMED, ORDER_STATUS_COMMENTED
from trade.query_util import query_page, query_order_by, query_filter, filter_order_and_list
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, require_jwt, require_item_exist, require_keys, get_user


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"grade", "images"})
@require_item_exist(Order, "id", "query_id")
def comment_order(request: HttpRequest, query_id):
    """
    [POST] /api/order/comment/<int:query_id>
    """
    order = Order.objects.get(id=query_id)
    if get_user(request) != order.user:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    if order.status != ORDER_STATUS_CONFIRMED:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "订单状态出出错")
    order.status = ORDER_STATUS_COMMENTED
    order.save()
    data = parse_data(request)
    images = data["images"]
    filter_data(data, {"grade", "content"})
    data["order"] = order
    comment = Comment.objects.create(**data)
    for image_id in images:
        comment.image_set.add(image_id)
    return success_api_response({"id": comment.id})


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Comment, "id", "query_id")
def get_comment_detail(request: HttpRequest, query_id):
    """
    [GET] /api/comment/<int:query_id>
    """
    comment = Comment.objects.get(id=query_id)
    data = {
        "id": comment.id,
        "order_id": comment.order.id,
        "order__price": comment.order.price,
        "order__num": comment.order.num,
        "order__user_id": comment.order.user.id,
        "order__user__nickname": comment.order.user.nickname,
        "parameters": list(map(lambda x: x.description, comment.order.select_paras.all())),
        "grade": comment.grade,
        "content": comment.content,
        "comment_time": comment.comment_time,
        "image_urls": list(map(lambda x: s3_download_url(x.oss_token), comment.image_set.all())),
    }
    return success_api_response(data)


def comment_to_dict(comment: Comment) -> dict:
    data = {
        "id": comment.id,
        "order__user__nickname": comment.order.user.nickname,
        "grade": comment.grade,
        "content": comment.content,
        "comment_time": comment.comment_time,
        "parameters": list(map(lambda x: x.description, comment.order.select_paras.all())),
        "image_urls": list(map(lambda x: s3_download_url(x.oss_token), comment.image_set.all())),
        "user_image_url": None if comment.order.user.image is None else s3_download_url(
            comment.order.user.image.oss_token),
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Commodity, "id", "query_id")
@query_filter(fields=[("grade", int), ])
@query_order_by(fields=["id", "comment_time", "grade"])
@query_page(default=10)
def get_commodity_comment_list(request: HttpRequest, query_id, *args, **kwargs):
    """
    [GET] /api/commodity/comment/list/<int:query_id>
    """
    comments = Comment.objects.filter(order__commodity_id=query_id)
    try:
        data = filter_order_and_list(comments, comment_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


def get_commodity_avg_grade(commodity_id: int):
    comments = Comment.objects.filter(order__commodity_id=commodity_id)
    if not comments.exists():
        return None
    return comments.aggregate(Avg("grade"))["grade__avg"]


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Commodity, "id", "query_id")
def get_commodity_grade(request: HttpRequest, query_id):
    """
    [GET] /api/commodity/comment/avg_grade/<int:query_id>
    """
    avg = get_commodity_avg_grade(query_id)
    return success_api_response({"grade": avg})


def admin_comment_to_dict(comment: Comment) -> dict:
    data = {
        "id": comment.id,
        "order__user_id": comment.order.user.id,
        "order__user__nickname": comment.order.user.nickname,
        "order__commodity_id": comment.order.commodity.id,
        "order__commodity__name": comment.order.commodity.name,
        "order__commodity__shop_id": comment.order.commodity.shop.id,
        "order__commodity__shop__name": comment.order.commodity.shop.name,
        "grade": comment.grade,
        "comment_time": comment.comment_time,
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
@query_filter(fields=[("id", int), ("order__user_id", int), ("order__user__nickname", str),
                      ("order__commodity_id", int), ("order_commodity__name", str), ("order__commodity__shop_id", int),
                      ("order__commodity__shop__name", str), ("grade", int), ("comment_time", str)])
@query_order_by(fields=["id", "comment_time", "grade"])
@query_page(default=10)
def admin_get_comment_list(requestL: HttpRequest, *args, **kwargs):
    """
    [GET] /api/admin/comment/list
    """
    comments = Comment.objects.all()
    try:
        data = filter_order_and_list(comments, admin_comment_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)
