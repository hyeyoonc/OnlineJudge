import hashlib
import json
import logging
import re
from time import sleep
from urllib.parse import urljoin

import requests
from django.db import transaction
from django.db.models import F
from django.conf import settings
from conf.models import JudgeServer
from judge.languages import languages
from submission.models import JudgeStatus
from options.options import SysOptions
from compilerun.models import CompileRunStatus, CompileRun
from utils.cache import cache
from utils.constants import CacheKey

logger = logging.getLogger(__name__)


# 继续处理在队列中的问题
def process_pending_task():
    if cache.llen(CacheKey.waiting_queue):
        # 防止循环引入c
        from compilerun.tasks import compile_run_task

        data = json.loads(cache.rpop(CacheKey.waiting_queue).decode("utf-8"))
        compile_run_task.delay(**data)


class DispatcherBase(object):
    def __init__(self):
        self.token = hashlib.sha256(
            SysOptions.judge_server_token.encode("utf-8")
        ).hexdigest()

    def _request(self, url, data=None):
        kwargs = {"headers": {"X-Judge-Server-Token": self.token}}
        if data:
            kwargs["json"] = data
        try:
            return requests.post(url, **kwargs).json()
        except Exception as e:
            logger.exception(e)

    @staticmethod
    def choose_compile_run_server():
        with transaction.atomic():
            servers = (
                JudgeServer.objects.select_for_update()
                .filter(is_disabled=False)
                .order_by("task_number")
            )
            servers = [s for s in servers if s.status == "normal"]
            if servers:
                server = servers[0]
                server.used_instance_number = F("task_number") + 1
                server.save()
                return server

    @staticmethod
    def release_judge_server(judge_server_id):
        with transaction.atomic():
            # 使用原子操作, 同时因为use和release中间间隔了判题过程,需要重新查询一下
            server = JudgeServer.objects.get(id=judge_server_id)
            server.used_instance_number = F("task_number") - 1
            server.save()


class CompileRunDispatcher(DispatcherBase):
    def __init__(self, compile_run_id, alms_back_current_url=None):
        super().__init__()
        self.compile_run = CompileRun.objects.get(id=compile_run_id)
        self.alms_back_current_url = alms_back_current_url

    def _compute_statistic_info(self, resp_data):
        # 用时和内存占用保存为多个测试点中最长的那个
        self.compile_run.statistic_info["time_cost"] = max(
            [x["cpu_time"] for x in resp_data]
        )
        self.compile_run.statistic_info["memory_cost"] = max(
            [x["memory"] for x in resp_data]
        )

    def do_compile_run(self):
        server = self.choose_compile_run_server()
        if not server:
            data = {"compile_run_id": self.compile_run.id}
            cache.lpush(CacheKey.waiting_queue, json.dumps(data))
            return

        language = self.compile_run.language
        compile_run_config = list(
            filter(lambda item: language == item["name"], languages)
        )[0]
        code = self.compile_run.code
        input_data = self.compile_run.input_data

        data = {
            "language_config": compile_run_config["config"],
            "code": code,
            "max_cpu_time": 1000 * 5,  # 3 seconds
            "max_memory": 1024 * 1024 * 256,  # 10MB? -> 128 (?)
            "compile_run_id": self.compile_run.id,
            "output": False,
            "input_data": input_data,
        }

        self.compile_run.result = CompileRunStatus.JUDGING
        resp = self._request(urljoin(server.service_url, "/compile_run"), data=data)

        patch_data = {
            "output": "",
            "result": "",
            "error": "OK",
            "memory": 0,
            "cpu_time": 0,
            "real_time": 0,
            "error_message": "",
        }
        # 에러가 발생할 경우

        if resp["err"]:
            self.compile_run.result = CompileRunStatus.COMPILE_ERROR
            patch_data["error"] = "Compile Error"
            patch_data["result"] = CompileRunStatus.COMPILE_ERROR
            patch_data["error_message"] = resp["data"]
        else:
            self.compile_run.info = resp
            # COMPILE_ERROR = -2
            # WRONG_ANSWER = -1
            # ACCEPTED = 0
            # CPU_TIME_LIMIT_EXCEEDED = 1
            # REAL_TIME_LIMIT_EXCEEDED = 2
            # MEMORY_LIMIT_EXCEEDED = 3
            # RUNTIME_ERROR = 4
            # SYSTEM_ERROR = 5
            # PENDING = 6
            # JUDGING = 7
            # PARTIALLY_ACCEPTED = 8
            execution_result = self.compile_run.info["data"][0]
            self.compile_run.result = execution_result["result"]
            patch_data["output"] = execution_result["output"]
            patch_data["result"] = execution_result["result"]
            patch_data["error"] = execution_result["error"]
            patch_data["memory"] = execution_result["memory"]
            patch_data["cpu_time"] = execution_result["cpu_time"]
            patch_data["real_time"] = execution_result["real_time"]

        self.compile_run.save()

        compile_run = CompileRun.objects.get(id=self.compile_run.id)
        # ALMS_BASE_URL = settings.ALMS_BACK_BASE_URL
        ALMS_BASE_URL = self.alms_back_current_url
        alms_compile_run_url = ALMS_BASE_URL + "qjudge/compile_run/"

        headers = {
            "content-type": "application/json",
        }
        qj_compile_run_id = self.compile_run.id

        # alms compile_run update API call
        for i in range(3):
            response = requests.patch(
                alms_compile_run_url + qj_compile_run_id + "/",
                data=json.dumps(patch_data),
                headers=headers,
                verify=False,
            )
            if response.status_code < 400:
                break
            sleep(1)

        self.release_judge_server(server.id)

        # 至此判题结束，尝试处理任务队列中剩余的任务
        process_pending_task()
