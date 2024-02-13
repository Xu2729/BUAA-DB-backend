from django.db import models

from trade.models.File import File
from trade.models.Shop import Shop
from trade.models.status import COMM_STATUSES, COMM_STATUS_INVALID

METHOD_ONLINE = 0
METHOD_SELF = 1
METHOD_DELIVERY = 2


class Commodity(models.Model):
    """
    商品模型：
    name: 商品名
    introduction: 商品介绍
    status: 商品状态，有未生效、预售中、售卖中、已下架 四种状态
    total: 商品总量
    sale: 已售量，注意：对于预售商品是预售量，所以可以 sale > total
    price: 原价
    discount: 优惠，实际购买价格 = price - discount，必须有 price > discount
    method: 交易方式
    image: 主预览图
    image_set: 详情页图片
    """
    METHODS = [
        (METHOD_ONLINE, "线上交易"),
        (METHOD_SELF, "线下自取"),
        (METHOD_DELIVERY, "送货上门")
    ]

    name = models.CharField(max_length=100, blank=False)
    introduction = models.TextField(null=True)
    status = models.IntegerField(choices=COMM_STATUSES, default=COMM_STATUS_INVALID)
    total = models.IntegerField()
    sale = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    discount = models.DecimalField(max_digits=8, decimal_places=2)
    shop = models.ForeignKey(to=Shop, on_delete=models.PROTECT)
    method = models.IntegerField(choices=METHODS)
    image = models.ForeignKey(to=File, on_delete=models.PROTECT, related_name="main_image")
    image_set = models.ManyToManyField(to=File)
