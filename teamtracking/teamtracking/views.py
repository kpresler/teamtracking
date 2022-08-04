from django.shortcuts import render

# Create your views here.

from django.contrib.auth.models import User, Group
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework import generics


from teamtracking.teamtracking.serializers import (
    UserSerializer,
    GroupSerializer,
    TcrsQuestionSerializer,
    TcrsResponseSerializer,
    IterationSerializer,
    NoteSerializer,
    TeamSerializer,
)
from .models import (
    TcrsQuestion,
    TcrsResponse,
    TcrsQuestionResponse,
    Iteration,
    Note,
    Team,
    negative_sentiment_penalty,
)

from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk import tokenize

import sys
from datetime import datetime


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    queryset = User.objects.all().order_by("-date_joined")
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
    queryset = TcrsQuestion.objects.all()
    serializer_class = TcrsQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]


class IterationViewSet(viewsets.ModelViewSet):
    queryset = Iteration.objects.all()
    serializer_class = IterationSerializer
    permission_classes = [permissions.IsAuthenticated]


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def assigned_ta(self, request):

        team = Team.objects.filter(id=request.data["team"]).get()

        ta = username = request.data.get("ta")

        if ta:
            team.assigned_TA = User.objects.filter(username=ta).get()
            team.save()
        else:
            team.assigned_TA = None
            team.save()

        return JsonResponse(
            "TA assignment for {} updated successfully".format(team),
            safe=False,
            status=status.HTTP_200_OK,
        )


class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def new_note(self, request):
        """DRF will magic up a POST method for us already, but this lets us specify how we want some of the fields to be filled in"""

        note = Note()

        team = Team.objects.filter(
            course=request.data["course"],
            section=request.data["section"],
            team=request.data["team"],
        ).get()

        note.note_text = request.data["text"]
        note.team = team
        note.submit_date = datetime.now()
        note.submitter = request.user

        note.save()

        return JsonResponse(
            "Note for {} created successfully".format(note.team),
            safe=False,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def for_team(self, request):
        course = request.data["course"]
        section = request.data["section"]
        team = request.data["team"]

        matching = (
            Note.objects.filter(
                team__course=course, team__section=section, team__team=team
            )
            .order_by("-submit_date")
            .all()
        )

        resp = []

        for note in matching:
            """Derpy JSON serialisation hurting us again..."""
            resp.append(note.toDict())

        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)


