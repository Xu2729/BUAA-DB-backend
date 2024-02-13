from django.db import models
from django.utils import timezone

from trade.models.Commodity import Commodity
from trade.models.User import User


class CommCollectRecord(models.Model):
    """
    商品收藏记录：
    user: 用户
    commodity: 商品
    op_time: 操作时间
    """
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    commodity = models.ForeignKey(to=Commodity, on_delete=models.CASCADE)
    op_time = models.DateTimeField(default=timezone.now)
