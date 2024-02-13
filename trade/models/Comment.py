from django.db import models
from django.utils import timezone

from trade.models.File import File
from trade.models.Order import Order


class Comment(models.Model):
    """
    订单评价模型：
    order: 关联的订单
    grade: 评价星级
    content: 评价内容
    comment_time: 评价时间
    image_set: 添加的图片
    """
    GRADES = [
        (1, "非常差"),
        (2, "较差"),
        (3, "中等"),
        (4, "较好"),
        (5, "非常好"),
    ]

    order = models.ForeignKey(to=Order, on_delete=models.PROTECT)
    grade = models.IntegerField(choices=GRADES)
    content = models.TextField(null=True)
    comment_time = models.DateTimeField(default=timezone.now)
    image_set = models.ManyToManyField(to=File)
