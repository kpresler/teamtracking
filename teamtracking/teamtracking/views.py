from django.shortcuts import render

# Create your views here.

from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework import status;
from rest_framework.decorators import action
from teamtracking.teamtracking.serializers import UserSerializer, GroupSerializer, TcrsQuestionSerializer, TcrsResponseSerializer;
from .models import TcrsQuestion, TcrsResponse, TcrsQuestionResponse;
from django.http import HttpResponse, JsonResponse;

import sys;
from datetime import datetime;

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
        
        possible_questions = TcrsQuestion.objects.filter(active=True);
        
        saved_responses = 0;
        skipped_responses = 0;
        
        for tcrs_response in request.data:
            print(tcrs_response);
            
            full_response = TcrsResponse();
            
            full_response.submit_date = datetime.now();
            full_response.course = tcrs_response['course'];
            full_response.section = tcrs_response['section'];
            full_response.team = tcrs_response['team'];
            full_response.submitter = tcrs_response['submitter'];
            full_response.iteration = tcrs_response['iteration'];
            
            possiblyMatching = TcrsResponse.objects.filter(course=full_response.course, section=full_response.section, team=full_response.team, iteration=full_response.iteration);
            
            print("Found " + str(possiblyMatching) + " in database already ");
            
            if possiblyMatching.exists():
                print("Skipping over this response");
                skipped_responses += 1;
                continue;
            
            full_response.save();
            
            for (question, response) in tcrs_response.items():
                print(question + "::" + response);
                matchingQuestion = [x for x in possible_questions if x.text == question];
                
                if matchingQuestion != []:
                    print("Matching question is: " + str(matchingQuestion));
                    question_response = TcrsQuestionResponse();
                    question_response.question = matchingQuestion[0];
                    question_response.response = response;
                    question_response.fullResponse = full_response;
                    question_response.save();
                    
            saved_responses += 1;                    

        response = (saved_responses, skipped_responses);
        
        sys.stdout.flush();
        return JsonResponse(response, safe=False, status=status.HTTP_200_OK);
    
    
    
def index(request):
    return render(request,"index.html");