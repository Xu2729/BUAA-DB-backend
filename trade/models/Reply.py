from django.db import models
from django.utils import timezone

from trade.models.Article import Article
from trade.models.User import User


class Reply(models.Model):
    """
    回复模型：
    user: 发回复的人
    article: 回复所在的文章
    floor: 回复楼层
    refer: 引用的回复
    content: 回复内容
    reply_time: 回复时间
    """
    user = models.ForeignKey(to=User, on_delete=models.PROTECT)
    article = models.ForeignKey(to=Article, on_delete=models.CASCADE)
    floor = models.IntegerField()
    refer = models.ForeignKey(to='self', on_delete=models.SET_NULL, null=True)
    content = models.TextField(blank=False)
    reply_time = models.DateTimeField(default=timezone.now)
