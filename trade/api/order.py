from django.db import connection
from django.http import HttpRequest
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from trade.exceptions import InvalidOrderByException, InvalidFilterException
from trade.file_util import s3_download_url
from trade.models.Comment import Order
from trade.models.Commodity import Commodity
from trade.models.Log import Log
from trade.models.Parameter import Parameter
from trade.models.Shop import Shop
from trade.models.status import ORDER_STATUS_ORDERED, ORDER_STATUS_PAID, ORDER_STATUS_DELIVERED, \
    ORDER_STATUS_CONFIRMED, ORDER_STATUS_DICT, COMM_STATUS_CLOSED, COMM_STATUS_ON_SELL
from trade.query_util import query_page, query_order_by, query_filter, filter_order_and_list
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, require_jwt, require_item_exist, require_keys, get_user, data_export


def get_comm_para_price(comm: Commodity, para_list: list[int]) -> float:
    base_price = comm.price - comm.discount
    for para_id in para_list:
        base_price += Parameter.objects.get(id=para_id).add
    return float(base_price)


def check_paras(para_list: list[int]) -> bool:
    for para_id in para_list:
        if not Parameter.objects.filter(id=para_id).exists():
            return False
    return True


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"num", "select_paras"})
@require_item_exist(Commodity, "id", "query_id")
def create_order(request: HttpRequest, query_id):
    """
    [POST] /api/order/new/<int:query_id>
    这里使用了函数 create_order
    """
    user = get_user(request)
    comm = Commodity.objects.get(id=query_id)
    data = parse_data(request)
    filter_data(data, {"num", "select_paras", "address", "note"})
    check_paras(data["select_paras"])
    data["price"] = get_comm_para_price(comm, data["select_paras"]) * data["num"]
    select_paras = data["select_paras"]
    del data["select_paras"]
    data["user"] = user
    data["commodity"] = comm
    # 检查下数据会不会爆 Decimal(8, 2)
    if data["price"] > 88888888.88:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "非法订单")
    with connection.cursor() as cursor:
        cursor.execute("select create_order(%s,%s,%s,%s,%s,%s)",
                       [user.id, comm.id, data["num"], data["price"],
                        None if data.get("address", None) is None else data["address"],
                        None if data.get("note", None) is None else data["note"]])
        ret = cursor.fetchall()[0][0]
    if ret == 0:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "很抱歉，该商品被抢光了")
    order = Order.objects.get(id=ret)
    for para_id in select_paras:
        order.select_paras.add(para_id)
    if comm.sale >= comm.total and comm.status != COMM_STATUS_CLOSED:
        comm.status = COMM_STATUS_CLOSED
        comm.save()
    return success_api_response({"id": order.id})


def brief_para_to_dict(para: Parameter) -> dict:
    data = {
        "id": para.id,
        "description": para.description,
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Order, "id", "query_id")
def get_order_detail(request: HttpRequest, query_id):
    """
    [GET] /api/order/<int:query_id>
    """
    order = Order.objects.get(id=query_id)
    data = {
        "id": order.id,
        "user_id": order.user.id,
        "user__nickname": order.user.nickname,
        "commodity_id": order.commodity.id,
        "commodity__name": order.commodity.name,
        "commodity__price": order.commodity.price - order.commodity.discount,
        "commodity__shop_id": order.commodity.shop.id,
        "commodity__shop__name": order.commodity.name,
        "num": order.num,
        "price": order.price,
        "address": order.address,
        "status": order.status,
        "start_time": order.start_time,
        "pay_time": order.pay_time,
        "deliver_time": order.deliver_time,
        "confirm_time": order.confirm_time,
        "close_time": order.close_time,
        "image_url": s3_download_url(order.commodity.image.oss_token),
        "select_paras": list(map(brief_para_to_dict, order.select_paras.all())),
        "note": order.note,
    }
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_keys({"address"})
@require_item_exist(Order, "id", "query_id")
def update_order_address(request: HttpRequest, query_id):
    """
    [PUT] /api/order/address/<int:query_id>
    """
    data = parse_data(request)
    user = get_user(request)
    if user != Order.objects.get(id=query_id).user:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    filter_data(data, {"address"})
    try:
        Order.objects.filter(id=query_id).update(**data)
        Log.objects.create(user=user, detail="修改订单地址ID:{}".format(query_id))
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, str(exception))


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Order, "id", "query_id")
def close_order(request: HttpRequest, query_id):
    """
    [POST] /api/order/close/<int:query_id>
    这里使用了存储过程 close_order
    """
    order = Order.objects.get(id=query_id)
    if get_user(request) != order.user:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    if order.status != ORDER_STATUS_ORDERED:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "订单关闭失败")
    with connection.cursor() as cursor:
        cursor.execute("call close_order(%s);", [query_id, ])
    if order.commodity.sale < order.commodity.total and order.commodity.status == COMM_STATUS_CLOSED:
        order.commodity.status = COMM_STATUS_ON_SELL
        order.commodity.save()
    Log.objects.create(user=get_user(request), detail="用户关闭订单ID:{}".format(query_id))
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Order, "id", "query_id")
def pay_order(request: HttpRequest, query_id):
    """
    [POST] /api/order/pay/<int:query_id>
    """
    order = Order.objects.get(id=query_id)
    if get_user(request) != order.user:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    if order.status != ORDER_STATUS_ORDERED:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "订单状态出出错")
    order.status = ORDER_STATUS_PAID
    order.pay_time = timezone.now()
    order.save()
    Log.objects.create(user=get_user(request), detail="支付订单ID:{}".format(query_id))
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Order, "id", "query_id")
def deliver_order(request: HttpRequest, query_id):
    """
    [POST] /api/order/deliver/<int:query_id>
    """
    order = Order.objects.get(id=query_id)
    shop = order.commodity.shop
    user = get_user(request)
    if user != shop.owner and not shop.admin.contains(user):
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    if order.status != ORDER_STATUS_PAID:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "订单状态出出错")
    order.status = ORDER_STATUS_DELIVERED
    order.deliver_time = timezone.now()
    order.save()
    Log.objects.create(user=get_user(request), detail="发货订单ID:{}".format(query_id))
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Order, "id", "query_id")
def confirm_order(request: HttpRequest, query_id):
    """
    [POST] /api/order/confirm/<int:query_id>
    """
    order = Order.objects.get(id=query_id)
    if get_user(request) != order.user:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    if order.status != ORDER_STATUS_DELIVERED:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "订单状态出出错")
    order.status = ORDER_STATUS_CONFIRMED
    order.confirm_time = timezone.now()
    order.save()
    Log.objects.create(user=get_user(request), detail="确认收货订单ID:{}".format(query_id))
    return success_api_response()


