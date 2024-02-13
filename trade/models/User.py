from datetime import timedelta

import jwt
from django.db import models
from django.utils import timezone

from DBProject import settings
from trade.models.File import File
from trade.models.Student import Student

ROLE_ADMIN = 0
ROLE_NORMAL_USER = 1


class User(models.Model):
    """
    用户模型：
    username: 用户名，其实就是账号
    password: 密码，这里存储的是加密后的密文
    nickname: 昵称
    reg_time: 注册时间
    phone_on: 电话
    email: 邮箱
    signature: 个性签名
    role: 角色，分为管理员和普通用户
    student: 认证关联的学生
    image: 头像
    valid: 是否有效，对于 valid = False 的账号，无法进行部分敏感操作
    """
    ROLE_TYPE = [
        (ROLE_ADMIN, "管理员"),
        (ROLE_NORMAL_USER, "普通用户"),
    ]

    username = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=128)
    nickname = models.CharField(max_length=30)
    reg_time = models.DateTimeField(default=timezone.now)
    phone_no = models.CharField(max_length=11, null=True)
    email = models.CharField(max_length=50)
    signature = models.CharField(max_length=50, null=True)
    role = models.IntegerField(choices=ROLE_TYPE, default=ROLE_NORMAL_USER)
    student = models.ForeignKey(to=Student, on_delete=models.SET_NULL, null=True)
    image = models.ForeignKey(to=File, on_delete=models.SET_NULL, null=True)
    valid = models.BooleanField(default=True)

    @property
    def token(self):
        token = jwt.encode({
            'exp': timezone.now() - timedelta(hours=8) + timedelta(hours=12),
            'iat': timezone.now() - timedelta(hours=8),
            'username': self.username,
            'role': self.role,
            'valid': self.valid
        }, settings.SECRET_KEY, algorithm='HS256')
        return token
