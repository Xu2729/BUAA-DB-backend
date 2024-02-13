from django.db import models
from django.utils import timezone

from trade.models.Commodity import Commodity
from trade.models.Parameter import Parameter
from trade.models.User import User
from trade.models.status import ORDER_STATUSES, ORDER_STATUS_ORDERED


class Order(models.Model):
    """
    订单模型：
    user: 下单的人
    commodity: 下单商品，不许一单多个商品，没有购物车
    status: 状态，有：已下单、已支付、已送达、已确认、已评价、已关闭（已关闭是下单了但是15min内没付款）
    price: 单价
    num: 数量，订单金额 = num * price
    address: 收货地址/取货地址
    start_time: 下单时间
    pay_time: 付款时间
    deliver_tine: 发货时间
    confirm_time: 确认时间
    close_time: 关闭时间
    select_paras: 选择的参数
    not: 备注，选填
    """
    user = models.ForeignKey(to=User, on_delete=models.PROTECT)
    commodity = models.ForeignKey(to=Commodity, on_delete=models.PROTECT)
    status = models.IntegerField(choices=ORDER_STATUSES, default=ORDER_STATUS_ORDERED)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    num = models.IntegerField()
    address = models.CharField(max_length=100, null=True)
    start_time = models.DateTimeField(default=timezone.now)
    pay_time = models.DateTimeField(null=True)
    deliver_time = models.DateTimeField(null=True)
    confirm_time = models.DateTimeField(null=True)
    close_time = models.DateTimeField(null=True)
    select_paras = models.ManyToManyField(to=Parameter)
    note = models.TextField(null=True)
