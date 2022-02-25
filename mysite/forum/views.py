from django.shortcuts import render, redirect
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.db.models.functions import Greatest, Coalesce
from django.views.generic.list import ListView
from django.views.generic.base import TemplateView

from .models import Topic, Message, Comment
from .forms import MessageForm, CommentForm, MessageSearchForm


class IndexView(ListView):
    template_name = "forum/index.html"
    model = Topic

    def get_queryset(self, **kwargs):
        queryset = (
            Topic.objects.all()
            .annotate(
                letest_message_date=Max("topic_message__created_at"),
                letest_comment_date=Max("topic_message__comment__created_at"),
                latest_date=Greatest("letest_message_date", "letest_comment_date"),
                time=Coalesce(
                    "latest_date", "letest_message_date", "letest_comment_date"
                ),
            )
            .order_by("-time")
        )
        return queryset


class ForumView(ListView):
    template_name = "forum/forum.html"
    paginate_by = 5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        topic = Topic.objects.get(name=self.kwargs["topic"])
        context["topic"] = topic

        context["message_form"] = MessageForm()
        context["comment_form"] = CommentForm()

        form = MessageSearchForm(self.request.GET)
        if form.is_valid():
            context["keyword"] = form.cleaned_data["keyword"]

        context["search_form"] = form

        if self.request.GET.get("tag"):
            context["tag"] = self.request.GET.get("tag")

        return context

    def get_queryset(self, **kwargs):
        subquery = Comment.objects.filter(message=OuterRef("id")).order_by(
            "-created_at"
        )
        queryset = (
            Message.objects.filter(topic__name=self.kwargs["topic"])
            .annotate(
                reply_num=Count("comment"),
                latest_reply_date=Subquery(subquery.values("created_at")[:1]),
                # latest_reply_date=Max('comment__created_at'),
            )
            .prefetch_related("tag", "comment")
            .order_by("created_at")
        )
        if "tag" in self.request.GET:
            queryset = queryset.filter(tag__name=self.request.GET["tag"])

        form = MessageSearchForm(self.request.GET)
        if form.is_valid():
            keyword = form.cleaned_data["keyword"]
            if keyword:
                queryset = queryset.filter(content__icontains=keyword)

        return queryset

    def post(self, request, *args, **kwargs):

        if self.request.user.is_anonymous:
            return redirect("forum:forum", topic=self.kwargs["topic"])

        if "message" in request.POST:

            message_form = MessageForm(request.POST, request.FILES)

            topic = Topic.objects.get(name=self.kwargs["topic"])

            if message_form.is_valid():
                message_form.instance.topic = topic
                message_form.instance.user = self.request.user
                message = message_form.save()
                for tag in message_form.cleaned_data["tag"]:
                    message.tag.add(tag)

        elif "comment" in request.POST:

            comment_form = CommentForm(request.POST)

            if comment_form.is_valid():

                message_id = request.POST["comment"]
                message = Message.objects.get(id=message_id)

                comment_form.instance.message = message
                comment_form.instance.user = self.request.user
                comment = comment_form.save()

        return redirect("forum:forum", topic=self.kwargs["topic"])

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
