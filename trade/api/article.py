from django.core.paginator import Paginator
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from trade.exceptions import InvalidOrderByException, InvalidFilterException
from trade.file_util import s3_download_url
from trade.models.Article import Article
from trade.models.ArticleOp import ARTICLE_OP_GOOD, ARTICLE_OP_COLLECT, ArticleOp
from trade.models.Commodity import Commodity
from trade.query_util import query_page, query_order_by, query_filter, filter_order_and_list
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, require_jwt, require_item_exist, require_keys, get_user, wrapped_api


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"title", "content"})
def user_new_article(request: HttpRequest):
    """
    [POST] /api/article/new
    """
    user = get_user(request)
    data = parse_data(request)
    data["user"] = user
    if data.get("commodity_id", None) is not None:
        if not Commodity.objects.filter(id=data["commodity_id"]).exists():
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "无效的商品id")
        data["commodity"] = Commodity.objects.get(id=data["commodity_id"])
    filter_data(data, {"title", "content", "commodity", "user"})
    article = Article.objects.create(**data)
    return success_api_response({"id": article.id})


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_item_exist(Article, "id", "query_id")
def update_article(request: HttpRequest, query_id):
    """
    [PUT] /api/article/<int:query_id>
    """
    user = get_user(request)
    article = Article.objects.get(id=query_id)
    if user != article.user:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非法访问！")
    data = parse_data(request)
    if data.get("commodity_id", None) is not None:
        if not Commodity.objects.filter(id=data["commodity_id"]).exists():
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "商品id无效")
        data["commodity"] = Commodity.objects.get(id=data["commodity_id"])
    filter_data(data, {"title", "content", "commodity"})
    try:
        Article.objects.filter(id=query_id).update(**data)
        return success_api_response()
    except Exception as exception:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, str(exception))


def article_commodity_to_dict(commodity: Commodity) -> dict:
    data = {
        "id": commodity.id,
        "name": commodity.name,
        "price": commodity.price,
        "discount": commodity.discount,
        "image_url": s3_download_url(commodity.image.oss_token),
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Article, "id", "query_id")
def get_article_detail(request: HttpRequest, query_id):
    """
    [GET] /api/article/<int:query_id>
    """
    article = Article.objects.get(id=query_id)
    user = get_user(request)
    data = {
        "id": article.id,
        "title": article.title,
        "content": article.content,
        "post_time": article.post_time,
        "user_id": article.user.id,
        "user__nickname": article.user.nickname,
        "star": ArticleOp.objects.filter(user=user, article_id=query_id, op=ARTICLE_OP_GOOD).exists(),
        "collect": ArticleOp.objects.filter(user=user, article_id=query_id, op=ARTICLE_OP_COLLECT).exists(),
        "star_count": get_article_star_count(article),
        "collect_count": get_article_collect_count(article),
        "commodity": None if article.commodity is None else article_commodity_to_dict(article.commodity),
    }
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_GET
@query_filter(fields=[("title", str), ("content", str), ("post_time", str)])
@query_order_by(fields=["id", "post_time"])
@query_page(default=10)
def user_get_article_list(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/article/list
    """
    articles = Article.objects.all()
    user = get_user(request)

    def user_brief_article_to_dict(article: Article) -> dict:
        dic = {
            "id": article.id,
            "title": article.title,
            "content": article.content if len(article.content) < 200 else article.content[:198] + "...",
            "user_id": article.user.id,
            "user__nickname": article.user.nickname,
            "post_time": article.post_time,
            "star": ArticleOp.objects.filter(user=user, article=article, op=ARTICLE_OP_GOOD).exists(),
            "collect": ArticleOp.objects.filter(user=user, article=article, op=ARTICLE_OP_COLLECT).exists(),
            "star_count": get_article_star_count(article),
            "collect_count": get_article_collect_count(article),
        }
        return dic

    try:
        data = filter_order_and_list(articles, user_brief_article_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


def admin_article_to_dict(article: Article) -> dict:
    data = {
        "id": article.id,
        "title": article.title,
        "user_id": article.user.id,
        "user__nickname": article.user.nickname,
        "post_time": article.post_time,
        "commodity_id": None if article.commodity is None else article.commodity.id,
        "commodity__name": None if article.commodity is None else article.commodity.name,
        "star_count": get_article_star_count(article),
        "collect_count": get_article_collect_count(article),
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
@query_filter(fields=[("id", int), ("title", str), ("user_id", int), ("user__nickname", str), ("post_time", str),
                      ("commodity_id", int), ("commodity__name", str)])
@query_order_by(fields=["id", "post_time"])
@query_page(default=10)
def admin_get_article_list(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/admin/article/list
    """
    articles = Article.objects.all()
    try:
        data = filter_order_and_list(articles, admin_article_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Article, "id", "query_id")
def user_star_article(request: HttpRequest, query_id):
    """
    [POST] /api/article_op/star/<int:query_id>
    """
    user = get_user(request)
    if ArticleOp.objects.filter(article_id=query_id, user=user, op=ARTICLE_OP_GOOD).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "你已经赞过了")
    ArticleOp.objects.create(article_id=query_id, user=user, op=ARTICLE_OP_GOOD)
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Article, "id", "query_id")
def user_cancel_star_article(request: HttpRequest, query_id):
    """
    [POST] /api/article_op/cancel_star/<int:query_id>
    """
    user = get_user(request)
    if not ArticleOp.objects.filter(article_id=query_id, user=user, op=ARTICLE_OP_GOOD).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "点赞状态出错")
    ArticleOp.objects.filter(article_id=query_id, user=user, op=ARTICLE_OP_GOOD).delete()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Article, "id", "query_id")
