from django.conf.urls import url
from compilerun.views import CompileAPI

urlpatterns = [
    url(r"^compile_run/?$", CompileAPI.as_view(), name="compile_api"),
]
