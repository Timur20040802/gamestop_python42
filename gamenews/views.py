from annotated_types import T
from django.conf.locale import el
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.sites import requests
from django.db.migrations import questioner
from django.db.models import F, Q, Case, CharField, Count, Max, Value, When
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from gamenews.forms import AddPostForm, CommentForm
from gamenews.models import Category, Comment, Post
from dotenv import load_dotenv
import os 



load_dotenv()
import requests
import json
VSEGPT_KEY= os.getenv('VSEGPT_KEY')
def check_comment_with_AI(text):
    question = f'''Ты - это ИИ-модератор сайта для комменатриев.
    Контекст: комментарий должен быть без оскорблений, без мата, не упоминать политику, и не содержать призывов к насилию.
    Оцени этот комментарий:{text}.
    Ответь: true если комментаорий прошел эту проверку и false если не прошёл эту проверку.'''


        


# Выполнение POST запроса
    response = requests.post(
        "https://api.vsegpt.ru/v1/chat/completions",
        headers={
        "Authorization": f"Bearer {VSEGPT_KEY}",
        "Content-Type": "application/json",
        "X-Title": "File analysis demo" # опционально - передача информация об источнике API-вызова
        },
        json={
        "model": "openai/gpt-5-nano",
        "messages": [ {"role": "user", "content": question}]
        }
)


# Обработка ответа
    response_data = response.json()
    msg = response_data["choices"][0]["message"]["content"]

    print("Ответ:", msg)


    if msg.lower() == 'true':
        return True
    elif msg.lower() == 'false':
        return False
    else:
        print('что то пошло не так!')


class IndexPage(ListView):
    model = Post
    template_name = "gamenews/index.html"
    context_object_name = "posts"
    paginate_by = 3

    def get_queryset(self):
        if self.request.GET:
            if "search" in self.request.GET:
                query = self.request.GET["search"]
                return Post.objects.filter(
                    Q(title__icontains=query) | Q(full_description__icontains=query)
                )
        return Post.objects.annotate(rat=Case(
            When(views__gt=100, then=Value('Высокий')),
            When(views__gt=50, then=Value('Средний')),
            When(views__gt=10, then=Value('Низкий')),
            default=Value('Начальный'),
            output_field=CharField()
        ))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Главная страница"
        context["count"] = self.get_queryset().count()
        context["anno"] = Category.objects.annotate(total=Count("posts_by_cat"))
        if self.request.GET:
            if "search" in self.request.GET:
                context["search"] = self.request.GET["search"]
        return context


class DetailPost(LoginRequiredMixin, DetailView):
    model = Post
    template_name = "gamenews/post_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.get_object()
        context["comments"] = post.comments_by_post.filter(verify=True)
        context["title"] = post.title
        context["rel_posts"] = (
            Post.objects.select_related("category")
            .prefetch_related("tag")
            .filter(category=post.category)
            .order_by("?")[:3]
        )
        context["best_cats"] = Category.objects.annotate(
            total=Count("posts_by_cat")
        ).order_by("-total")[:5]
        context['last_post'] = Post.objects.order_by('-published_date')[:3]

        return context

    def get(self, request, *args, **kwargs):        
        form = CommentForm()
        self.object = self.get_object()
        Post.objects.filter(pk=self.object.pk).update(views=F("views") + 1)
        self.object.refresh_from_db()
        my_context = self.get_context_data(object=self.object)
        my_context["form"] = form
        

        return self.render_to_response(context=my_context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = CommentForm(request.POST)

        if form.is_valid():
            check_ai =""
            author = request.user
            if author.username == "admin":
                verify = True
            else:
                verify = check_comment_with_AI(form.cleaned_data["text"])
                check_ai = " проерено ии"


            Comment.objects.create(
                post=self.object,
                author=author,
                text=form.cleaned_data["text"] + check_ai,
                verify=verify,
            )
            return redirect(self.object.get_absolute_url())
        context = self.get_context_data(form=form)
        return self.render_to_response(context=context)


class AddPostView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    form_class = AddPostForm
    template_name = "gamenews/form_add.html"

    def form_valid(self, form):
        new_post = form.save(commit=False)
        new_post.author = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Создание поста"
        return context


class UpdatePostView(UpdateView):
    model = Post
    fields = ["title", "shot_description", "full_description"]
    template_name = "gamenews/form_add.html"
    success_url = reverse_lazy("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Изменение поста"
        return context


class About(TemplateView):
    template_name = "gamenews/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "О нас"
        return context


class CategoryView(ListView):
    model = Category
    template_name = "gamenews/category_all.html"
    context_object_name = "categories"

    def get_queryset(self):
        return Category.objects.annotate(post_count=Count("posts_by_cat"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Все категории"
        return context


class CategoryDetailView(ListView):
    model = Post
    template_name = "gamenews/category.html"
    context_object_name = "post_cats"

    def get_queryset(self):
        query_set = super().get_queryset()
        cat = Category.objects.get(slug=self.kwargs["slug"])
        return query_set.filter(category__pk=cat.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cat"] = Category.objects.get(slug=self.kwargs["slug"])
        context["title"] = context["cat"]
        return context
