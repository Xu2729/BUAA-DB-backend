from django.core.paginator import Paginator
from django.db.models import Q, F, ProtectedError
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from trade.api.comment import get_commodity_avg_grade
from trade.api.shop import get_shop_avg_grade
from trade.file_util import s3_download_url
from trade.models.CommCollectRecord import CommCollectRecord
from trade.models.Commodity import Commodity
from trade.models.File import File
from trade.models.Log import Log
from trade.models.ParaSet import ParaSet
from trade.models.Parameter import Parameter
from trade.models.Shop import Shop
from trade.models.status import COMM_STATUS_ON_SELL, COMM_STATUS_PRE_SELL, COMM_STATUS_INVALID
from trade.query_util import query_page
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, wrapped_api, require_jwt, require_item_exist, require_keys, get_user


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"name", "total", "price", "discount", "method", "image_id", "status", "para_set", "introduction"})
@require_item_exist(Shop, "id", "query_id")
def add_commodity(request: HttpRequest, query_id):
    """
    [POST] /api/shop/comm/add/<int:query_id>
    para_set example:
    [{"name":"颜色","options":{"红色":0.00,"蓝色":0.00}},{"name":"大小","options":{"小":0.00,"大":10.00}}]
    """
    user = get_user(request)
    shop = Shop.objects.get(id=query_id)
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    data = parse_data(request)
    if not File.objects.filter(id=data["image_id"][0]).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "图片不存在！")
    image = File.objects.get(id=data["image_id"][0])
    other_image = [data["image_id"][i] for i in range(1, len(data["image_id"]))]
    filter_data(data, {"name", "introduction", "status", "total", "price", "discount", "method", "para_set"})
    if data.get("status", None) is not None and \
            data["status"] not in (COMM_STATUS_INVALID, COMM_STATUS_PRE_SELL, COMM_STATUS_ON_SELL):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "商品初始状态错误")
    data["shop"] = shop
    data["image"] = image
    flag = False
    para_sets = []
    if data.get("para_set", None) is not None:
        flag = True
        para_sets = data["para_set"]
        del data["para_set"]
    commodity = Commodity.objects.create(**data)
    # add parameter
    if flag:
        for para_set in para_sets:
            para_set_obj = ParaSet.objects.create(commodity=commodity, name=para_set["name"])
            for key, value in para_set["options"].items():
                Parameter.objects.create(description=key, add=value, para_set=para_set_obj)
    for image_id in other_image:
        if File.objects.filter(id=image_id).exists():
            commodity.image_set.add(image_id)
    Log.objects.create(user=user, detail="添加商品ID:{}".format(commodity.id))
    return success_api_response({"id": commodity.id})


def para_to_dict(parameter: Parameter) -> dict:
    data = {
        "id": parameter.id,
        "description": parameter.description,
        "add": parameter.add
    }
    return data


