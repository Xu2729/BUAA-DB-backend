from django.db import models

from trade.models.Commodity import Commodity


class ParaSet(models.Model):
    """
    参数组模型：
    name: 参数组名
    commodity: 关联商品
    """
    name = models.CharField(max_length=50)
    commodity = models.ForeignKey(to=Commodity, on_delete=models.CASCADE)
