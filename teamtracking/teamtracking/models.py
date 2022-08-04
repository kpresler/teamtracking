from django.db import models
from django.contrib.auth.models import User

# Create your models here.

"""The point penalty for negative sentiment in TCRS natural language processing.  Should be enough to force the response negative."""
negative_sentiment_penalty = -100


class Team(models.Model):
    """Represents a team on project for a course"""

    course = models.CharField(max_length=10)
    section = models.CharField(max_length=10)
    team = models.CharField("Name or number of the student's team", max_length=20)

    assigned_TA = models.ForeignKey(
        to=User,
        on_delete=models.PROTECT,
        related_name="assigned_TA",
        null=True,
        blank=True,
    )

    def toDict(self):
        dictionary = dict()
        dictionary["course"] = self.course
        dictionary["section"] = self.section
        dictionary["team"] = self.team
        if self.assigned_TA:
            dictionary["assigned_TA"] = self.assigned_TA.username
        else:
            dictionary["assigned_TA"] = None
        return dictionary

    def __str__(self):
        return "{}-{}-{}".format(self.course, self.section, self.team)


class TcrsQuestion(models.Model):
    """An individual question in the Team Collaboration Reflection Survey.  A question has question text and can be marked as `p`ositive, `n`egative, `t`ext, or `o`ther."""

    text = models.CharField("Question text", max_length=200)
    qType = models.CharField(
        choices=(
            ("p", "Positive"),
            ("n", "Negative"),
            ("t", "Text"),
            ("o", "Other"),
        ),
        max_length=1,
    )

    active = models.BooleanField("Is this question currently active?")

    def __str__(self):
        return self.text


class Iteration(models.Model):

    displayed_value = models.CharField(max_length=5)
    sequential_value = models.IntegerField()

    def __str__(self):
        return (
            "Iteration "
            + self.displayed_value
            + " ("
            + str(self.sequential_value)
            + ")"
        )


class TcrsResponse(models.Model):
    """Response to the TCRS for a specific student and specific week"""

    submit_date = models.DateTimeField("Submission date")

    team = models.ForeignKey(
        to=Team,
        on_delete=models.PROTECT,
        related_name="response",
        null=False,
        blank=False,
    )
    submitter = models.CharField("Who submitted this response?", max_length=50)
    iteration = models.ForeignKey(
        to=Iteration, on_delete=models.PROTECT, null=False, blank=False
    )

    score = models.IntegerField()

    def __str__(self):
        return (
            "Response from "
            + self.submitter
            + " to iteration "
            + str(self.iteration)
            + " on team "
            + str(self.team)
            + " with a score of "
            + str(self.score)
        )


class TcrsQuestionResponse(models.Model):
    """Represents a response to a single question on the TCRS"""

    question = models.ForeignKey(
        to=TcrsQuestion, on_delete=models.PROTECT, null=False, blank=False
    )

    response = models.CharField("Response to question", max_length=1000)

    fullResponse = models.ForeignKey(
        to=TcrsResponse,
        on_delete=models.PROTECT,
        related_name="responses",
        null=True,
        blank=True,
    )

    def __str__(self):
        return str(self.question) + "::" + self.response

    def toDict(self):

        dictionary = {}
        dictionary["question"] = self.question.text
        dictionary["response"] = self.response

        return dictionary


class Note(models.Model):
    """Represents an observation/note about a team's performance, or a followup requested"""

    note_text = models.CharField(max_length=1000)
    submit_date = models.DateTimeField("Note date")

    submitter = models.ForeignKey(
        to=User,
        on_delete=models.PROTECT,
        related_name="submitter",
        null=False,
        blank=False,
    )

    team = models.ForeignKey(
        to=Team,
        on_delete=models.PROTECT,
        related_name="note",
        null=False,
        blank=False,
    )

    def toDict(self):
        dictionary = dict()

        dictionary["note_text"] = self.note_text
        dictionary["submit_date"] = self.submit_date
        dictionary["submitter"] = self.submitter.username

        team = dict()
        team["course"] = self.team.course
        team["section"] = self.team.section
        team["team"] = self.team.team

        dictionary["team"] = team

        return dictionary
