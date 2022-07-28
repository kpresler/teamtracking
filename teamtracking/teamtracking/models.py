from django.db import models
from django.contrib.auth.models import User

# Create your models here.


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

    course = models.CharField(max_length=10)
    section = models.CharField(max_length=10)
    team = models.CharField("Name or number of the student's team", max_length=20)
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
            + self.section
            + "-"
            + self.team
            + " in "
            + self.course
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

    def responseToDictionary(self):

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

    course = models.CharField(max_length=10)
    section = models.CharField(max_length=10)
    team = models.CharField("Name or number of the student's team", max_length=20)

    def noteToDictionary(self):
        dictionary = dict()

        dictionary["note_text"] = self.note_text
        dictionary["submit_date"] = self.submit_date
        dictionary["submitter"] = self.submitter.username
        dictionary["course"] = self.course
        dictionary["section"] = self.section
        dictionary["team"] = self.team

        return dictionary

    # TODO: At some point, extract the (course, section, team) into a Team object & reference that from this and the TcrsResponse.
