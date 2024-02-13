from django.http import HttpRequest
from django.views.decorators.http import require_GET

from trade.exceptions import InvalidOrderByException, InvalidFilterException
from trade.models.Log import Log
from trade.query_util import query_filter, query_order_by, query_page, filter_order_and_list
from trade.util import response_wrapper, success_api_response, failed_api_response, ErrorCode, \
    require_jwt, data_export


def log_to_dict(log: Log) -> dict:
    data = {
        "id": log.id,
        "user_id": log.user_id,
        "user__nickname": log.user.nickname,
        "detail": log.detail,
        "op_time": log.op_time,
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
@query_filter(fields=[("id", int), ("user_id", int), ("user__nickname", str), ("detail", str), ("op_time", str)])
@query_order_by(fields=["op_time", "id", "user_id"])
@query_page(default=10)
def list_log(request: HttpRequest, *args, **kwargs):
    """
    [GET] /api/admin/log/list
    """
    logs = Log.objects.all()
    try:
        data = filter_order_and_list(logs, log_to_dict, **kwargs)
    except InvalidOrderByException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的order_by")
    except InvalidFilterException:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "不合法的filter")
    return success_api_response(data)


def log_to_dict_export(log: Log) -> dict:
    data = {
        "日志ID": log.id,
        "用户ID": log.user_id,
        "用户昵称": log.user.nickname,
        "操作简述": log.detail,
        "操作时间": log.op_time,
    }
    return data


@response_wrapper
@require_jwt(admin=True)
@require_GET
def export_log_list(request: HttpRequest):
    """
    [GET] /api/admin/log/list_csv
    """
    logs = Log.objects.all()
    columns = ["日志ID", "用户ID", "用户昵称", "操作简述", "操作时间"]
    filename = "日志.csv"
    return data_export(query_set=logs, columns=columns, model_to_dict=log_to_dict_export,
                       bom=request.GET.get("bom", None), filename=filename)