class TcrsResponseViewSet(viewsets.ModelViewSet):
    queryset = TcrsResponse.objects.all()
    serializer_class = TcrsResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def process_responses(self, request):

        """The idea here is that we want to parse each line and turn it into a TCRS Response.  In order to be more flexible and not just support a hardcoded set of responses, we're going to pull a list of possible questions from the DB, and then match the question headers in the request to the questions supported"""

        """Pull a list of all currently active questions; match questions in the submitted TCRS against these"""
        possible_questions = TcrsQuestion.objects.filter(active=True)

        """For tracking how many responses were parsed & saved and how many were duplicates (from previous submissions) & skipped"""
        saved_responses = 0
        skipped_responses = 0

        sid = SentimentIntensityAnalyzer()

        """Traverse over all responses submitted.  The JSON has the header used as object labels in each record, which is super nice"""

        # TCRS responses where the NLP found negative sentiment.  It's not particularly good, so kick these back to the user to double-check :)
        needs_checking = []

        for tcrs_response in request.data:
            print(tcrs_response)

            try:
                print(
                    "Searching for a team matching {}-{}-{}".format(
                        tcrs_response["course"],
                        tcrs_response["section"],
                        tcrs_response["team"],
                    )
                )
                team = Team.objects.filter(
                    course=tcrs_response["course"],
                    section=tcrs_response["section"],
                    team=tcrs_response["team"],
                ).get()
            except ObjectDoesNotExist:
                print("Matching team not found -- creating!")
                team = Team()
                team.course = tcrs_response["course"]
                team.section = tcrs_response["section"]
                team.team = tcrs_response["team"]
                team.save()

            """Fill in response that is tracked across the entire TCRS response"""
            full_response = TcrsResponse()
            full_response.submit_date = datetime.now()
            full_response.team = team
            full_response.submitter = tcrs_response["submitter"]
            full_response.iteration = Iteration.objects.filter(
                displayed_value=tcrs_response["iteration"]
            ).get()
            full_response.score = 0

            """Is this a duplicate against one that has already been saved?  If so, skip it"""
            possiblyMatching = TcrsResponse.objects.filter(
                team=team,
                iteration=full_response.iteration,
                submitter=full_response.submitter,
            )
            if possiblyMatching.exists():
                print("Skipping over this response")
                skipped_responses += 1
                continue

            full_response.save()

            response_score = 0

            # Traverse over all of the responses to individual questions
            for (question, response) in tcrs_response.items():
                print(question + "::" + response)
                matchingQuestions = [
                    x for x in possible_questions if x.text == question
                ]

                if matchingQuestions != []:
                    matching_question = matchingQuestions[0]
                    print("Matching question is: " + str(matching_question))
                    print("Matching question type: " + matching_question.qType)
                    question_response = TcrsQuestionResponse()
                    question_response.question = matching_question
                    question_response.response = response
                    question_response.fullResponse = full_response
                    question_response.save()
                    scoreFromQuestion = 0
                    # Have to check disagree first...otherwise it find "agree" as a substring in disagree and does stupid stuff.  Want to guess how we figured out this one? :)
                    if matching_question.qType == "p":
                        if "disagree" in response.lower():
                            scoreFromQuestion = -2
                        elif "agree" in response.lower():
                            scoreFromQuestion = 2
                        if "strongly" in response.lower():
                            scoreFromQuestion *= 2
                    elif matching_question.qType == "n":
                        if "disagree" in response.lower():
                            scoreFromQuestion = 2
                        elif "agree" in response.lower():
                            scoreFromQuestion = -2
                        if "strongly" in response.lower():
                            scoreFromQuestion *= 2
                    elif matching_question.qType == "t" and response.strip():
                        print("Processing natural language question")
                        # Text questions are natural language processed, as long as they exist :magier:
                        sentiment_scores = sid.polarity_scores(response)
                        # TODO: These magic numbers seem to work decently well but could stand to be revisited
                        if (
                            sentiment_scores["neg"] > 0
                            and sentiment_scores["pos"] < 0.5
                        ):
                            # kekw.  this is a way to force the score into negative if it's flagged through the natural language parser
                            scoreFromQuestion += negative_sentiment_penalty
                            flagged = dict()
                            flagged["text"] = response
                            flagged["tcrsID"] = full_response.id
                            needs_checking.append(flagged)
                        # endif
                    # end elif

                    response_score += scoreFromQuestion
                # end if

            # end for
            saved_responses += 1
            full_response.score = response_score
            full_response.save()
            # print(str(full_response))
        # end for

        response = dict()
        response["saved"] = saved_responses
        response["skipped"] = skipped_responses
        response["needs_checking"] = needs_checking

        sys.stdout.flush()
        return JsonResponse(response, safe=False, status=status.HTTP_200_OK)

    # end method

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def toggle_sentiment(self, request):

        tcrs_response = TcrsResponse.objects.filter(id=request.data["tcrsID"]).get()

        isNegative = request.data["isNegative"]

        # negative_sentiment_penalty is a negative number, so add it to force a lower score, subtract it to give a higher one

        if isNegative:
            tcrs_response.score += negative_sentiment_penalty

        else:
            tcrs_response.score -= negative_sentiment_penalty

        tcrs_response.save()

        resp = dict()
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def team_data(self, request):
        resp = {}

        """First, go load in all matching TCRS responses"""
        section = request.data["section"]
        team = request.data["teamNumber"]
        course = request.data["course"]

        teamRecord = Team.objects.filter(
            course=course, section=section, team=team
        ).get()

        print("Team record is " + str(teamRecord))

        resp["team"] = teamRecord.toDict()

        iteration = Iteration.objects.filter(
            displayed_value=request.data["iteration"]
        ).get()

        matchingResponses = TcrsResponse.objects.filter(
            team=teamRecord,
            iteration=iteration,
        ).values()

        """Compute a change in sentiment since last week, if the data exists"""

        """Find matching responses from last week to compute a change in sentiment"""
        lastIteration = None
        try:
            lastIteration = Iteration.objects.filter(
                sequential_value=iteration.sequential_value - 1
            ).get()
        except ObjectDoesNotExist:
            pass

        responsesLastIteration = None
        if lastIteration:
            responsesLastIteration = TcrsResponse.objects.filter(
                team__course=course,
                team__section=section,
                team__team=team,
                iteration=lastIteration,
            ).values()

        scoresThisWeek = [x["score"] for x in matchingResponses]
        sentimentThisWeek = sum(scoresThisWeek) / len(scoresThisWeek)

        sentimentChange = dict()

        if responsesLastIteration:
            scoresLastWeek = [x["score"] for x in responsesLastIteration]
            sentimentLastWeek = sum(scoresLastWeek) / len(scoresLastWeek)
            sentimentChange["change"] = sentimentThisWeek - sentimentLastWeek
            sentimentChange["this"] = sentimentThisWeek
            sentimentChange["last"] = sentimentLastWeek
        else:
            sentimentChange["change"] = "No Data"
            sentimentChange["this"] = sentimentThisWeek

        resp["sentimentChange"] = sentimentChange

        """End calculate change in sentiment"""

        """Then, find responses to specific questions"""

        tcrsDetails = dict()

        """MatchingResponses is all individual TCRS submissions....need to go through each one to pull in the associated questions"""
        for matchingResponse in matchingResponses:
            # print("Looking for Question Responses for TCRS #" + str(matchingResponse['id']));

            respForUser = []

            """This pulls in the responses to individual questions"""
            individualResponses = (
                TcrsQuestionResponse.objects.select_related()
                .filter(fullResponse=matchingResponse["id"])
                .all()
            )
            for response in individualResponses:
                """And finally prepare JSON data for the answer to each question"""
                respForUser.append(response.toDict())
            tcrsDetails[matchingResponse["submitter"]] = respForUser

        resp["tcrsDetails"] = tcrsDetails

        sys.stdout.flush()
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def all_sentiment_data(self, request):
        resp = dict()

        runningLookup = TcrsResponse.objects

        course = request.data.get("course")

        if course:
            print("Filtering on course = " + str(course))
            runningLookup = runningLookup.filter(team__course__in=course)

        section = request.data.get("section")
        print(section)
        if section:
            print("Filtering on section = " + str(section))
            runningLookup = runningLookup.filter(team__section__in=section)

        team = request.data.get("team")

        if team:
            print("Filtering on team = " + str(team))
            runningLookup = runningLookup.filter(team__team__in=team)

        matchingResponses = runningLookup.all()

        """Get a list of iterations where we had at least one reply, and then sort them into ascending order so the chart comes out looking ok"""
        iterationsWithResponses = [x.iteration.id for x in matchingResponses]
        uniqueIterationIds = list(dict.fromkeys(iterationsWithResponses))

        uniqueIterations = []
        for iterationId in uniqueIterationIds:
            uniqueIterations.append(Iteration.objects.filter(id=iterationId).get())

        uniqueIterations.sort(key=lambda x: x.sequential_value)

        resp["iterations"] = [x.displayed_value for x in uniqueIterations]

        """Now, fetch sentiment details for each member of the team.  The JSON format we want is:
        {
           "team-1": [array-of-values],
           "team-2": [array-of-values],
           ...
        }
        
        In cases where they forgot to submit an iteration for the week, stick a `None` in the list in the appropriate slot; the charting is configured to skip over missing values and will handle it.
        """

        sentiments = dict()
        teams = [x.team for x in matchingResponses]

        for team in teams:
            responses = []
            for iteration in uniqueIterations:
                full_responses = TcrsResponse.objects.filter(
                    team=team,
                    iteration=iteration,
                ).all()

                if full_responses:
                    resp_scores = [x.score for x in full_responses]
                    team_score = sum(resp_scores) / len(resp_scores)
                    responses.append(team_score)

                else:
                    responses.append(None)
            sentiments[str(team)] = responses

        resp["sentimentDetails"] = sentiments

        sys.stdout.flush()
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def team_sentiment_data(self, request):

        section = request.data["section"]
        team = request.data["teamNumber"]
        course = request.data["course"]

        resp = dict()

        """Get sentiment from each person for each iteration"""

        teamResponsesAllIterations = TcrsResponse.objects.filter(
            team__course=course, team__section=section, team__team=team
        ).values()

        """Get a list of iterations where we had at least one reply, and then sort them into ascending order so the chart comes out looking ok"""
        iterationsWithResponses = [
            x["iteration_id"] for x in teamResponsesAllIterations
        ]
        uniqueIterationIds = list(dict.fromkeys(iterationsWithResponses))

        uniqueIterations = []
        for iterationId in uniqueIterationIds:
            uniqueIterations.append(Iteration.objects.filter(id=iterationId).get())

        uniqueIterations.sort(key=lambda x: x.sequential_value)

        resp["iterations"] = [x.displayed_value for x in uniqueIterations]

        """Now, fetch sentiment details for each member of the team.  The JSON format we want is:
        {
           "member1": [array-of-values],
           "member2": [array-of-values],
           ...
        }
        
        In cases where they forgot to submit an iteration for the week, stick a `None` in the list in the appropriate slot; the charting is configured to skip over missing values and will handle it.
        """

        sentiments = dict()
        membersOfTeam = [x["submitter"] for x in teamResponsesAllIterations]

        for member in membersOfTeam:
            responses = []
            for iteration in uniqueIterations:
                try:
                    response = TcrsResponse.objects.filter(
                        team__course=course,
                        team__section=section,
                        team__team=team,
                        iteration=iteration,
                        submitter=member,
                    ).get()
                    responses.append(response.score)
                except ObjectDoesNotExist:
                    responses.append(None)
            sentiments[member] = responses

        resp["sentimentDetails"] = sentiments

        sys.stdout.flush()
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def iterations(self, request):
        section = request.data["section"]
        team = request.data["teamNumber"]
        course = request.data["course"]

        resp = dict()

        """Get sentiment from each person for each iteration"""

        teamResponsesAllIterations = TcrsResponse.objects.filter(
            team__course=course, team__section=section, team__team=team
        ).values()

        """Get a list of iterations where we had at least one reply, and then sort them into ascending order so the chart comes out looking ok"""
        iterationsWithResponses = [
            x["iteration_id"] for x in teamResponsesAllIterations
        ]
        uniqueIterationIds = list(dict.fromkeys(iterationsWithResponses))

        uniqueIterations = []
        for iterationId in uniqueIterationIds:
            uniqueIterations.append(Iteration.objects.filter(id=iterationId).get())

        uniqueIterations.sort(key=lambda x: x.sequential_value)

        resp["iterations"] = [x.displayed_value for x in uniqueIterations]

        sys.stdout.flush()
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def matching_teams(self, request):

        runningLookup = TcrsResponse.objects

        course = request.data.get("course")

        if course:
            print("Filtering on course = " + str(course))
            runningLookup = runningLookup.filter(team__course__in=course)

        section = request.data.get("section")
        print(section)
        if section:
            print("Filtering on section = " + str(section))
            runningLookup = runningLookup.filter(team__section__in=section)

        team = request.data.get("team")

        if team:
            print("Filtering on team = " + str(team))
            runningLookup = runningLookup.filter(team__team__in=team)

        matchingResponses = runningLookup.all()

        resp = dict()

        resp["course"] = list(set([x.team.course for x in matchingResponses]))

        resp["section"] = list(set([x.team.section for x in matchingResponses]))

        resp["team"] = list(set([x.team.team for x in matchingResponses]))

        sys.stdout.flush()
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def team_summary(self, request):

        resp = dict()

        runningLookup = TcrsResponse.objects

        course = request.data.get("course")

        if course:
            print("Filtering on course = " + str(course))
            runningLookup = runningLookup.filter(team__course__in=course)

        section = request.data.get("section")
        print(section)
        if section:
            print("Filtering on section = " + str(section))
            runningLookup = runningLookup.filter(team__section__in=section)

        team = request.data.get("team")

        if team:
            print("Filtering on team = " + str(team))
            runningLookup = runningLookup.filter(team__team__in=team)

        iteration = request.data.get("iteration")

        it = Iteration.objects.filter(displayed_value=iteration).get()

        lookupWithoutIteration = runningLookup

        runningLookup = runningLookup.filter(iteration=it)

        matchingResponses = runningLookup.all()

        scoresPerTeam = dict()

        # First, calculate how many struggling teams we have -- this is the number of teams where at least one member's response has a score <= 0
        for response in matchingResponses:
            # python is dumb and throws a fit if you try to use either an object or a tuple as a key, so we have to use this hack and then un-hack it (re-hack?) in the JS.
            key = "{}::{}::{}::{}".format(
                response.team.course,
                response.team.section,
                response.team.team,
                response.team.id,
            )

            if key not in scoresPerTeam:
                scoresPerTeam[key] = []

            scoresPerTeam[key].append(response.score)

        teamsWithNeg = dict()

        for team in scoresPerTeam:
            scores = scoresPerTeam[team]
            lowestScore = sorted(scores)[0]
            if lowestScore <= 0:
                teamsWithNeg[team] = lowestScore

        averageScorePerTeam = dict()

        for team in scoresPerTeam:
            scores = scoresPerTeam[team]
            avgScore = sum(scores) / len(scores)
            averageScorePerTeam[team] = avgScore

        resp["strugglingTeams"] = teamsWithNeg

        # If there are responses for a previous week, go calculate teams that have seen the biggest improvement and ones that have seen the biggest drop.
        # Note, that while the flagging ^ above uses individual scores, this uses team-level scores.  This might be worth revisiting in the future

        if it.sequential_value != 0:

            lastIteration = Iteration.objects.filter(
                sequential_value=it.sequential_value - 1
            ).get()

            responsesLastIteration = lookupWithoutIteration.filter(
                iteration=lastIteration
            ).all()

            lastIterationScoresPerTeam = dict()

            for response in responsesLastIteration:
                # python is dumb and throws a fit if you try to use either an object or a tuple as a key, so we have to use this hack and then un-hack it (re-hack?) in the JS.
                key = "{}::{}::{}::{}".format(
                    response.team.course,
                    response.team.section,
                    response.team.team,
                    response.team.id,
                )

                if key not in lastIterationScoresPerTeam:
                    lastIterationScoresPerTeam[key] = []

                lastIterationScoresPerTeam[key].append(response.score)

            lastIterationAverageScorePerTeam = dict()

            for team in lastIterationScoresPerTeam:
                scores = lastIterationScoresPerTeam[team]
                avgScore = sum(scores) / len(scores)
                lastIterationAverageScorePerTeam[team] = avgScore

            scoreChanges = dict()

            # Now, go compute changes vs last week:
            for team in averageScorePerTeam:
                scoreThisWeek = averageScorePerTeam[team]
                scoreLastWeek = lastIterationAverageScorePerTeam.get(team)

                print("    " + str(team))
                print("    Last week score: " + str(scoreLastWeek))
                print("    This week score: " + str(scoreThisWeek))

                diff = None
                if scoreLastWeek:
                    diff = scoreThisWeek - scoreLastWeek

                if diff:
                    scoreChanges[team] = diff

            print("Score changes")
            print(scoreChanges)

            mostImproved = {
                team: scoreChanges[team]
                for team in sorted(scoreChanges)
                if scoreChanges[team] > 3
            }

            mostDrop = {
                team: scoreChanges[team]
                for team in sorted(scoreChanges)
                if scoreChanges[team] < -3
            }

            resp["improvement"] = mostImproved
            resp["drop"] = mostDrop
        # end if

        # Now, prepare a list of all teams

        allTeamDetails = []

        for team in scoresPerTeam:

            scores = sorted(scoresPerTeam[team])

            out = dict()

            out["lowestScore"] = scores[0]
            out["highestScore"] = scores[-1]
            out["avgScore"] = sum(scores) / len(scores)
            out["team"] = team

            allTeamDetails.append(out)

        resp["allTeams"] = allTeamDetails

        print(resp)

        sys.stdout.flush()
        return JsonResponse(resp, safe=False, status=status.HTTP_200_OK)


# end class


def loadTCRS(request):
    return render(request, "loadTCRS.html")


def index(request):
    return render(request, "index.html")


def teamDetails(request):
    return render(request, "viewTeamDetails.html")


def summary(request):
    return render(request, "summary.html")