def admin_order_to_dict(order: Order) -> dict:
    data = {
        "id": order.id,
        "user_id": order.user.id,
        "user__nickname": order.user.nickname,
        "commodity_id": order.commodity.id,
        "commodity__name": order.commodity.name,
        "commodity__shop_id": order.commodity.shop.id,
        "commodity__shop__name": order.commodity.shop.name,
        "image_url": s3_download_url(order.commodity.image.oss_token),
        "select_paras": list(map(lambda x: x.description, order.select_paras.all())),
        "price": order.price,
        "status": order.status,
        "start_time": order.start_time,
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
@query_filter(fields=[("id", int), ("user_id", int), ("user__nickname", str), ("commodity_id", int),
                      ("commodity__name", str), ("commodity__shop_id", int), ("commodity__shop__name", str),
                      ("price", float), ("status", int), ("start_time", str)])
@query_order_by(fields=["id", "user_id", "commodity_id", "commodity__shop_id", "price", "start_time"])
@query_page(default=10)
def admin_get_order_list(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/admin/order/list
    """
    orders = Order.objects.all()
    try:
        data = filter_order_and_list(orders, admin_order_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


def admin_order_to_dict_export(order: Order) -> dict:
    data = {
        "订单ID": order.id,
        "用户ID": order.user_id,
        "用户昵称": order.user.nickname,
        "商品ID": order.commodity_id,
        "商品名": order.commodity.name,
        "店铺ID": order.commodity.shop_id,
        "店铺名": order.commodity.shop.name,
        "所选参数": ",".join(list(map(lambda x: x.description, order.select_paras.all()))),
        "订单金额": order.price,
        "商品数量": order.num,
        "订单状态": ORDER_STATUS_DICT[order.status],
        "创建时间": order.start_time,
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
def export_order_list_admin(request: HttpRequest):
    """
    [GET] /api/admin/order/list_csv
    """
    orders = Order.objects.all()
    columns = ["订单ID", "用户ID", "用户昵称", "商品ID", "商品名", "店铺ID", "店铺名", "所选参数", "订单金额", "商品数量", "订单状态", "创建时间"]
    filename = "订单信息-管理员.csv"
    return data_export(query_set=orders, columns=columns, model_to_dict=admin_order_to_dict_export,
                       bom=request.GET.get("bom", None), filename=filename)


def user_order_to_dict(order: Order) -> dict:
    data = {
        "id": order.id,
        "commodity_id": order.commodity.id,
        "commodity__name": order.commodity.name,
        "commodity__price": order.commodity.price - order.commodity.discount,
        "commodity__shop_id": order.commodity.shop.id,
        "commodity__shop__name": order.commodity.name,
        "num": order.num,
        "price": order.price,
        "status": order.status,
        "image_url": s3_download_url(order.commodity.image.oss_token),
        "select_paras": list(map(lambda x: x.description, order.select_paras.all())),
        "start_time": order.start_time,
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
@query_filter(fields=[("id", int), ("commodity__name", str), ("commodity__shop__name", str), ("num", int),
                      ("price", float), ("status", int), ("start_time", str)])
@query_order_by(fields=["start_time", "price", "num"])
@query_page(default=10)
def user_get_order_list(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/order/user/list
    """
    user = get_user(request)
    orders = Order.objects.filter(user=user)
    try:
        data = filter_order_and_list(orders, user_order_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


def user_order_to_dict_export(order: Order) -> dict:
    data = {
        "订单ID": order.id,
        "商品ID": order.commodity_id,
        "商品名": order.commodity.name,
        "店铺ID": order.commodity.shop_id,
        "店铺名": order.commodity.shop.name,
        "所选参数": ",".join(list(map(lambda x: x.description, order.select_paras.all()))),
        "订单金额": order.price,
        "商品数量": order.num,
        "订单状态": ORDER_STATUS_DICT[order.status],
        "创建时间": order.start_time,
        "支付时间": order.pay_time,
        "发货时间": order.deliver_time,
        "确认收货时间": order.confirm_time,
        "关闭时间": order.close_time,
        "地址": order.address,
        "备注": order.note,
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
def export_user_order_list(request: HttpRequest):
    """
    [GET] /api/order/user/list_csv
    """
    user = get_user(request)
    orders = Order.objects.filter(user=user)
    columns = ["订单ID", "商品ID", "商品名", "店铺ID", "店铺名", "所选参数", "订单金额", "商品数量", "订单状态", "创建时间",
               "支付时间", "发货时间", "确认收货时间", "关闭时间", "地址", "备注"]
    filename = "{}的订单信息.csv".format(user.nickname)
    return data_export(query_set=orders, columns=columns, model_to_dict=user_order_to_dict_export,
                       bom=request.GET.get("bom", None), filename=filename)


def shop_order_to_dict(order: Order) -> dict:
    data = {
        "id": order.id,
        "user_id": order.user.id,
        "user__nickname": order.user.nickname,
        "commodity_id": order.commodity.id,
        "commodity__name": order.commodity.name,
        "num": order.num,
        "price": order.price,
        "address": order.address,
        "status": order.status,
        "start_time": order.start_time,
        "pay_time": order.pay_time,
        "deliver_time": order.deliver_time,
        "confirm_time": order.confirm_time,
        "close_time": order.close_time,
        "image_url": s3_download_url(order.commodity.image.oss_token),
        "select_paras": list(map(lambda x: x.description, order.select_paras.all())),
        "note": order.note,
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Shop, "id", "query_id")
@query_filter(fields=[("id", int), ("user_id", int), ("user__nickname", str), ("commodity__name", str),
                      ("commodity_id", int), ("num", int), ("price", float), ("address", str), ("status", int),
                      ("start_time", str), ("pay_time", str), ("deliver_time", str), ("confirm_time", str),
                      ("close_time", str), ("note", str)])
@query_order_by(fields=["id", "start_time", "pay_time", "deliver_time", "confirm_time", "close_time", "price",
                        "commodity_id", "num"])
@query_page(default=10)
def shop_admin_get_order_list(request: HttpRequest, query_id, *args, **kwargs):
    """
    [GET] /api/order/shop/list/<int:query_id>
    """
    user = get_user(request)
    shop = Shop.objects.get(id=query_id)
    if user != shop.owner and not shop.admin.contains(user):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "你没有权限访问这个店铺")
    orders = Order.objects.filter(commodity__shop=shop)
    try:
        data = filter_order_and_list(orders, shop_order_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


def shop_order_to_dict_export(order: Order) -> dict:
    data = {
        "订单ID": order.id,
        "用户ID": order.user_id,
        "用户昵称": order.user.nickname,
        "商品ID": order.commodity_id,
        "商品名": order.commodity.name,
        "所选参数": ",".join(list(map(lambda x: x.description, order.select_paras.all()))),
        "订单金额": order.price,
        "商品数量": order.num,
        "订单状态": ORDER_STATUS_DICT[order.status],
        "创建时间": order.start_time,
        "支付时间": order.pay_time,
        "发货时间": order.deliver_time,
        "确认收货时间": order.confirm_time,
        "关闭时间": order.close_time,
        "地址": order.address,
        "备注": order.note,
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
def export_shop_order_list(request: HttpRequest, query_id):
    """
    [GET] /api/order/shop/list_csv/<int:query_id>
    """
    user = get_user(request)
    shop = Shop.objects.get(id=query_id)
    if user != shop.owner and not shop.admin.contains(user):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "你没有权限访问这个店铺")
    orders = Order.objects.filter(commodity__shop=shop)
    columns = ["订单ID", "用户ID", "用户昵称", "商品ID", "商品名", "所选参数", "订单金额", "商品数量", "订单状态", "创建时间",
               "支付时间", "发货时间", "确认收货时间", "关闭时间", "地址", "备注"]
    filename = "{}的订单信息.csv".format(shop.name)
    return data_export(query_set=orders, columns=columns, model_to_dict=shop_order_to_dict_export,
                       bom=request.GET.get("bom", None), filename=filename)
