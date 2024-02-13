import re
from datetime import datetime

from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest
from django.views.decorators.http import require_POST, require_http_methods, require_GET

from trade.file_util import _validate_upload_file
from trade.models.Log import Log
from trade.models.User import User, ROLE_ADMIN
from trade.util import response_wrapper, success_api_response, failed_api_response, parse_data, ErrorCode, \
    require_keys, filter_data, require_jwt, get_user, validate_request, make_random_password, send_email

email_regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')


@response_wrapper
@require_POST
@require_keys({"username", "password"})
def login(request: HttpRequest):
    """
    [POST] /api/auth/login
    """
    data = parse_data(request)
    username = data["username"]
    password = data["password"]
    try:
        user = User.objects.get(username=username)
        if not check_password(password, user.password):
            return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "密码错误")
        token = user.token
        Log.objects.create(user=user, detail="用户登录")
        return success_api_response({"token": token, "role": user.role, "id": user.id})
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "用户不存在")


@response_wrapper
@require_POST
@require_keys({"username", "password", "nickname", "email"})
def register(request: HttpRequest):
    """
    [POST] /api/auth/register
    """
    data = parse_data(request)
    username = data["username"]
    if User.objects.filter(username=username).exists():
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "用户名已被注册")
    data["password"] = make_password(data["password"], None, 'pbkdf2_sha256')
    filter_data(data, {"username", "password", "nickname", "phone_no", "email", "signature"})
    user = User.objects.create(**data)
    Log.objects.create(user=user, detail="用户注册")
    return success_api_response({"id": user.id})


def parse_csv_file(file_path: str):
    """
    parse csv file and return content list
    :param file_path: csv file path
    :return: a list with content or error message, None if header is not correct
    return example:
    [
        {
            "valid": True,
            "username": "test",
            "nickname": "test",
            "password": "密文xxx",
            "email": "test@buaa.edu.cn"
        },
        {
            "valid": False,
            "line": 2,
            "error_msg": "缺少email"
        },
        {
            "valid": False,
            "line": 3,
            "error_msg": "密码太短"
        }
    ]
    """
    ret = []
    with open(file_path, "r") as file:
        lines = file.readlines()
    head = lines[0]
    temp = head.split(",")
    if temp[0].strip() != "username" or temp[1].strip() != "password" or \
            temp[2].strip() != "nickname" or temp[3].strip() != "email":
        return None
    for i in range(1, len(lines)):
        line = lines[i]
        temp = line.split(",")
        username = temp[0].strip()
        password = temp[1].strip()
        nickname = temp[2].strip()
        email = temp[3].strip()
        if len(username) == 0:
            ret.append({"valid": False, "error_msg": "缺少用户名", "line": i})
            continue
        if len(password) == 0:
            ret.append({"valid": False, "error_msg": "缺少密码", "line": i})
            continue
        if len(password) < 6:
            ret.append({"valid": False, "error_msg": "密码太短", "line": i})
            continue
        if len(password) > 25:
            ret.append({"valid": False, "error_msg": "密码太长", "line": i})
            continue
        if len(nickname) == 0:
            ret.append({"valid": False, "error_msg": "缺少昵称", "line": i})
            continue
        if len(email) == 0:
            ret.append({"valid": False, "error_msg": "缺少邮箱", "line": i})
            continue
        if re.fullmatch(email_regex, email) is None:
            ret.append({"valid": False, "error_msg": "不合法的邮箱", "line": i})
            continue
        if User.objects.filter(username=username).exists():
            ret.append({"valid": False, "error_msg": "用户名已存在", "line": i})
            continue
        ret.append({
            "valid": True,
            "username": username,
            "nickname": nickname,
            "email": email,
            "password": make_password(password, None, 'pbkdf2_sha256')
        })
    return ret


@response_wrapper
@require_jwt(admin=True)
@require_POST
@validate_request(func=_validate_upload_file)
def batch_register(request: HttpRequest):
    """
    [POST] /api/auth/batch/register
    """
    csv_file = request.FILES.get("file")
    if not csv_file.name.endswith(".csv"):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不是csv文件")
    if csv_file.multiple_chunks():
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "文件太大")
    with open("temp.csv", "wb") as file:
        for line in csv_file.chunks():
            file.write(line)
    user_detail = parse_csv_file("temp.csv")
    if user_detail is None:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的文件，请检查文件内容和表头")
    error_msg = []
    for user in user_detail:
        if user["valid"]:
            User.objects.create(username=user["username"], password=user["password"], nickname=user["nickname"],
                                email=user["email"])
        else:
            error_msg.append("第{}行：{}".format(user["line"], user["error_msg"]))
    Log.objects.create(user=get_user(request), detail="批量创建用户")
    if len(error_msg) == 0:
        return success_api_response()
    return success_api_response({"error_msg": error_msg})


@response_wrapper
@require_POST
@require_keys({"username", "password"})
def admin_login(request: HttpRequest):
    """
    [POST] /api/auth/admin/login
    """
    data = parse_data(request)
    username = data["username"]
    password = data["password"]
    try:
        user = User.objects.get(username=username)
        if user.role != ROLE_ADMIN:
            return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "非管理员用户")
        if not check_password(password, user.password):
            return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "密码错误")
        token = user.token
        Log.objects.create(user=user, detail="管理员登录")
        return success_api_response({"token": token})
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "用户不存在")


@response_wrapper
@require_jwt()
@require_http_methods(["PUT"])
@require_keys({"origin_pwd", "new_pwd"})
def update_password(request: HttpRequest):
    """
    [PUT] /api/auth/password/update
    """
    data = parse_data(request)
    origin_pwd = data["origin_pwd"]
    new_pwd = data["new_pwd"]
    user = get_user(request)
    if not check_password(origin_pwd, user.password):
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "原密码错误")
    user.password = make_password(new_pwd, None, 'pbkdf2_sha256')
    user.save()
    Log.objects.create(user=user, detail="用户修改密码")
    return success_api_response()


@response_wrapper
@require_GET
def check_user_name_exist(request: HttpRequest, username):
    """
    [GET] /api/auth/check_username/<str:username>
    """
    return success_api_response({"exist": User.objects.filter(username=username).exists()})


@response_wrapper
@require_POST
@require_keys({"username", "email"})
def reset_password(request: HttpRequest):
    """
    [POST] /api/auth/password/reset
    """
    data = parse_data(request)
    try:
        user = User.objects.get(username=data["username"])
    except ObjectDoesNotExist:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "用户名无效！")
    if user.email != data["email"]:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "邮箱错误！")
    new_pwd = make_random_password(16)
    title = "北航交易中心-重置用户密码"
    content = "{} 您好:\n\t您的北航交易中心账号 {} 密码已重置为 {} ，请您使用该密码登录并修改密码。".format(user.nickname, user.username, new_pwd)
    if not send_email(title, content, user.email):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "重置密码邮件发送失败，请联系管理员")
    user.password = make_password(new_pwd, None, 'pbkdf2_sha256')
    user.save()
    Log.objects.create(user=user, detail="用户修改密码")
    return success_api_response()