def para_set_to_dict(para_set: ParaSet) -> dict:
    paras = Parameter.objects.filter(para_set=para_set)
    data = {
        "id": para_set.id,
        "name": para_set.name,
        "options": list(map(para_to_dict, paras))
    }
    return data


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
@require_item_exist(Commodity, "id", "query_id")
def delete_commodity(request: HttpRequest, query_id):
    """
    [DELETE] /api/comm/<int:query_id>
    """
    user = get_user(request)
    shop = Commodity.objects.get(id=query_id).shop
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    try:
        Commodity.objects.filter(id=query_id).delete()
        Log.objects.create(user=user, detail="删除商品ID:{}".format(query_id))
        return success_api_response()
    except ProtectedError:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "存在与之关联的订单，不能删除")
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, str(exception))


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Commodity, "id", "query_id")
def get_commodity_detail(request: HttpRequest, query_id):
    """
    [GET] /api/comm/<int:query_id>
    """
    commodity = Commodity.objects.get(id=query_id)
    para_sets = ParaSet.objects.filter(commodity=commodity)
    user = get_user(request)
    data = {
        "id": commodity.id,
        "name": commodity.name,
        "introduction": commodity.introduction,
        "status": commodity.status,
        "total": commodity.total,
        "sale": commodity.sale,
        "price": commodity.price,
        "discount": commodity.discount,
        "shop_id": commodity.shop.id,
        "shop__name": commodity.shop.name,
        "shop__grade": get_shop_avg_grade(commodity.shop.id),
        "method": commodity.method,
        "parameters": list(map(para_set_to_dict, para_sets)),
        "img_url": s3_download_url(commodity.image.oss_token),
        "img_url_list": list(map(lambda x: s3_download_url(x.oss_token), commodity.image_set.all())),
        "grade": get_commodity_avg_grade(query_id),
        "collect": CommCollectRecord.objects.filter(user=user, commodity=commodity).exists(),
    }
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_item_exist(Commodity, "id", "query_id")
def update_commodity_detail(request: HttpRequest, query_id):
    """
    [PUT] /api/comm/<int:query_id>
    """
    user = get_user(request)
    shop = Commodity.objects.get(id=query_id).shop
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    data = parse_data(request)
    filter_data(data, {"status", "discount"})
    try:
        Commodity.objects.filter(id=query_id).update(**data)
        Log.objects.create(user=user, detail="更新商品ID:{}".format(query_id))
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, str(exception))


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
@require_item_exist(Parameter, "id", "query_id")
def delete_parameter(request: HttpRequest, query_id):
    """
    [DELETE] /api/comm/para/<int:query_id>
    """
    user = get_user(request)
    shop = Parameter.objects.get(id=query_id).para_set.commodity.shop
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    Parameter.objects.get(id=query_id).delete()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_item_exist(Parameter, "id", "query_id")
def update_parameter(request: HttpRequest, query_id):
    """
    [PUT] /api/comm/para/<int:query_id>
    """
    user = get_user(request)
    shop = Parameter.objects.get(id=query_id).para_set.commodity.shop
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    data = parse_data(request)
    filter_data(data, {"description", "add"})
    try:
        Parameter.objects.filter(id=query_id).update(**data)
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, str(exception))


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"description", "add"})
@require_item_exist(ParaSet, "id", "query_id")
def add_parameter(request: HttpRequest, query_id):
    """
    [POST] /api/comm/para/add_to_para_set/<int:query_id>
    """
    user = get_user(request)
    para_set = ParaSet.objects.get(id=query_id)
    shop = para_set.commodity.shop
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    data = parse_data(request)
    filter_data(data, {"description", "add"})
    data["para_set"] = para_set
    para = Parameter.objects.create(**data)
    return success_api_response({"id": para.id})


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
@require_item_exist(ParaSet, "id", "query_id")
def delete_para_set(request: HttpRequest, query_id):
    """
    [DELETE] /api/comm/para_set/<int:query_id>
    """
    user = get_user(request)
    shop = ParaSet.objects.get(id=query_id).commodity.shop
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    Parameter.objects.filter(para_set_id=query_id).delete()
    ParaSet.objects.filter(id=query_id).delete()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_item_exist(ParaSet, "id", "query_id")
