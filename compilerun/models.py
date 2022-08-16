from django.db import models
from utils.models import JSONField
from account.models import User
from problem.models import Problem


class CompileRunStatus:
    COMPILE_ERROR = -2
    WRONG_ANSWER = -1
    ACCEPTED = 0
    CPU_TIME_LIMIT_EXCEEDED = 1
    REAL_TIME_LIMIT_EXCEEDED = 2
    MEMORY_LIMIT_EXCEEDED = 3
    RUNTIME_ERROR = 4
    SYSTEM_ERROR = 5
    PENDING = 6
    JUDGING = 7
    PARTIALLY_ACCEPTED = 8


class CompileRun(models.Model):
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField("수정 일시", auto_now=True)
    input_data = models.TextField(default="", null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    username = models.TextField()
    code = models.TextField()
    result = models.IntegerField(db_index=True, default=CompileRunStatus.PENDING)
    info = JSONField(default=dict)
    language = models.TextField()
    error_message = models.TextField(default="", blank=True)  # std_out
    error = models.CharField(max_length=140, blank=True)
    memory = models.BigIntegerField(default=0)
    cpu_time = models.IntegerField(default=0)
    real_time = models.IntegerField(default=0)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)

    def check_user_permission(self, user):
        return (
            self.user_id == user.id
            or user.is_super_admin()
            or user.can_mgmt_all_problem()
        )

    class Meta:
        db_table = "compile_run"
        ordering = ("-create_time",)

    def __str__(self):
        return self.id
