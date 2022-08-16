from compilerun.models import CompileRun
from utils.api import serializers
from judge.languages import language_names


class CreateCompileRunSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=1024 * 1024)
    input_data = serializers.CharField(max_length=1024 * 1024, allow_blank=True)
    language = serializers.ChoiceField(choices=language_names)
    email = serializers.CharField(max_length=100)


class CompileRunModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompileRun
        fields = "__all__"