def update_para_set(request: HttpRequest, query_id):
    """
    [PUT] /api/comm/para_set/<int:query_id>
    """
    user = get_user(request)
    shop = ParaSet.objects.get(id=query_id)
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    data = parse_data(request)
    filter_data(data, {"name"})
    try:
        ParaSet.objects.filter(id=query_id).update(**data)
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, str(exception))


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"name"})
@require_item_exist(Commodity, "id", "query_id")
def add_para_set(request: HttpRequest, query_id):
    """
    [POST] /api/comm/para_set/add_to_comm/<int:query_id>
    """
    user = get_user(request)
    commodity = Commodity.objects.get(id=query_id)
    shop = commodity.get(id=query_id).shop
    if not shop.admin.contains(user) and user.id != shop.owner.id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你没有权限操作这个店铺")
    data = parse_data(request)
    filter_data(data, {"name"})
    data["commodity"] = commodity
    para_set = ParaSet.objects.create(**data)
    return success_api_response({"id": para_set.id})


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"keyword"})
@query_page(default=10)
def user_get_commodity(request: HttpRequest, *args, **kwargs):
    """
    [POST] /api/comm/list
    请求体中参数：keyword, min_price, max_price, status, min_sale, method, have_stock
    order_by: sale, price
    """
    data = parse_data(request)
    user = get_user(request)

    def user_commodity_to_dict(commodity: Commodity) -> dict:
        dic = {
            "id": commodity.id,
            "name": commodity.name,
            "introduction": commodity.introduction,
            "status": commodity.status,
            "total": commodity.total,
            "sale": commodity.sale,
            "price": commodity.price,
            "discount": commodity.discount,
            "shop_id": commodity.shop.id,
            "shop__name": commodity.shop.name,
            "method": commodity.method,
            "img_url": s3_download_url(commodity.image.oss_token),
            "grade": get_commodity_avg_grade(commodity.id),
            "collect": CommCollectRecord.objects.filter(user=user, commodity=commodity).exists(),
        }
        return dic

    filter_data(data, {"keyword", "min_price", "status", "max_price", "method", "min_sale", "have_stock", "order_by"})
    commodities = Commodity.objects.filter(
        Q(name__contains=data["keyword"]) | Q(introduction__contains=data["keyword"]) | Q(
            shop__name__contains=data["keyword"]))
    if data.get("min_price", None) is not None:
        commodities = commodities.filter(price__gte=F("discount") + data["min_price"])
    if data.get("max_price", None) is not None:
        commodities = commodities.filter(price__lte=F("discount") + data["max_price"])
    if data.get("status", None) is not None:
        commodities = commodities.filter(status__in=data["status"])
    if data.get("min_sale", None) is not None:
        commodities = commodities.filter(sale__gte=data["min_sale"])
    if data.get("method", None) is not None:
        commodities = commodities.filter(method__in=data["method"])
    if data.get("have_stock", None) is not None and data.get("have_stock", None):
        commodities = commodities.filter(total__gt=F("sale"))
    if data.get("order_by", None) is None:
        commodities = commodities.order_by("-sale")
    else:
        order_by_fields = data["order_by"].split("*")
        commodities = commodities.order_by(*order_by_fields)
    tot_count = commodities.count()
    page = kwargs.get("page")
    page_size = kwargs.get("page_size")
    paginator = Paginator(commodities, page_size)
    page_all = paginator.num_pages
    if page > page_all:
        data_list = []
    else:
        data_list = list(map(user_commodity_to_dict, paginator.get_page(page).object_list))
    res_data = {
        "tot_count": tot_count,
        "page_all": page_all,
        "page": page,
        "data": data_list
    }
    return success_api_response(res_data)


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"keyword"})
@require_item_exist(Shop, "id", "query_id")
@query_page(default=10)
def user_get_shop_commodity_list(request: HttpRequest, query_id, *args, **kwargs):
    """
    [POST] /api/shop/comm/list/<int:query_id>
    """
    shop = Shop.objects.get(id=query_id)
    user = get_user(request)

    def user_commodity_to_dict(commodity: Commodity) -> dict:
        dic = {
            "id": commodity.id,
            "name": commodity.name,
            "introduction": commodity.introduction,
            "status": commodity.status,
            "total": commodity.total,
            "sale": commodity.sale,
            "price": commodity.price,
            "discount": commodity.discount,
            "method": commodity.method,
            "img_url": s3_download_url(commodity.image.oss_token),
            "grade": get_commodity_avg_grade(commodity.id),
            "collect": CommCollectRecord.objects.filter(user=user, commodity=commodity).exists(),
        }
        return dic

    commodities = Commodity.objects.filter(shop=shop)
    data = parse_data(request)
    filter_data(data, {"keyword", "min_price", "status", "max_price", "method", "min_sale", "have_stock", "order_by"})
    if data.get("keyword", None) is not None:
        commodities = commodities.filter(Q(name__contains=data["keyword"]) | Q(introduction__contains=data["keyword"]))
    if data.get("min_price", None) is not None:
        commodities = commodities.filter(price__gte=F("discount") + data["min_price"])
    if data.get("max_price", None) is not None:
        commodities = commodities.filter(price__lte=F("discount") + data["max_price"])
    if data.get("status", None) is not None:
        commodities = commodities.filter(status__in=data["status"])
    if data.get("min_sale", None) is not None:
        commodities = commodities.filter(sale__gte=data["min_sale"])
    if data.get("method", None) is not None:
        commodities = commodities.filter(method__in=data["method"])
    if data.get("have_stock", None) is not None and data.get("have_stock", None):
        commodities = commodities.filter(total__gt=F("sale"))
    if data.get("order_by", None) is None:
        commodities = commodities.order_by("-sale")
    else:
        order_by_fields = data["order_by"].split("*")
        commodities = commodities.order_by(*order_by_fields)
    tot_count = commodities.count()
    page = kwargs.get("page")
    page_size = kwargs.get("page_size")
    paginator = Paginator(commodities, page_size)
    page_all = paginator.num_pages
    if page > page_all:
        data_list = []
    else:
        data_list = list(map(user_commodity_to_dict, paginator.get_page(page).object_list))
    res_data = {
        "tot_count": tot_count,
        "page_all": page_all,
        "page": page,
        "data": data_list
    }
    return success_api_response(res_data)


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Commodity, "id", "query_id")
def user_collect_commodity(request: HttpRequest, query_id):
    """
    [POST] /api/commodity/collect/<int:query_id>
    """
    user = get_user(request)
    if CommCollectRecord.objects.filter(user=user, commodity_id=query_id).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "你已经收藏过了")
    CommCollectRecord.objects.create(user=user, commodity_id=query_id)
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Commodity, "id", "query_id")
def user_cancel_collect_commodity(request: HttpRequest, query_id):
    """
    [POST] /api/commodity/cancel_collect/<int:query_id>
    """
    user = get_user(request)
    if not CommCollectRecord.objects.filter(user=user, commodity_id=query_id).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "收藏状态出错")
    CommCollectRecord.objects.filter(user=user, commodity_id=query_id).delete()
    return success_api_response()


