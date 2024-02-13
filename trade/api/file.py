from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest
from django.views.decorators.http import require_POST, require_GET

from trade.file_util import s3_download, s3_upload, s3_download_url, _validate_upload_file, get_oss_token
from trade.models.Log import Log
from trade.models.Comment import Comment
from trade.models.Commodity import Commodity
from trade.models.File import File
from trade.models.Shop import Shop
from trade.util import response_wrapper, success_api_response, failed_api_response, ErrorCode, \
    require_jwt, require_item_exist, validate_request, get_user, require_keys, parse_data


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(File, "id", "query_id")
def set_user_image(request: HttpRequest, query_id):
    """
    [POST] /api/image/user/<int:query_id>
    """
    user = get_user(request)
    user.image_id = query_id
    user.save()
    Log.objects.create(user=user, detail="更新头像ID:{}".format(query_id))
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"shop_id"})
@require_item_exist(File, "id", "query_id")
def set_shop_image(request: HttpRequest, query_id):
    """
    [POST] /api/image/shop/<int:query_id>
    """
    data = parse_data(request)
    try:
        shop = Shop.objects.get(id=data["shop_id"])
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "店铺不存在")
    shop.image_id = query_id
    shop.save()
    Log.objects.create(user=get_user(request), detail="更新店铺图片ID:{}".format(query_id))
    return success_api_response()


def check_image_ids(images: list[int]) -> bool:
    for image_id in images:
        if not File.objects.filter(id=image_id).exists():
            return False
    return True


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"comment_id", "image_id_list"})
def add_comment_image(request: HttpRequest):
    """
    [POST] /api/image/comment
    """
    data = parse_data(request)
    user = get_user(request)
    try:
        comment = Comment.objects.get(id=data["comment_id"])
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "店铺不存在")
    if comment.order.user != user:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    check_image_ids(data["image_id_list"])
    for image_id in data["image_id_list"]:
        comment.image_set.add(image_id)
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"commodity_id", "image_id_list"})
def add_commodity_image(request: HttpRequest):
    """
    [POST] /api/image/commodity
    """
    data = parse_data(request)
    user = get_user(request)
    try:
        commodity = Commodity.objects.get(id=data["commodity_id"])
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "商品不存在")
    shop = commodity.shop
    if user != shop.owner and not shop.admin.contains(user):
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你无权操作这个店铺")
    check_image_ids(data["image_id_list"])
    for image_id in data["image_id_list"]:
        commodity.image_set.add(image_id)
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"commodity_id"})
@require_item_exist(File, "id", "query_id")
def set_commodity_main_image(request: HttpRequest, query_id):
    """
    [POST] /api/image/comm_main/<int:query_id>
    """
    data = parse_data(request)
    user = get_user(request)
    try:
        commodity = Commodity.objects.get(id=data["commodity_id"])
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "商品不存在")
    shop = commodity.shop
    if user != shop.owner and not shop.admin.contains(user):
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "你无权操作这个店铺")
    commodity.image = query_id
    commodity.save()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@validate_request(func=_validate_upload_file)
def upload_file(request: HttpRequest):
    """
    [POST] /api/file/upload
    """
    user = get_user(request)
    try:
        filename = request.FILES.get("file").name
        data = {
            "filename": filename,
            "oss_token": get_oss_token(user.id, filename),
        }
        s3_upload(data["oss_token"], request)
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, str(exception))
    file = File.objects.create(**data)
    return success_api_response({"id": file.id})


@response_wrapper
@require_GET
@require_item_exist(File, "id", "query_id")
def download_file(request: HttpRequest, query_id):
    """
    [GET] /api/file/download/<int:query_id>
    """
    file = File.objects.get(id=query_id)
    try:
        response = s3_download(file.oss_token, file.filename)
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, str(exception))
    return response


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(File, "id", "query_id")
def get_file_url(request: HttpRequest, query_id):
    """
    [GET] /api/file/url/<int:query_id>
    """
    file = File.objects.get(id=query_id)
    return success_api_response({"url": s3_download_url(file.oss_token)})
