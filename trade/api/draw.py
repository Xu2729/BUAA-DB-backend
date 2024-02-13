import json

from django.db.models import Sum
from django.http import HttpRequest
from django.views.decorators.http import require_GET
from pyecharts import options as opts
from pyecharts.charts import Bar

from trade.models.Order import Order
from trade.models.User import User
from trade.models.status import ORDER_STATUS_PAID, ORDER_STATUS_DELIVERED, ORDER_STATUS_CONFIRMED, \
    ORDER_STATUS_COMMENTED
from trade.util import response_wrapper, failed_api_response, success_api_response, ErrorCode


@response_wrapper
@require_GET
def get_consume_statistic(request: HttpRequest):
    """
    [GET] /api/draw/consume
    """
    if request.GET.get("year", None) is None:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "缺少参数year")
    if request.GET.get("id", None) is None:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "缺少参数id")
    if not User.objects.filter(id=request.GET["id"]).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "id无效")
    year = request.GET["year"]
    user = User.objects.get(id=request.GET["id"])
    orders = Order.objects.filter(user=user, start_time__year=year,
                                  status__in=[ORDER_STATUS_PAID, ORDER_STATUS_DELIVERED, ORDER_STATUS_CONFIRMED,
                                              ORDER_STATUS_COMMENTED])
    months = [i for i in range(1, 13)]
    price_list = []
    for month in months:
        price_list.append(orders.filter(start_time__month=month).aggregate(Sum("price"))["price__sum"])
    months = [str(i) + "月" for i in range(1, 13)]
    c = (
        Bar()
            .add_xaxis(months)
            .add_yaxis("消费金额", price_list)
            .set_global_opts(title_opts=opts.TitleOpts(title="{}年度每月消费统计".format(year)),
                             yaxis_opts=opts.AxisOpts(
                                 name="金额",
                                 type_="value",
                                 axislabel_opts=opts.LabelOpts(formatter="{value} 元"),
                             ))
            .dump_options_with_quotes()
    )
    return success_api_response(json.loads(c))
