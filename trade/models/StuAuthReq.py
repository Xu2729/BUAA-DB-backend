from django.db import models
from django.utils import timezone

from trade.models.File import File
from trade.models.Student import Student
from trade.models.User import User
from .status import AUTH_REQ_STATUS_WAITING, AUTH_REQ_STATUSES


class StuAuthReq(models.Model):
    """
    学生认证请求模型：
    user: 申请人
    student_id: 学号
    student_name: 真实姓名
    depart: 院系
    attendance_year: 入学年份
    gender: 性别
    admin: 分配的管理员
    status: 状态
    req_time: 申请时间
    comment: 管理员审核信息
    deal_time: 处理时间
    """
    user = models.ForeignKey(to=User, related_name='student_stu_reqs', on_delete=models.PROTECT)

    student_id = models.CharField(max_length=12)
    student_name = models.CharField(max_length=10)
    depart = models.IntegerField(choices=Student.DEPARTS)
    attendance_year = models.IntegerField()
    gender = models.IntegerField(choices=Student.GENDERS)

    image = models.ForeignKey(to=File, on_delete=models.PROTECT)
    admin = models.ForeignKey(to=User, related_name='admin_stu_reqs', on_delete=models.PROTECT)
    status = models.IntegerField(choices=AUTH_REQ_STATUSES, default=AUTH_REQ_STATUS_WAITING)
    req_time = models.DateTimeField(default=timezone.now)
    comment = models.CharField(max_length=200, null=True)
    deal_time = models.DateTimeField(null=True)