def user_collect_article(request: HttpRequest, query_id):
    """
    [POST] /api/article_op/collect/<int:query_id>
    """
    user = get_user(request)
    if ArticleOp.objects.filter(article_id=query_id, user=user, op=ARTICLE_OP_COLLECT).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "你已经收藏过了")
    ArticleOp.objects.create(article_id=query_id, user=user, op=ARTICLE_OP_COLLECT)
    return success_api_response()


@response_wrapper
@require_jwt()
@require_POST
@require_item_exist(Article, "id", "query_id")
def user_cancel_collect_article(request: HttpRequest, query_id):
    """
    [POST] /api/article_op/cancel_collect/<int:query_id>
    """
    user = get_user(request)
    if not ArticleOp.objects.filter(article_id=query_id, user=user, op=ARTICLE_OP_COLLECT).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "收藏状态出错")
    ArticleOp.objects.filter(article_id=query_id, user=user, op=ARTICLE_OP_COLLECT).delete()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_GET
@query_page(default=10)
def user_get_collect_article_list(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/article/collect/list
    """
    user = get_user(request)

    def user_brief_article_to_dict(article: Article) -> dict:
        dic = {
            "id": article.id,
            "title": article.title,
            "content": article.content if len(article.content) < 200 else article.content[:198] + "...",
            "user_id": article.user.id,
            "user__nickname": article.user.nickname,
            "post_time": article.post_time,
            "star": ArticleOp.objects.filter(user=user, article=article, op=ARTICLE_OP_GOOD).exists(),
            "collect": ArticleOp.objects.filter(user=user, article=article, op=ARTICLE_OP_COLLECT).exists(),
            "star_count": get_article_star_count(article),
            "collect_count": get_article_collect_count(article),
        }
        return dic

    article_op_list = ArticleOp.objects.filter(user=user, op=ARTICLE_OP_COLLECT).order_by("-op_time")
    page = kwargs.get("page")
    page_size = kwargs.get("page_size")
    paginator = Paginator(article_op_list, page_size)
    page_all = paginator.num_pages
    if page > page_all:
        articles = []
    else:
        articles = list(map(lambda aop: user_brief_article_to_dict(aop.article), paginator.get_page(page).object_list))
    data = {
        "page": page,
        "page_all": page_all,
        "count": article_op_list.count(),
        "articles": articles,
    }
    return success_api_response(data)


def get_article_star_count(article: Article) -> int:
    return ArticleOp.objects.filter(article=article, op=ARTICLE_OP_GOOD).count()


def get_article_collect_count(article: Article) -> int:
    return ArticleOp.objects.filter(article=article, op=ARTICLE_OP_COLLECT).count()


ARTICLE_DETAIL_API = wrapped_api({
    "GET": get_article_detail,
    "PUT": update_article,
})
