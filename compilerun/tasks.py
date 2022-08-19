from __future__ import absolute_import, unicode_literals
from celery import shared_task
from compilerun.dispatcher import CompileRunDispatcher
import logging

logger = logging.getLogger(__name__)


@shared_task
def compile_run_task(compile_run_id, problem_id):
    CompileRunDispatcher(compile_run_id, problem_id).do_compile_run()