def user_collect_commodity_record_to_dict(record: CommCollectRecord) -> dict:
    commodity = record.commodity
    data = {
        "id": commodity.id,
        "name": commodity.name,
        "introduction": commodity.introduction,
        "status": commodity.status,
        "total": commodity.total,
        "sale": commodity.sale,
        "price": commodity.price,
        "discount": commodity.discount,
        "shop_id": commodity.shop.id,
        "shop__name": commodity.shop.name,
        "method": commodity.method,
        "img_url": s3_download_url(commodity.image.oss_token),
        "grade": get_commodity_avg_grade(commodity.id),
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
@query_page(default=10)
def user_get_collect_commodity_list(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/comm/collect/list
    """
    user = get_user(request)
    records = CommCollectRecord.objects.filter(user=user).order_by("-op_time")
    tot_count = records.count()
    page = kwargs.get("page")
    page_size = kwargs.get("page_size")
    paginator = Paginator(records, page_size)
    page_all = paginator.num_pages
    if page > page_all:
        data_list = []
    else:
        data_list = list(map(user_collect_commodity_record_to_dict, paginator.get_page(page).object_list))
    res_data = {
        "tot_count": tot_count,
        "page_all": page_all,
        "page": page,
        "data": data_list
    }
    return success_api_response(res_data)


COMMODITY_DETAIL_API = wrapped_api({
    "GET": get_commodity_detail,
    "PUT": update_commodity_detail,
    "DELETE": delete_commodity,
})

PARAMETER_API = wrapped_api({
    "PUT": update_parameter,
    "DELETE": delete_parameter,
})

PARA_SET_API = wrapped_api({
    "PUT": update_para_set,
    "DELETE": delete_para_set,
})
