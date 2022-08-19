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
from problem.models import Problem
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
    def __init__(self, compile_run_id, problem_id):
        super().__init__()
        self.compile_run = CompileRun.objects.get(id=compile_run_id)
        self.problem = Problem.objects.get(id=problem_id)

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
        input_data = self.compile_run.input

        data = {
            "language_config": compile_run_config["config"],
            "code": code,
            "max_cpu_time": self.problem.time_limit,  # 3 seconds 1000 * 5
            "max_memory": 1024 * 1024 * self.problem.memory_limit,  # 10MB? -> 128 (?)
            "compile_run_id": self.compile_run.id,
            "output": False,
            "input_data": input_data,
        }

        self.compile_run.result = CompileRunStatus.JUDGING
        resp = self._request(urljoin(server.service_url, "/compile_run"), data=data)
        # 에러가 발생할 경우
        if resp["err"]:
            self.compile_run.result = CompileRunStatus.COMPILE_ERROR
            self.compile_run.error = CompileRunStatus.COMPILE_ERROR
            self.compile_run.error_message = resp["data"]
        else:
            execution_result = resp["data"][0]
            self.compile_run.result = execution_result["result"]
            self.compile_run.output = execution_result["output"]
            self.compile_run.result = execution_result["result"]
            self.compile_run.error = execution_result["error"]
            self.compile_run.cpu_time = execution_result["cpu_time"]
            self.compile_run.memory = execution_result["memory"]
            self.compile_run.real_time = execution_result["real_time"]
        self.compile_run.save()
        self.release_judge_server(server.id)

        # 큐에 남아있는 task 처리
        process_pending_task()
