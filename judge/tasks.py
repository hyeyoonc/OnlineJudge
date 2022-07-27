from celery import shared_task

from account.models import User
from submission.models import Submission
from judge.dispatcher import JudgeDispatcher
from utils.shortcuts import DRAMATIQ_WORKER_ARGS


@shared_task
def judge_task(submission_id, problem_id):
    uid = Submission.objects.get(id=submission_id).user_id
    if User.objects.get(id=uid).is_disabled:
        return
    JudgeDispatcher(submission_id, problem_id).judge()
