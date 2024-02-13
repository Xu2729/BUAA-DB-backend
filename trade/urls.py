from django.urls import path

from trade.api.article import user_new_article, ARTICLE_DETAIL_API, user_get_article_list, admin_get_article_list, \
    user_star_article, user_cancel_star_article, user_collect_article, user_cancel_collect_article, \
    user_get_collect_article_list
from trade.api.auth import login, register, admin_login, update_password, check_user_name_exist, batch_register, \
    reset_password
from trade.api.comment import comment_order, get_comment_detail, get_commodity_comment_list, get_commodity_grade, \
    admin_get_comment_list
from trade.api.commodity import add_commodity, COMMODITY_DETAIL_API, user_get_commodity, user_get_shop_commodity_list, \
    PARAMETER_API, PARA_SET_API, add_parameter, add_para_set
from trade.api.draw import get_consume_statistic
from trade.api.file import upload_file, download_file, get_file_url, set_user_image, set_shop_image, \
    add_comment_image, add_commodity_image, set_commodity_main_image
from trade.api.log import list_log, export_log_list
from trade.api.order import create_order, admin_get_order_list, get_order_detail, update_order_address, close_order, \
    pay_order, deliver_order, confirm_order, user_get_order_list, shop_admin_get_order_list, export_user_order_list, \
    export_shop_order_list, export_order_list_admin
from trade.api.reply import ARTICLE_REPLY_API, REPLY_DETAIL_API
from trade.api.shop import SHOP_DETAIL_API, list_shop, register_shop, SHOP_ADMIN_API, list_user_shop
from trade.api.student_auth import ADMIN_STUDENT_AUTH_REQ_API, get_admin_student_auth_reqs, \
    get_student_auth_req_detail, create_student_auth_req, get_student_auth_reqs, check_student_id_exist
from trade.api.user import USER_DETAIL_API, list_user, export_user_list
from trade.views import test

urlpatterns = [
    # for test
    path("test", test),

    # auth
    path("auth/login", login),
    path("auth/register", register),
    path("auth/password/update", update_password),
    path("auth/check_username/<str:username>", check_user_name_exist),
    path("auth/batch/register", batch_register),
    path("auth/password/reset", reset_password),

    # file and image
    path("file/upload", upload_file),
    path("file/download/<int:query_id>", download_file),
    path("file/url/<int:query_id>", get_file_url),
    path("image/user/<int:query_id>", set_user_image),
    path("image/shop/<int:query_id>", set_shop_image),
    path("image/comment", add_comment_image),
    path("image/commodity", add_commodity_image),
    path("image/comm_main/<int:query_id>", set_commodity_main_image),

    # user
    path("user/<int:query_id>", USER_DETAIL_API),

    # shop
    path("shop/<int:query_id>", SHOP_DETAIL_API),
    path("shop/register", register_shop),
    path("shop/shop_admin/<int:query_id>", SHOP_ADMIN_API),
    path("shop/user_shop/<int:query_id>", list_user_shop),

    # commodity
    path("shop/comm/add/<int:query_id>", add_commodity),
    path("comm/<int:query_id>", COMMODITY_DETAIL_API),
    path("comm/list", user_get_commodity),
    path("shop/comm/list/<int:query_id>", user_get_shop_commodity_list),
    path("comm/para_set/<int:query_id>", PARA_SET_API),
    path("comm/para/<int:query_id>", PARAMETER_API),
    path("comm/para/add_to_para_set/<int:query_id>", add_parameter),
    path("comm/para_set/add_to_comm/<int:query_id>", add_para_set),

    # order
    path("order/new/<int:query_id>", create_order),
    path("order/<int:query_id>", get_order_detail),
    path("order/address/<int:query_id>", update_order_address),
    path("order/close/<int:query_id>", close_order),
    path("order/pay/<int:query_id>", pay_order),
    path("order/deliver/<int:query_id>", deliver_order),
    path("order/confirm/<int:query_id>", confirm_order),
    path("order/user/list", user_get_order_list),
    path("order/user/list_csv", export_user_order_list),
    path("order/shop/list/<int:query_id>", shop_admin_get_order_list),
    path("order/shop/list_csv/<int:query_id>", export_shop_order_list),

    # comment
    path("order/comment/<int:query_id>", comment_order),
    path("comment/<int:query_id>", get_comment_detail),
    path("commodity/comment/list/<int:query_id>", get_commodity_comment_list),
    path("commodity/comment/avg_grade/<int:query_id>", get_commodity_grade),

    # student auth req
    path("student/auth_req/new", create_student_auth_req),
    path("student/auth_req/list", get_student_auth_reqs),
    path("student/auth_req/detail/<int:query_id>", get_student_auth_req_detail),
    path("student/auth_req/check_id/<int:query_id>", check_student_id_exist),

    # article
    path("article/new", user_new_article),
    path("article/<int:query_id>", ARTICLE_DETAIL_API),
    path("article/list", user_get_article_list),
    path("article_op/star/<int:query_id>", user_star_article),
    path("article_op/cancel_star/<int:query_id>", user_cancel_star_article),
    path("article_op/collect/<int:query_id>", user_collect_article),
    path("article_op/cancel_collect/<int:query_id>", user_cancel_collect_article),
    path("article/collect/list", user_get_collect_article_list),

    # reply
    path("reply/article/<int:query_id>", ARTICLE_REPLY_API),
    path("reply/<int:query_id>", REPLY_DETAIL_API),

    # draw
    path("draw/consume", get_consume_statistic),

    # for admin
    path("amdin/login", admin_login),
    path("admin/user/list", list_user),
    path("admin/user/list_csv", export_user_list),
    path("admin/student/auth_req/detail/<int:query_id>", ADMIN_STUDENT_AUTH_REQ_API),
    path("admin/student/auth_req/list", get_admin_student_auth_reqs),
    path("admin/shop/list", list_shop),
    path("admin/order/list", admin_get_order_list),
    path("admin/order/list_csv", export_order_list_admin),
    path("admin/comment/list", admin_get_comment_list),
    path("admin/article/list", admin_get_article_list),
    path("admin/log/list", list_log),
    path("admin/log/list_csv", export_log_list),
]
