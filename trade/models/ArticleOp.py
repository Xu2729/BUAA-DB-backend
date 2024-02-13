from django.db import models
from django.utils import timezone

from trade.models.Article import Article
from trade.models.User import User

ARTICLE_OP_GOOD = 0
ARTICLE_OP_COLLECT = 1


class ArticleOp(models.Model):
    """
    文章操作记录：
    op: 对文章的操作，如：赞，踩，收藏
    user: 操作的用户
    article: 操作的文章
    op_time: 操作的时间
    """
    ARTICLE_OPS = [
        (ARTICLE_OP_GOOD, "赞"),
        (ARTICLE_OP_COLLECT, "收藏"),
    ]

    op = models.IntegerField(choices=ARTICLE_OPS)
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    article = models.ForeignKey(to=Article, on_delete=models.CASCADE)
    op_time = models.DateTimeField(default=timezone.now)
