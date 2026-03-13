from unittest.mock import MagicMock

import pytest
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from coderag.core.models import Node, NodeKind
from coderag.plugins.python.extractor import PythonExtractor
from coderag.plugins.python.frameworks.django import DjangoDetector


@pytest.fixture
def django_detector():
    return DjangoDetector()


@pytest.fixture
def python_extractor():
    return PythonExtractor()


@pytest.fixture
def python_parser():
    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)
    return parser


def test_django_detect_framework_manage_py(django_detector, tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("django==4.2.0")
    manage = tmp_path / "manage.py"
    manage.write_text("import os\nimport sys\n")
    assert django_detector.detect_framework(str(tmp_path)) is True


def test_django_detect_framework_settings_py(django_detector, tmp_path):
    req = tmp_path / "pyproject.toml"
    req.write_text("[tool.poetry.dependencies]\ndjango = '^4.2'")
    settings = tmp_path / "settings.py"
    settings.write_text("INSTALLED_APPS = ['django.contrib.admin']")
    assert django_detector.detect_framework(str(tmp_path)) is True


def test_django_detect_framework_wsgi_py(django_detector, tmp_path):
    req = tmp_path / "Pipfile"
    req.write_text("[packages]\ndjango = '*'")
    wsgi = tmp_path / "wsgi.py"
    wsgi.write_text("os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')")
    assert django_detector.detect_framework(str(tmp_path)) is True


def test_django_detect_framework_asgi_py(django_detector, tmp_path):
    req = tmp_path / "setup.py"
    req.write_text("install_requires=['django']")
    asgi = tmp_path / "asgi.py"
    asgi.write_text("os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')")
    assert django_detector.detect_framework(str(tmp_path)) is True


def test_django_detect_framework_no_django(django_detector, tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask==2.0.0")
    assert django_detector.detect_framework(str(tmp_path)) is False


def test_django_detect_models(django_detector, python_extractor, python_parser):
    source = b"""
from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=100)

class Book(models.Model):
    title = models.CharField(max_length=100)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    published = models.BooleanField(default=True)
"""
    result = python_extractor.extract("models.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("models.py", tree, source, nodes, edges)

    model_patterns = [p for p in patterns if p.pattern_type == "model"]
    assert len(model_patterns) == 2

    book_pattern = next(p for p in model_patterns if p.metadata.get("model_name") == "Book")

    field_nodes = [n for n in book_pattern.nodes if n.kind == NodeKind.PROPERTY]
    assert len(field_nodes) == 3

    author_field = next(n for n in field_nodes if n.name == "author")
    assert author_field.metadata["field_type"] == "ForeignKey"
    assert author_field.metadata["related_model"] == "Author"


def test_django_detect_fbv(django_detector, python_extractor, python_parser):
    source = b"""
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view

@api_view(["GET", "POST"])
def my_view(request, pk):
    return HttpResponse("Hello")

def simple_view(request):
    return render(request, 'index.html')
"""
    result = python_extractor.extract("views.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("views.py", tree, source, nodes, edges)

    controller_patterns = [p for p in patterns if p.pattern_type == "controller"]
    assert len(controller_patterns) >= 1

    my_view = next((p for p in controller_patterns if p.metadata.get("controller_name") == "my_view"), None)
    if my_view:
        assert my_view.metadata["view_type"] == "fbv"


def test_django_detect_cbv(django_detector, python_extractor, python_parser):
    source = b"""
from django.views.generic import ListView, DetailView
from .models import Book

class BookListView(ListView):
    model = Book
    template_name = 'book_list.html'

class BookDetailView(DetailView):
    model = Book
"""
    result = python_extractor.extract("views.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("views.py", tree, source, nodes, edges)

    controller_patterns = [p for p in patterns if p.pattern_type == "controller"]
    assert len(controller_patterns) == 2


def test_django_detect_urls(django_detector, python_extractor, python_parser):
    source = b"""
from django.urls import path, include
from . import views

urlpatterns = [
    path('books/', views.BookListView.as_view(), name='book-list'),
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book-detail'),
    path('authors/', views.author_list, name='author-list'),
    path('api/', include('api.urls')),
]
"""
    result = python_extractor.extract("urls.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("urls.py", tree, source, nodes, edges)

    route_patterns = [p for p in patterns if p.pattern_type == "routes"]
    assert len(route_patterns) == 1
    assert route_patterns[0].metadata["route_count"] == 4


def test_django_detect_admin(django_detector, python_extractor, python_parser):
    source = b"""
from django.contrib import admin
from .models import Book

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author')

class AuthorAdmin(admin.ModelAdmin):
    pass
admin.site.register(Author, AuthorAdmin)
"""
    result = python_extractor.extract("admin.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("admin.py", tree, source, nodes, edges)

    admin_patterns = [p for p in patterns if p.pattern_type == "admin"]
    assert len(admin_patterns) == 2


def test_django_detect_serializers(django_detector, python_extractor, python_parser):
    source = b"""
from rest_framework import serializers
from .models import Book

class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = '__all__'

class CustomSerializer(serializers.Serializer):
    name = serializers.CharField()
"""
    result = python_extractor.extract("serializers.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("serializers.py", tree, source, nodes, edges)

    serializer_patterns = [p for p in patterns if p.pattern_type == "serializer"]
    assert len(serializer_patterns) == 2


def test_django_detect_commands(django_detector, python_extractor, python_parser):
    source = b"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'My custom command'

    def handle(self, *args, **options):
        pass
"""
    result = python_extractor.extract("management/commands/mycmd.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("management/commands/mycmd.py", tree, source, nodes, edges)

    command_patterns = [p for p in patterns if p.pattern_type == "management_command"]
    assert len(command_patterns) == 1


def test_django_detect_signals(django_detector, python_extractor, python_parser):
    source = b"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    pass
"""
    result = python_extractor.extract("signals.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("signals.py", tree, source, nodes, edges)

    signal_patterns = [p for p in patterns if p.pattern_type == "signal"]
    assert len(signal_patterns) == 1


def test_django_detect_middleware(django_detector, python_extractor, python_parser):
    source = b"""
class SimpleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
"""
    result = python_extractor.extract("middleware.py", source)
    nodes, edges = result.nodes, result.edges
    tree = python_parser.parse(source)
    patterns = django_detector.detect("middleware.py", tree, source, nodes, edges)

    middleware_patterns = [p for p in patterns if p.pattern_type == "middleware"]
    assert len(middleware_patterns) == 1


def test_django_global_patterns(django_detector, tmp_path):
    # Create a fake django project structure
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    manage_py = tmp_path / "manage.py"
    manage_py.write_text("# manage.py")

    settings_py = app_dir / "settings.py"
    settings_py.write_text(
        "MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'myapp.middleware.SimpleMiddleware']"
    )

    urls_py = app_dir / "urls.py"
    urls_py.write_text("urlpatterns = [path('api/', include('api.urls'))]")

    api_dir = app_dir / "api"
    api_dir.mkdir()
    api_urls_py = api_dir / "urls.py"
    api_urls_py.write_text("urlpatterns = [path('users/', views.user_list)]")

    store = MagicMock()

    file_node = Node(
        id="file1",
        file_path=str(manage_py),
        start_line=1,
        end_line=1,
        kind=NodeKind.FILE,
        name="manage.py",
        qualified_name="manage.py",
        language="python",
    )

    def find_nodes_impl(kind=None, name_pattern=None, limit=10, **kwargs):
        if kind == NodeKind.FILE:
            return [file_node]
        if name_pattern == "user_list":
            return [
                Node(
                    id="view1",
                    kind=NodeKind.FUNCTION,
                    name="user_list",
                    qualified_name="user_list",
                    file_path="views.py",
                    start_line=1,
                    end_line=1,
                    language="python",
                )
            ]
        return []

    store.find_nodes.side_effect = find_nodes_impl

    patterns = django_detector.detect_global_patterns(store)
    assert len(patterns) >= 2
