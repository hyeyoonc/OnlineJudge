import logging
import time
from rest_framework.response import Response
from rest_framework import status

from account.decorators import login_required
from options.options import SysOptions
from compilerun.models import CompileRun
from compilerun.tasks import compile_run_task
from compilerun.serializers import CreateCompileRunSerializer, CompileRunModelSerializer
from problem.models import Problem
from utils.api import APIView, validate_serializer
from utils.throttling import TokenBucket
from utils.cache import cache


logger = logging.getLogger(__name__)


class CompileAPI(APIView):
    @validate_serializer(CreateCompileRunSerializer)
    @login_required
    def post(self, request):
        data = request.data
        print("=============data")
        print(data)
        try:
            input_data = data["input_data"]
        except:
            input_data = None
        problem_id = data.get("problem_id")
        try:
            problem = Problem.objects.get(id=problem_id)
        except Problem.DoesNotExist:
            return self.error("Problem does not exist")

        if len(data["code"]) == 0:
            message = "code: This field may not be blank."
            return Response({"message": message}, status=status.HTTP_400_BAD_REQUEST)

        compile_run = CompileRun.objects.create(
            user=request.user,
            language=data["language"],
            code=data["code"],
            input=input_data,
            problem=problem,
        )
        compile_run_task.delay(compile_run.id, problem_id)
        return self.success({"compile_run_id": compile_run.id})

    @login_required
    def get(self, request):
        compile_run_id = request.GET.get("id")
        if not compile_run_id:
            return self.error("compile_run_id doesn't exist")
        try:
            compile_run = CompileRun.objects.get(id=compile_run_id)
        except CompileRun.DoesNotExist:
            return self.error("CompileRun doesn't exist")

        if not compile_run.check_user_permission(request.user):
            return self.error("No permission for this submission")

        data = CompileRunModelSerializer(compile_run).data
        return self.success({"data": data})
