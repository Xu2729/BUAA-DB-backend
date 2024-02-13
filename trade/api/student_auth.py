from django.http import HttpRequest
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from trade.exceptions import InvalidOrderByException, InvalidFilterException
from trade.file_util import s3_download_url
from trade.models.Log import Log
from trade.models.status import AUTH_REQ_STATUS_PASSED, AUTH_REQ_STATUS_DENIED
from trade.models.StuAuthReq import StuAuthReq
from trade.models.Student import Student
from trade.models.File import File
from trade.models.User import User, ROLE_ADMIN
from trade.query_util import query_filter, query_order_by, query_page, filter_order_and_list
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    filter_data, require_jwt, require_item_exist, require_keys, wrapped_api, get_user


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"student_id", "student_name", "depart", "attendance_year", "gender", "image_id"})
def create_student_auth_req(request: HttpRequest):
    """
    [POST] /api/student/auth_req
    """
    data = parse_data(request)
    image_id = data["image_id"]
    if not File.objects.filter(id=image_id).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "没有找到相应的图片")
    filter_data(data, {"student_id", "student_name", "depart", "attendance_year", "gender"})
    if Student.objects.filter(id=data["student_id"]).exists():
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "该学号已存在")
    data["user"] = get_user(request)
    data["admin"] = User.objects.filter(role=ROLE_ADMIN).first()
    data["image"] = File.objects.get(id=image_id)
    student_req = StuAuthReq.objects.create(**data)
    Log.objects.create(user=get_user(request), detail="发起学生认证请求ID:{}".format(student_req.id))
    return success_api_response({"id": student_req.id, "admin_id": student_req.admin.id,
                                 "admin__nickname": student_req.admin.nickname})


def student_auth_req_to_dict(student_auth_req: StuAuthReq) -> dict:
    data = {
        "id": student_auth_req.id,
        "admin_id": student_auth_req.admin.id,
        "admin__nickname": student_auth_req.admin.nickname,
        "status": student_auth_req.status,
        "req_time": student_auth_req.req_time,
        "student_id": student_auth_req.student_id
    }
    return data


@response_wrapper
@require_jwt()
@require_GET
def get_student_auth_reqs(request: HttpRequest):
    """
    [GET] /api/student/auth_req
    """
    user = get_user(request)
    auths = StuAuthReq.objects.filter(user=user)
    data = list(map(student_auth_req_to_dict, auths))
    return success_api_response({"req_count": auths.count(), "auth_reqs": data})


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(StuAuthReq, "id", "query_id")
def get_student_auth_req_detail(request: HttpRequest, query_id):
    """
    [GET] /api/student/auth_req/detail/<int:query_id>
    """
    req = StuAuthReq.objects.get(id=query_id)
    data = {
        "user_id": req.user.id,
        "user__nickname": req.user.nickname,
        "student_id": req.student_id,
        "student_name": req.student_name,
        "depart": req.depart,
        "attendance_year": req.attendance_year,
        "gender": req.gender,
        "admin_id": req.admin.id,
        "admin__nickname": req.admin.nickname,
        "req_time": req.req_time,
        "comment": req.comment,
        "deal_time": req.deal_time,
        "status": req.status,
        "image_url": s3_download_url(req.image.oss_token),
    }
    return success_api_response(data)


def admin_student_auth_req_to_dict(student_auth_req: StuAuthReq) -> dict:
    data = {
        "id": student_auth_req.id,
        "user_id": student_auth_req.user.id,
        "user__nickname": student_auth_req.user.nickname,
        "status": student_auth_req.status,
        "req_time": student_auth_req.req_time,
        "student_id": student_auth_req.student_id,
        "student_name": student_auth_req.student_name
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
@query_filter(fields=[("id", int), ("user_id", int), ("user__nickname", str), ("status", int), ("req_time", str),
                      ("student_id", str), ("student_name", str)])
@query_order_by(fields=["req_time", "id", "student_id", "user_id"])
@query_page(default=10)
def get_admin_student_auth_reqs(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/admin/student/auth_req/list
    """
    user = get_user(request)
    reqs = StuAuthReq.objects.filter(admin=user)
    try:
        data = filter_order_and_list(reqs, admin_student_auth_req_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


@response_wrapper
@require_jwt(admin=True)
@require_GET
@require_item_exist(StuAuthReq, "id", "query_id")
def admin_get_student_auth_req_detail(request: HttpRequest, query_id):
    """
    [GET] /api/admin/student/auth_req/detail/<int:query_id>
    """
    req = StuAuthReq.objects.get(id=query_id)
    data = {
        "id": req.id,
        "user_id": req.user.id,
        "user__nickname": req.user.nickname,
        "status": req.status,
        "req_time": req.req_time,
        "student_id": req.student_id,
        "student_name": req.student_name,
        "depart": req.depart,
        "attendance_year": req.attendance_year,
        "gender": req.gender,
        "image_url": s3_download_url(req.image.oss_token),
    }
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_GET
def check_student_id_exist(request: HttpRequest, query_id):
    """
    [GET] /api/student/auth_req/check_id/<int:query_id>
    """
    return success_api_response({"exist": Student.objects.filter(id=query_id).exists()})


@response_wrapper
@require_jwt(admin=True)
@require_http_methods(["PUT"])
@require_item_exist(StuAuthReq, "id", "query_id")
@require_keys({"pass", "comment"})
def admin_update_student_auth_req_status(request: HttpRequest, query_id):
    """
    [PUT] /api/admin/student/auth_req/detail/<int:query_id>
    """
    req = StuAuthReq.objects.get(id=query_id)
    data = parse_data(request)
    req.deal_time = timezone.now()
    req.comment = data["comment"]
    if data["pass"]:
        req.status = AUTH_REQ_STATUS_PASSED
        req.save()
        student = Student.objects.create(id=req.student_id, name=req.student_name, depart=req.depart,
                                         attendance_year=req.attendance_year, gender=req.gender)
        req.user.student = student
        req.user.save()
        Log.objects.create(user=get_user(request), detail="通过学生认证请求ID:{}".format(query_id))
    else:
        req.status = AUTH_REQ_STATUS_DENIED
        req.save()
        Log.objects.create(user=get_user(request), detail="拒绝学生认证请求ID:{}".format(query_id))
    return success_api_response()


ADMIN_STUDENT_AUTH_REQ_API = wrapped_api({
    "GET": admin_get_student_auth_req_detail,
    "PUT": admin_update_student_auth_req_status,
})
