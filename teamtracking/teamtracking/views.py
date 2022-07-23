from django.shortcuts import render

# Create your views here.

from django.contrib.auth.models import User, Group
from django.http import HttpResponse, JsonResponse;
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction;
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework import status;
from rest_framework.decorators import action
from rest_framework import generics;


from teamtracking.teamtracking.serializers import UserSerializer, GroupSerializer, TcrsQuestionSerializer, TcrsResponseSerializer, IterationSerializer;
from .models import TcrsQuestion, TcrsResponse, TcrsQuestionResponse, Iteration;

from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk import tokenize

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
    
    
class IterationViewSet(viewsets.ModelViewSet):
    queryset = Iteration.objects.all();
    serializer_class = IterationSerializer;
    permission_classes = [permissions.IsAuthenticated];    
    
    
class TcrsResponseViewSet(viewsets.ModelViewSet):
    queryset = TcrsResponse.objects.all();
    serializer_class = TcrsResponseSerializer;
    permission_classes = [permissions.IsAuthenticated];
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def process_responses(self, request):
        
        """The idea here is that we want to parse each line and turn it into a TCRS Response.  In order to be more flexible and not just support a hardcoded set of responses, we're going to pull a list of possible questions from the DB, and then match the question headers in the request to the questions supported"""
        
        """Pull a list of all currently active questions; match questions in the submitted TCRS against these"""
        possible_questions = TcrsQuestion.objects.filter(active=True);
        
        """For tracking how many responses were parsed & saved and how many were duplicates (from previous submissions) & skipped"""
        saved_responses = 0;
        skipped_responses = 0;
        
        sid = SentimentIntensityAnalyzer();
        
        """Traverse over all responses submitted.  The JSON has the header used as object labels in each record, which is super nice"""
        for tcrs_response in request.data:
            print(tcrs_response);
            
            
            """Fill in response that is tracked across the entire TCRS response"""
            full_response = TcrsResponse();
            full_response.submit_date = datetime.now();
            full_response.course = tcrs_response['course'];
            full_response.section = tcrs_response['section'];
            full_response.team = tcrs_response['team'];
            full_response.submitter = tcrs_response['submitter'];
            full_response.iteration = Iteration.objects.filter(displayed_value=tcrs_response['iteration']).get();
            full_response.score = 0;
            
            """Is this a duplicate against one that has already been saved?  If so, skip it"""
            possiblyMatching = TcrsResponse.objects.filter(course=full_response.course, section=full_response.section, team=full_response.team, iteration=full_response.iteration,submitter=full_response.submitter);
            if possiblyMatching.exists():
                print("Skipping over this response");
                skipped_responses += 1;
                continue;
            
            
            full_response.save();
            
            response_score = 0;
            
            """Traverse over all of the responses to individual questions"""
            for (question, response) in tcrs_response.items():
                print(question + "::" + response);
                matchingQuestions = [x for x in possible_questions if x.text == question];
                
                
                if matchingQuestions != []:
                    matching_question = matchingQuestions[0];
                    print("Matching question is: " + str(matching_question));
                    question_response = TcrsQuestionResponse();
                    question_response.question = matching_question;
                    question_response.response = response;
                    question_response.fullResponse = full_response;
                    question_response.save();
                    scoreFromQuestion = 0;
                    if matching_question.qType == "p":
                        if "agree" in response.lower():
                            scoreFromQuestion = 2;
                        elif "disagree" in response.lower():
                            scoreFromQuestion = -2;
                        if "strongly" in response.lower():
                            scoreFromQuestion *= 2;
                    elif matching_question.qType == "n":
                        if "agree" in response.lower():
                            scoreFromQuestion = -2;
                        elif "disagree" in response.lower():
                            scoreFromQuestion = 2;
                        if "strongly" in response.lower():
                            scoreFromQuestion *=2;
                    elif matching_question.qType == "t" and not response.strip():
                        """Text questions are natural language processed, as long as they exist :magier: """
                        sentiment_scores = sid.polarity_scores(response);
                        """TODO: These magic numbers seem to work decently well but could stand to be revisited"""
                        if ss["neg"] > 0 and ss["pos"] < .5: 
                            """ kekw.  this is a way to force the score into negative if it's flagged through the natural language parser"""
                            scoreFromQuestion -= 100;
                        # endif
                    #end elif
                
                    
                    response_score += scoreFromQuestion;
                #end if
            
            #end for     
            saved_responses += 1;                    
            full_response.score = response_score;
            full_response.save();
            print(str(full_response));
        #end for

        response = (saved_responses, skipped_responses);
        
        sys.stdout.flush();
        return JsonResponse(response, safe=False, status=status.HTTP_200_OK);
    #end method
    
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def team_data(self, request):
        
        resp = {};

        """First, go load in all matching TCRS responses"""
        section = request.data['section'];
        team = request.data['teamNumber'];
        iteration = Iteration.objects.filter(displayed_value=request.data['iteration']).get();
        course = request.data['course'];
        matchingResponses = TcrsResponse.objects.filter(course=course, section=section, team=team, iteration=iteration).values();
        
        
        
        """Compute a change in sentiment since last week, if the data exists"""
        
        """Find matching responses from last week to compute a change in sentiment"""
        lastIteration = None;
        try:
            lastIteration = Iteration.objects.filter(sequential_value=iteration.sequential_value-1).get();
        except ObjectDoesNotExist:
            pass;
        
        
        responsesLastIteration = None;
        if lastIteration:
            responsesLastIteration = TcrsResponse.objects.filter(course=course, section=section, team=team, iteration=lastIteration).values();
            
            
       
        scoresThisWeek = [x['score'] for x in matchingResponses];
        sentimentThisWeek = sum(scoresThisWeek)/len(scoresThisWeek);
        
        sentimentChange = dict();
        
        if responsesLastIteration:
            scoresLastWeek = [x['score'] for x in responsesLastIteration];
            sentimentLastWeek = sum(scoresLastWeek)/len(scoresLastWeek);
            sentimentChange['change'] = sentimentThisWeek - sentimentLastWeek;
            sentimentChange['this'] = sentimentThisWeek;
            sentimentChange['last'] = sentimentLastWeek;
        else:
            sentimentChange['change'] = "No Data";
            sentimentChange['this'] = sentimentThisWeek;
        
        resp['sentimentChange'] = sentimentChange;
        
        """End calculate change in sentiment"""
        

        """Then, find responses to specific questions"""

        tcrsDetails = dict();
                       
        """MatchingResponses is all individual TCRS submissions....need to go through each one to pull in the associated questions"""
        for matchingResponse in matchingResponses:
            print("Looking for Question Responses for TCRS #" + str(matchingResponse['id']));
            
            respForUser = [];
            
            """This pulls in the responses to individual questions"""
            individualResponses = TcrsQuestionResponse.objects.select_related().filter(fullResponse = matchingResponse['id']).all();
            print("Type of response:" + str(type(individualResponses)));
            for response in individualResponses:
                """And finally prepare JSON data for the answer to each question"""
                respForUser.append(response.responseToDictionary());
            tcrsDetails[matchingResponse['submitter']] = respForUser;
            
        resp["tcrsDetails"] = tcrsDetails;
        
        
        
        """Get sentiment from each person for each week"""
        
        teamResponsesAllIterations = TcrsResponse.objects.filter(course=course, section=section, team=team).values();
        
        print("\n\n\n\n");
        print(teamResponsesAllIterations);
        print("\n\n\n\n");
        
        iterationsWithResponses = [x['iteration_id'] for x in teamResponsesAllIterations];
        uniqueIterationIds = list(dict.fromkeys(iterationsWithResponses))
        
        uniqueIterations = [];
        for iterationId in uniqueIterationIds:
            uniqueIterations.append(Iteration.objects.filter(id=iterationId).get());
        
        uniqueIterations.sort(key=lambda x: x.sequential_value)
        
        resp["sentimentLabels"] = [x.displayed_value for x in uniqueIterations];
        
        
        sentiments = dict();
        
        membersOfTeam = [x['submitter'] for x in teamResponsesAllIterations];
        
        for member in membersOfTeam:
            responses = [];
            for iteration in uniqueIterations:
                try:
                    response = TcrsResponse.objects.filter(course=course, section=section, team=team, iteration=iteration, submitter=member).get();
                    responses.append(response.score);
                except ObjectDoesNotExist:
                    responses.append(None);
            sentiments[member] = responses;
        
        
        print(sentiments);
        
        resp["sentimentDetails"] = sentiments;
        
        sys.stdout.flush();
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK);        
        
#end class
    
    
def loadTCRS(request):
    return render(request,"loadTCRS.html");


def index(request):
    return render(request,"index.html");

def teamDetails(request):
    return render(request,"viewTeamDetails.html");