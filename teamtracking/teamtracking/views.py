from django.shortcuts import render

# Create your views here.

from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.decorators import action
from teamtracking.teamtracking.serializers import UserSerializer, GroupSerializer, TcrsQuestionSerializer, TcrsResponseSerializer;
from .models import TcrsQuestion, TcrsResponse, TcrsQuestionResponse;
from django.http import HttpResponse;

import sys;

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    

class TcrsQuestionViewSet(viewsets.ModelViewSet):
    queryset = TcrsQuestion.objects.all();
    serializer_class = TcrsQuestionSerializer;
    permission_classes = [permissions.IsAuthenticated];
    
    
class TcrsResponseViewSet(viewsets.ModelViewSet):
    queryset = TcrsResponse.objects.all();
    serializer_class = TcrsResponseSerializer;
    permission_classes = [permissions.IsAuthenticated];
    
    @action(detail=False, methods=['post'])
    def process_responses(self, request):
        
        """The idea here is that we want to parse each line and turn it into a TCRS Response.  In order to be more flexible and not just support a hardcoded set of responses, we're going to pull a list of possible questions from the DB, and then match the question headers in the request to the questions supported"""
        
        possible_questions = TcrsQuestion.objects.all();
        print("There are " + str(len(possible_questions)) + " possible questions");
        for question in possible_questions:
            print("    " + str(question));
        print("\n\n\n\n");
        
        for tcrs_response in request.data:
            print(tcrs_response);
            
            full_response = TcrsResponse();
            
            for (question, response) in tcrs_response.items():
                print(question + "::" + response);
                matchingQuestion = [x for x in possible_questions if x.text == question];
                
                if matchingQuestion != []:
                    print("Matching question is: " + str(matchingQuestion));
                    question_response = TcrsQuestionResponse();
                    question_response.question = matchingQuestion[0];
                    question_response.response = response;
                    question_response.fullResponse = full_response;
                    
            print (full_response);
        
        sys.stdout.flush();
        return HttpResponse("ok");
    
    
    
def index(request):
    return render(request,"index.html");