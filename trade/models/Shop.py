from django.db import models
from django.utils import timezone

from trade.models.File import File
from trade.models.User import User

TYPE_PERSONAL = 0
TYPE_COOPERATIVE = 1


class Shop(models.Model):
    """
    店铺模型：
    name: 店铺名
    reg_time: 注册时间
    introduction: 介绍
    type: 类型
    owner: 所有者
    admin: 管理者
    image: 店铺图标
    """
    TYPES = [
        (TYPE_PERSONAL, "个人店铺"),
        (TYPE_COOPERATIVE, "合作店铺"),
    ]

    name = models.CharField(max_length=30, unique=True)
    reg_time = models.DateTimeField(default=timezone.now)
    introduction = models.TextField(null=True)
    type = models.IntegerField(choices=TYPES)
    owner = models.ForeignKey(to=User, related_name='owner_shop', on_delete=models.PROTECT)
    admin = models.ManyToManyField(to=User, related_name='admins_shop')
    image = models.ForeignKey(to=File, on_delete=models.SET_NULL, null=True)
