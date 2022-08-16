import logging
import time
from rest_framework.response import Response
from rest_framework import status

from account.decorators import login_required
from options.options import SysOptions
from compilerun.models import CompileRun
from compilerun.tasks import compile_run_task
from compilerun.serializers import CreateCompileRunSerializer, CompileRunModelSerializer
from utils.api import APIView, validate_serializer
from utils.throttling import TokenBucket
from utils.cache import cache


logger = logging.getLogger(__name__)


class CompileAPI(APIView):
    @validate_serializer(CreateCompileRunSerializer)
    @login_required
    def post(self, request):
        data = request.data

        try:
            input_data = data["input_data"]
        except:
            input_data = None

        if len(data["code"]) == 0:
            message = "code: This field may not be blank."
            return Response({"message": message}, status=status.HTTP_400_BAD_REQUEST)

        compile_run = CompileRun.objects.create(
            user=request.user,
            language=data["language"],
            code=data["code"],
            input_data=input_data,
        )
        compile_run_task.delay(
            compile_run.id, alms_back_current_url=data["alms_back_current_url"]
        )
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
