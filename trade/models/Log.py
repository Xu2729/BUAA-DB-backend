from django.db import models
from django.utils import timezone

from trade.models.User import User


class Log(models.Model):
    """
    日志模型：
    user: 操作用户
    op_time: 操作时间
    detail: 操作详情，如：用户登录成功，管理员登录成功，新建商品123 等
    """
    user = models.ForeignKey(to=User, on_delete=models.PROTECT)
    op_time = models.DateTimeField(default=timezone.now)
    detail = models.CharField(max_length=100)
