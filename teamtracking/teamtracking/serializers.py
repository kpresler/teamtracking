from django.contrib.auth.models import User, Group
from rest_framework import serializers

from .models import TcrsQuestion, TcrsResponse, Iteration


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ["url", "username", "email", "groups"]


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]


class TcrsQuestionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TcrsQuestion
        fields = ["text", "qType", "active"]


class TcrsResponseSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TcrsResponse
        fields = ["submit_date", "course", "section", "team", "submitter"]


class IterationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Iteration
        fields = ["displayed_value", "sequential_value"]
