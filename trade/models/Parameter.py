from django.db import models

from trade.models.ParaSet import ParaSet


class Parameter(models.Model):
    """
    参数模型：
    description: 参数描述
    para_set: 属于的参数组
    add: 附加价格
    """
    description = models.CharField(max_length=50)
    para_set = models.ForeignKey(to=ParaSet, on_delete=models.CASCADE)
    add = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
