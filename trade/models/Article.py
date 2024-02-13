from django.db import models
from django.utils import timezone

from trade.models.Commodity import Commodity
from trade.models.User import User


class Article(models.Model):
    """
    文章模型：
    user: 发表用户
    title: 文章标题
    content: 文章内容
    post_time: 发布时间
    commodity: 关联商品
    """
    user = models.ForeignKey(to=User, on_delete=models.PROTECT)
    title = models.CharField(max_length=50, blank=False)
    content = models.TextField(blank=False)
    post_time = models.DateTimeField(default=timezone.now)
    commodity = models.ForeignKey(to=Commodity, on_delete=models.SET_NULL, null=True)
