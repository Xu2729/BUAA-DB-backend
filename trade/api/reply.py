from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from trade.file_util import s3_download_url
from trade.models.Article import Article
from trade.models.Reply import Reply
from trade.models.User import ROLE_ADMIN
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, require_jwt, require_item_exist, require_keys, get_user, wrapped_api


def get_next_floor(article_id: int) -> int:
    if not Reply.objects.filter(article_id=article_id).exists():
        return 1
    return Reply.objects.filter(article_id=article_id).order_by("-floor").first().floor + 1


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"content"})
@require_item_exist(Article, "id", "query_id")
def user_new_reply(request: HttpRequest, query_id):
    """
    [POST] /api/reply/article/<int:query_id>
    """
    user = get_user(request)
    data = parse_data(request)
    filter_data(data, {"content", "ref_floor"})
    if data.get("ref_floor", None) is not None:
        temp_qs = Reply.objects.filter(article_id=query_id, floor=data["ref_floor"])
        if not temp_qs.exists():
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "引用的楼层不存在")
        refer = temp_qs.first()
        data["refer"] = refer
        del data["ref_floor"]
    data["floor"] = get_next_floor(query_id)
    data["user"] = user
    data["article"] = Article.objects.get(id=query_id)
    reply = Reply.objects.create(**data)
    return success_api_response({"id": reply.id, "floor": reply.floor})


def reply_to_dict(reply: Reply) -> dict:
    data = {
        "id": reply.id,
        "user_id": reply.user_id,
        "user__nickname": reply.user.nickname,
        "article_id": reply.article_id,
        "article__title": reply.article.title,
        "floor": reply.floor,
        "refer": None if reply.refer is None else reply.refer_id,
        "refer_floor": None if reply.refer is None else reply.refer.floor,
        "content": reply.content,
        "image_url": None if reply.user.image is None else s3_download_url(reply.user.image.oss_token),
    }
    return data


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_item_exist(Reply, "id", "query_id")
def update_reply(request: HttpRequest, query_id):
    """
    [PUT] /api/reply/<int:query_id>
    管理员可操作
    """
    user = get_user(request)
    reply = Reply.objects.get(id=query_id)
    if user != reply.user and user.role != ROLE_ADMIN:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "非法访问！")
    data = parse_data(request)
    filter_data(data, {"ref_floor", "content"})
    if data.get("ref_floor", None) is not None:
        temp_qs = Reply.objects.filter(article_id=reply.article_id, floor=data["ref_floor"])
        if not temp_qs.exists():
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "引用的楼层不存在")
        refer = temp_qs.first()
        data["refer"] = refer
        del data["ref_floor"]
    try:
        Reply.objects.filter(id=query_id).update(**data)
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, str(exception))


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Article, "id", "query_id")
def get_article_all_reply(request: HttpRequest, query_id):
    """
    [GET] /api/reply/article/<int:query_id>
    """
    return success_api_response({"replies": list(map(reply_to_dict, Reply.objects.filter(article_id=query_id)))})


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
@require_item_exist(Reply, "id", "query_id")
def delete_reply(request: HttpRequest, query_id):
    """
    [DELETE] /api/article/<int:query_id>
    管理员可操作性
    """
    user = get_user(request)
    reply = Reply.objects.get(id=query_id)
    if user != reply.user and user.role != ROLE_ADMIN:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "非法访问！")
    Reply.objects.filter(id=query_id).delete()
    return success_api_response()


ARTICLE_REPLY_API = wrapped_api({
    "GET": get_article_all_reply,
    "POST": user_new_reply,
})

REPLY_DETAIL_API = wrapped_api({
    "PUT": update_reply,
    "DELETE": delete_reply,
})
