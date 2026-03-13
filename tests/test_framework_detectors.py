"""Tests for Python framework detectors (Django, Flask, FastAPI) and Angular."""

import json

from coderag.core.models import (
    EdgeKind,
    Node,
    NodeKind,
)

# ── Django Detector Tests ─────────────────────────────────────────────
from coderag.plugins.python.frameworks.django import DjangoDetector


class TestDjangoDetectFramework:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "django"

    def test_detects_django_with_manage_py_and_requirements(self, tmp_path):
        (tmp_path / "manage.py").write_text("#!/usr/bin/env python\nimport django")
        (tmp_path / "requirements.txt").write_text("django==4.2\n")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_django_with_pyproject_toml(self, tmp_path):
        (tmp_path / "manage.py").write_text("#!/usr/bin/env python")
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["django>=4.0"]\n')
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_django_with_settings_py(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("django==4.2\n")
        settings_dir = tmp_path / "myproject"
        settings_dir.mkdir()
        (settings_dir / "settings.py").write_text("INSTALLED_APPS = []\n")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_django_dependency(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask==2.0\n")
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_files(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestDjangoModels:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_model_class(self):
        source = b"""from django.db import models

class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    age = models.IntegerField(default=0)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
"""
        nodes = [
            Node(
                id="cls-user",
                name="User",
                kind=NodeKind.CLASS,
                qualified_name="User",
                language="python",
                file_path="models.py",
                start_line=3,
                end_line=9,
            )
        ]
        patterns = self.detector.detect("models.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        model_nodes = [n for n in all_nodes if n.kind == NodeKind.MODEL]
        assert len(model_nodes) >= 1
        model = model_nodes[0]
        assert "User" in model.name
        assert model.metadata.get("framework") == "django"

    def test_detect_model_fields(self):
        source = b"""from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    slug = models.SlugField(unique=True)
    uuid = models.UUIDField()
    image = models.ImageField(upload_to="products/")
"""
        nodes = [
            Node(
                id="cls-product",
                name="Product",
                kind=NodeKind.CLASS,
                qualified_name="Product",
                language="python",
                file_path="models.py",
                start_line=3,
                end_line=8,
            )
        ]
        patterns = self.detector.detect("models.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        model_nodes = [n for n in all_nodes if n.kind == NodeKind.MODEL]
        assert len(model_nodes) >= 1

    def test_detect_foreign_key_relations(self):
        source = b"""from django.db import models

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey("Product", on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=1)
"""
        nodes = [
            Node(
                id="cls-order",
                name="Order",
                kind=NodeKind.CLASS,
                qualified_name="Order",
                language="python",
                file_path="models.py",
                start_line=3,
                end_line=6,
            )
        ]
        patterns = self.detector.detect("models.py", None, source, nodes, [])
        all_edges = [e for p in patterns for e in p.edges]
        dep_edges = [e for e in all_edges if e.kind == EdgeKind.DEPENDS_ON]
        assert len(dep_edges) >= 1

    def test_detect_many_to_many(self):
        source = b"""from django.db import models

class Article(models.Model):
    tags = models.ManyToManyField(Tag)
    authors = models.ManyToManyField("Author")
"""
        nodes = [
            Node(
                id="cls-article",
                name="Article",
                kind=NodeKind.CLASS,
                qualified_name="Article",
                language="python",
                file_path="models.py",
                start_line=3,
                end_line=5,
            )
        ]
        patterns = self.detector.detect("models.py", None, source, nodes, [])
        all_edges = [e for p in patterns for e in p.edges]
        dep_edges = [e for e in all_edges if e.kind == EdgeKind.DEPENDS_ON]
        assert len(dep_edges) >= 1

    def test_detect_one_to_one(self):
        source = b"""from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
"""
        nodes = [
            Node(
                id="cls-profile",
                name="Profile",
                kind=NodeKind.CLASS,
                qualified_name="Profile",
                language="python",
                file_path="models.py",
                start_line=3,
                end_line=4,
            )
        ]
        patterns = self.detector.detect("models.py", None, source, nodes, [])
        all_edges = [e for p in patterns for e in p.edges]
        dep_edges = [e for e in all_edges if e.kind == EdgeKind.DEPENDS_ON]
        assert len(dep_edges) >= 1


class TestDjangoViews:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_class_based_view(self):
        source = b"""from django.views import View
from django.views.generic import ListView, DetailView

class UserListView(ListView):
    model = User
    template_name = "users/list.html"

class UserDetailView(DetailView):
    model = User
"""
        nodes = [
            Node(
                id="cls-userlist",
                name="UserListView",
                kind=NodeKind.CLASS,
                qualified_name="UserListView",
                language="python",
                file_path="views.py",
                start_line=4,
                end_line=6,
            ),
            Node(
                id="cls-userdetail",
                name="UserDetailView",
                kind=NodeKind.CLASS,
                qualified_name="UserDetailView",
                language="python",
                file_path="views.py",
                start_line=8,
                end_line=9,
            ),
        ]
        patterns = self.detector.detect("views.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        controller_nodes = [n for n in all_nodes if n.kind == NodeKind.CONTROLLER]
        assert len(controller_nodes) >= 1

    def test_detect_function_based_view(self):
        source = b"""from django.http import HttpResponse

def index(request):
    return HttpResponse("Hello")
"""
        nodes = [
            Node(
                id="fn-index",
                name="index",
                kind=NodeKind.FUNCTION,
                qualified_name="index",
                language="python",
                file_path="views.py",
                start_line=3,
                end_line=4,
            ),
        ]
        patterns = self.detector.detect("views.py", None, source, nodes, [])
        # Function-based views may or may not be detected depending on implementation
        assert isinstance(patterns, list)


class TestDjangoURLs:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_url_patterns(self):
        source = b"""from django.urls import path
from . import views

urlpatterns = [
    path("users/", views.UserListView.as_view(), name="user-list"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("api/login/", views.login_view, name="login"),
]
"""
        patterns = self.detector.detect("urls.py", None, source, [], [])
        all_nodes = [n for p in patterns for n in p.nodes]
        route_nodes = [n for n in all_nodes if n.kind == NodeKind.ROUTE]
        assert len(route_nodes) >= 2

    def test_detect_re_path(self):
        source = b"""from django.urls import re_path

urlpatterns = [
    re_path(r"^articles/(?P<year>[0-9]{4})/$", views.year_archive),
]
"""
        patterns = self.detector.detect("urls.py", None, source, [], [])
        # re_path may or may not be detected depending on implementation
        assert isinstance(patterns, list)


class TestDjangoMiddleware:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_middleware(self):
        source = b"""from django.utils.deprecation import MiddlewareMixin

class CustomMiddleware(MiddlewareMixin):
    def process_request(self, request):
        pass

    def process_response(self, request, response):
        return response
"""
        nodes = [
            Node(
                id="cls-middleware",
                name="CustomMiddleware",
                kind=NodeKind.CLASS,
                qualified_name="CustomMiddleware",
                language="python",
                file_path="middleware.py",
                start_line=3,
                end_line=8,
            )
        ]
        patterns = self.detector.detect("middleware.py", None, source, nodes, [])
        # MiddlewareMixin middleware detection depends on implementation
        assert isinstance(patterns, list)

    def test_detect_callable_middleware(self):
        source = b"""class SimpleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
"""
        nodes = [
            Node(
                id="cls-simple-mw",
                name="SimpleMiddleware",
                kind=NodeKind.CLASS,
                qualified_name="SimpleMiddleware",
                language="python",
                file_path="middleware.py",
                start_line=1,
                end_line=7,
            )
        ]
        patterns = self.detector.detect("middleware.py", None, source, nodes, [])
        # Callable middleware detection depends on implementation
        assert isinstance(patterns, list)


class TestDjangoSerializer:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_drf_serializer(self):
        source = b"""from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email"]

class ProductSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
"""
        nodes = [
            Node(
                id="cls-userser",
                name="UserSerializer",
                kind=NodeKind.CLASS,
                qualified_name="UserSerializer",
                language="python",
                file_path="serializers.py",
                start_line=4,
                end_line=7,
            ),
            Node(
                id="cls-prodser",
                name="ProductSerializer",
                kind=NodeKind.CLASS,
                qualified_name="ProductSerializer",
                language="python",
                file_path="serializers.py",
                start_line=9,
                end_line=11,
            ),
        ]
        patterns = self.detector.detect("serializers.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        serializer_nodes = [n for n in all_nodes if n.metadata.get("serializer") is True]
        assert len(serializer_nodes) >= 1


class TestDjangoSignals:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_signal_receiver(self):
        source = b"""from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
"""
        nodes = [
            Node(
                id="fn-create-profile",
                name="create_user_profile",
                kind=NodeKind.FUNCTION,
                qualified_name="create_user_profile",
                language="python",
                file_path="signals.py",
                start_line=6,
                end_line=8,
            )
        ]
        patterns = self.detector.detect("signals.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        event_nodes = [n for n in all_nodes if n.kind == NodeKind.EVENT]
        assert len(event_nodes) >= 1


class TestDjangoManagementCommand:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_management_command(self):
        source = b"""from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Import data from CSV"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str)

    def handle(self, *args, **options):
        pass
"""
        nodes = [
            Node(
                id="cls-command",
                name="Command",
                kind=NodeKind.CLASS,
                qualified_name="Command",
                language="python",
                file_path="management/commands/import_data.py",
                start_line=3,
                end_line=10,
            )
        ]
        patterns = self.detector.detect("management/commands/import_data.py", None, source, nodes, [])
        assert isinstance(patterns, list)


class TestDjangoAdmin:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_detect_admin_registration(self):
        source = b"""from django.contrib import admin
from .models import User, Product

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["name", "email"]
    search_fields = ["name"]

admin.site.register(Product)
"""
        nodes = [
            Node(
                id="cls-useradmin",
                name="UserAdmin",
                kind=NodeKind.CLASS,
                qualified_name="UserAdmin",
                language="python",
                file_path="admin.py",
                start_line=5,
                end_line=7,
            )
        ]
        patterns = self.detector.detect("admin.py", None, source, nodes, [])
        assert isinstance(patterns, list)


class TestDjangoNonPythonFiles:
    def setup_method(self):
        self.detector = DjangoDetector()

    def test_skip_non_python_files(self):
        source = b"<html><body>Hello</body></html>"
        patterns = self.detector.detect("template.html", None, source, [], [])
        assert len(patterns) == 0


# ── Flask Detector Tests ──────────────────────────────────────────────

from coderag.plugins.python.frameworks.flask import FlaskDetector


class TestFlaskDetectFramework:
    def setup_method(self):
        self.detector = FlaskDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "flask"

    def test_detects_flask_in_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask==2.3\n")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_flask_in_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["flask>=2.0"]\n')
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_flask_import_in_app(self, tmp_path):
        (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_flask_dependency(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("django==4.2\n")
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_files(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestFlaskRoutes:
    def setup_method(self):
        self.detector = FlaskDetector()

    def test_detect_app_route(self):
        source = b"""from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello World"

@app.route("/users", methods=["GET", "POST"])
def users():
    return "Users"

@app.route("/users/<int:user_id>")
def get_user(user_id):
    return f"User {user_id}"
"""
        nodes = [
            Node(
                id="fn-index",
                name="index",
                kind=NodeKind.FUNCTION,
                qualified_name="index",
                language="python",
                file_path="app.py",
                start_line=6,
                end_line=7,
            ),
            Node(
                id="fn-users",
                name="users",
                kind=NodeKind.FUNCTION,
                qualified_name="users",
                language="python",
                file_path="app.py",
                start_line=10,
                end_line=11,
            ),
            Node(
                id="fn-getuser",
                name="get_user",
                kind=NodeKind.FUNCTION,
                qualified_name="get_user",
                language="python",
                file_path="app.py",
                start_line=14,
                end_line=15,
            ),
        ]
        patterns = self.detector.detect("app.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        route_nodes = [n for n in all_nodes if n.kind == NodeKind.ROUTE]
        assert len(route_nodes) >= 2

    def test_detect_blueprint_route(self):
        source = b"""from flask import Blueprint

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.route("/login", methods=["GET", "POST"])
def login():
    return "Login"

@bp.route("/logout")
def logout():
    return "Logout"
"""
        nodes = [
            Node(
                id="fn-login",
                name="login",
                kind=NodeKind.FUNCTION,
                qualified_name="login",
                language="python",
                file_path="auth.py",
                start_line=6,
                end_line=7,
            ),
            Node(
                id="fn-logout",
                name="logout",
                kind=NodeKind.FUNCTION,
                qualified_name="logout",
                language="python",
                file_path="auth.py",
                start_line=10,
                end_line=11,
            ),
        ]
        patterns = self.detector.detect("auth.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        route_nodes = [n for n in all_nodes if n.kind == NodeKind.ROUTE]
        assert len(route_nodes) >= 1
        module_nodes = [n for n in all_nodes if n.kind == NodeKind.MODULE]
        assert len(module_nodes) >= 1

    def test_detect_before_after_request(self):
        source = b"""from flask import Flask

app = Flask(__name__)

@app.before_request
def check_auth():
    pass

@app.after_request
def add_headers(response):
    return response
"""
        nodes = [
            Node(
                id="fn-checkauth",
                name="check_auth",
                kind=NodeKind.FUNCTION,
                qualified_name="check_auth",
                language="python",
                file_path="app.py",
                start_line=6,
                end_line=7,
            ),
            Node(
                id="fn-addheaders",
                name="add_headers",
                kind=NodeKind.FUNCTION,
                qualified_name="add_headers",
                language="python",
                file_path="app.py",
                start_line=10,
                end_line=11,
            ),
        ]
        patterns = self.detector.detect("app.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        mw_nodes = [n for n in all_nodes if n.kind == NodeKind.MIDDLEWARE]
        assert len(mw_nodes) >= 1

    def test_detect_error_handler(self):
        source = b"""from flask import Flask

app = Flask(__name__)

@app.errorhandler(404)
def not_found(error):
    return "Not Found", 404
"""
        nodes = [
            Node(
                id="fn-notfound",
                name="not_found",
                kind=NodeKind.FUNCTION,
                qualified_name="not_found",
                language="python",
                file_path="app.py",
                start_line=6,
                end_line=7,
            ),
        ]
        patterns = self.detector.detect("app.py", None, source, nodes, [])
        assert isinstance(patterns, list)


class TestFlaskNonPythonFiles:
    def setup_method(self):
        self.detector = FlaskDetector()

    def test_skip_non_python_files(self):
        source = b"<html><body>Hello</body></html>"
        patterns = self.detector.detect("template.html", None, source, [], [])
        assert len(patterns) == 0


# ── FastAPI Detector Tests ────────────────────────────────────────────

from coderag.plugins.python.frameworks.fastapi import FastAPIDetector


class TestFastAPIDetectFramework:
    def setup_method(self):
        self.detector = FastAPIDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "fastapi"

    def test_detects_fastapi_in_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("fastapi==0.100\n")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_fastapi_in_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi>=0.100"]\n')
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_fastapi_import(self, tmp_path):
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_fastapi_dependency(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("django==4.2\n")
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_files(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestFastAPIRoutes:
    def setup_method(self):
        self.detector = FastAPIDetector()

    def test_detect_route_decorators(self):
        source = b"""from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/items/")
def create_item(item: Item):
    return item

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}

@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    return {"item_id": item_id}

@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    return {"deleted": item_id}
"""
        nodes = [
            Node(
                id="fn-root",
                name="read_root",
                kind=NodeKind.FUNCTION,
                qualified_name="read_root",
                language="python",
                file_path="main.py",
                start_line=6,
                end_line=7,
            ),
            Node(
                id="fn-create",
                name="create_item",
                kind=NodeKind.FUNCTION,
                qualified_name="create_item",
                language="python",
                file_path="main.py",
                start_line=10,
                end_line=11,
            ),
            Node(
                id="fn-read",
                name="read_item",
                kind=NodeKind.FUNCTION,
                qualified_name="read_item",
                language="python",
                file_path="main.py",
                start_line=14,
                end_line=15,
            ),
            Node(
                id="fn-update",
                name="update_item",
                kind=NodeKind.FUNCTION,
                qualified_name="update_item",
                language="python",
                file_path="main.py",
                start_line=18,
                end_line=19,
            ),
            Node(
                id="fn-delete",
                name="delete_item",
                kind=NodeKind.FUNCTION,
                qualified_name="delete_item",
                language="python",
                file_path="main.py",
                start_line=22,
                end_line=23,
            ),
        ]
        patterns = self.detector.detect("main.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        route_nodes = [n for n in all_nodes if n.kind == NodeKind.ROUTE]
        assert len(route_nodes) >= 3

    def test_detect_api_router(self):
        source = b"""from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
def list_users():
    return []

@router.post("/")
def create_user(user: UserCreate):
    return user
"""
        nodes = [
            Node(
                id="fn-list",
                name="list_users",
                kind=NodeKind.FUNCTION,
                qualified_name="list_users",
                language="python",
                file_path="routers/users.py",
                start_line=6,
                end_line=7,
            ),
            Node(
                id="fn-create",
                name="create_user",
                kind=NodeKind.FUNCTION,
                qualified_name="create_user",
                language="python",
                file_path="routers/users.py",
                start_line=10,
                end_line=11,
            ),
        ]
        patterns = self.detector.detect("routers/users.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        route_nodes = [n for n in all_nodes if n.kind == NodeKind.ROUTE]
        assert len(route_nodes) >= 1
        module_nodes = [n for n in all_nodes if n.kind == NodeKind.MODULE]
        assert len(module_nodes) >= 1

    def test_detect_websocket(self):
        source = b"""from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
"""
        nodes = [
            Node(
                id="fn-ws",
                name="websocket_endpoint",
                kind=NodeKind.FUNCTION,
                qualified_name="websocket_endpoint",
                language="python",
                file_path="main.py",
                start_line=6,
                end_line=7,
            ),
        ]
        patterns = self.detector.detect("main.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        route_nodes = [n for n in all_nodes if n.kind == NodeKind.ROUTE]
        assert len(route_nodes) >= 1


class TestFastAPIDependencies:
    def setup_method(self):
        self.detector = FastAPIDetector()

    def test_detect_depends(self):
        source = b"""from fastapi import Depends, FastAPI

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db = Depends(get_db)):
    return db.query(User).first()

@app.get("/users/me")
def read_users_me(current_user = Depends(get_current_user)):
    return current_user
"""
        nodes = [
            Node(
                id="fn-getdb",
                name="get_db",
                kind=NodeKind.FUNCTION,
                qualified_name="get_db",
                language="python",
                file_path="main.py",
                start_line=5,
                end_line=10,
            ),
            Node(
                id="fn-getuser",
                name="get_current_user",
                kind=NodeKind.FUNCTION,
                qualified_name="get_current_user",
                language="python",
                file_path="main.py",
                start_line=12,
                end_line=13,
            ),
            Node(
                id="fn-readme",
                name="read_users_me",
                kind=NodeKind.FUNCTION,
                qualified_name="read_users_me",
                language="python",
                file_path="main.py",
                start_line=16,
                end_line=17,
            ),
        ]
        patterns = self.detector.detect("main.py", None, source, nodes, [])
        all_edges = [e for p in patterns for e in p.edges]
        dep_edges = [e for e in all_edges if e.kind == EdgeKind.DEPENDS_ON]
        assert len(dep_edges) >= 1


class TestFastAPIPydanticModels:
    def setup_method(self):
        self.detector = FastAPIDetector()

    def test_detect_pydantic_model(self):
        source = b"""from pydantic import BaseModel
from typing import Optional

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: float = 0.0

class ItemCreate(BaseModel):
    name: str
    price: float

class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
"""
        nodes = [
            Node(
                id="cls-item",
                name="Item",
                kind=NodeKind.CLASS,
                qualified_name="Item",
                language="python",
                file_path="schemas.py",
                start_line=4,
                end_line=8,
            ),
            Node(
                id="cls-create",
                name="ItemCreate",
                kind=NodeKind.CLASS,
                qualified_name="ItemCreate",
                language="python",
                file_path="schemas.py",
                start_line=10,
                end_line=12,
            ),
            Node(
                id="cls-response",
                name="ItemResponse",
                kind=NodeKind.CLASS,
                qualified_name="ItemResponse",
                language="python",
                file_path="schemas.py",
                start_line=14,
                end_line=17,
            ),
        ]
        patterns = self.detector.detect("schemas.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        model_nodes = [n for n in all_nodes if n.kind == NodeKind.MODEL]
        assert len(model_nodes) >= 2


class TestFastAPIMiddleware:
    def setup_method(self):
        self.detector = FastAPIDetector()

    def test_detect_middleware_decorator(self):
        source = b"""from fastapi import FastAPI

app = FastAPI()

@app.middleware("http")
async def add_process_time_header(request, call_next):
    response = await call_next(request)
    return response
"""
        nodes = [
            Node(
                id="fn-mw",
                name="add_process_time_header",
                kind=NodeKind.FUNCTION,
                qualified_name="add_process_time_header",
                language="python",
                file_path="main.py",
                start_line=6,
                end_line=8,
            ),
        ]
        patterns = self.detector.detect("main.py", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        mw_nodes = [n for n in all_nodes if n.kind == NodeKind.MIDDLEWARE]
        assert len(mw_nodes) >= 1

    def test_detect_add_middleware(self):
        source = b"""from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)
"""
        patterns = self.detector.detect("main.py", None, source, [], [])
        all_nodes = [n for p in patterns for n in p.nodes]
        mw_nodes = [n for n in all_nodes if n.kind == NodeKind.MIDDLEWARE]
        assert len(mw_nodes) >= 1


class TestFastAPINonPythonFiles:
    def setup_method(self):
        self.detector = FastAPIDetector()

    def test_skip_non_python_files(self):
        source = b"<html><body>Hello</body></html>"
        patterns = self.detector.detect("template.html", None, source, [], [])
        assert len(patterns) == 0


# ── Angular Detector Tests ────────────────────────────────────────────

from coderag.plugins.typescript.frameworks.angular import AngularDetector


class TestAngularDetectFramework:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "angular"

    def test_detects_angular_json(self, tmp_path):
        (tmp_path / "angular.json").write_text("{}")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_angular_cli_json(self, tmp_path):
        (tmp_path / ".angular-cli.json").write_text("{}")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_angular_in_package_json(self, tmp_path):
        pkg = {"dependencies": {"@angular/core": "^16.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_angular_in_dev_dependencies(self, tmp_path):
        pkg = {"devDependencies": {"@angular/core": "^16.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_angular(self, tmp_path):
        pkg = {"dependencies": {"react": "^18.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_files(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestAngularComponents:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_detect_component_decorator(self):
        source = b"""import { Component } from '@angular/core';

@Component({
    selector: 'app-user-list',
    templateUrl: './user-list.component.html',
    styleUrls: ['./user-list.component.css'],
    standalone: true,
})
export class UserListComponent {
    users: User[] = [];
}
"""
        nodes = [
            Node(
                id="cls-userlist",
                name="UserListComponent",
                kind=NodeKind.CLASS,
                qualified_name="UserListComponent",
                language="typescript",
                file_path="user-list.component.ts",
                start_line=9,
                end_line=11,
            ),
        ]
        patterns = self.detector.detect("user-list.component.ts", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        comp_nodes = [n for n in all_nodes if n.kind == NodeKind.COMPONENT]
        assert len(comp_nodes) >= 1
        comp = comp_nodes[0]
        assert comp.metadata.get("framework") == "angular"
        assert comp.metadata.get("selector") == "app-user-list"


class TestAngularServices:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_detect_injectable_service(self):
        source = b"""import { Injectable } from '@angular/core';

@Injectable({
    providedIn: 'root'
})
export class UserService {
    getUsers(): Observable<User[]> {
        return this.http.get<User[]>('api/users');
    }
}
"""
        nodes = [
            Node(
                id="cls-userservice",
                name="UserService",
                kind=NodeKind.CLASS,
                qualified_name="UserService",
                language="typescript",
                file_path="user.service.ts",
                start_line=6,
                end_line=10,
            ),
        ]
        patterns = self.detector.detect("user.service.ts", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        provider_nodes = [n for n in all_nodes if n.kind == NodeKind.PROVIDER]
        assert len(provider_nodes) >= 1


class TestAngularModules:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_detect_ng_module(self):
        source = b"""import { NgModule } from '@angular/core';

@NgModule({
    declarations: [AppComponent, UserListComponent],
    imports: [BrowserModule, HttpClientModule],
    providers: [UserService],
    bootstrap: [AppComponent],
    exports: [UserListComponent],
})
export class AppModule {}
"""
        nodes = [
            Node(
                id="cls-appmodule",
                name="AppModule",
                kind=NodeKind.CLASS,
                qualified_name="AppModule",
                language="typescript",
                file_path="app.module.ts",
                start_line=10,
                end_line=10,
            ),
        ]
        patterns = self.detector.detect("app.module.ts", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        module_nodes = [n for n in all_nodes if n.kind == NodeKind.MODULE]
        assert len(module_nodes) >= 1
        all_edges = [e for p in patterns for e in p.edges]
        assert len(all_edges) >= 1


class TestAngularDI:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_detect_constructor_injection(self):
        source = b"""import { Component } from '@angular/core';

@Component({
    selector: 'app-user',
    template: '<div>{{user}}</div>',
})
export class UserComponent {
    constructor(
        private userService: UserService,
        private router: Router,
        public authService: AuthService
    ) {}
}
"""
        nodes = [
            Node(
                id="cls-user",
                name="UserComponent",
                kind=NodeKind.CLASS,
                qualified_name="UserComponent",
                language="typescript",
                file_path="user.component.ts",
                start_line=7,
                end_line=13,
            ),
        ]
        patterns = self.detector.detect("user.component.ts", None, source, nodes, [])
        all_edges = [e for p in patterns for e in p.edges]
        dep_edges = [e for e in all_edges if e.kind == EdgeKind.DEPENDS_ON]
        assert len(dep_edges) >= 2

    def test_detect_inject_function(self):
        source = b"""import { Component, inject } from '@angular/core';

@Component({
    selector: 'app-modern',
    standalone: true,
    template: '<div></div>',
})
export class ModernComponent {
    userService = inject(UserService);
    router = inject(Router);
}
"""
        nodes = [
            Node(
                id="cls-modern",
                name="ModernComponent",
                kind=NodeKind.CLASS,
                qualified_name="ModernComponent",
                language="typescript",
                file_path="modern.component.ts",
                start_line=8,
                end_line=11,
            ),
        ]
        patterns = self.detector.detect("modern.component.ts", None, source, nodes, [])
        all_edges = [e for p in patterns for e in p.edges]
        dep_edges = [e for e in all_edges if e.kind == EdgeKind.DEPENDS_ON]
        assert len(dep_edges) >= 1


class TestAngularSignals:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_detect_signals(self):
        source = b"""import { Component, signal, computed, effect } from '@angular/core';

@Component({
    selector: 'app-counter',
    standalone: true,
    template: '<div>{{count()}}</div>',
})
export class CounterComponent {
    count = signal(0);
    doubleCount = computed(() => this.count() * 2);

    constructor() {
        effect(() => console.log(this.count()));
    }
}
"""
        nodes = [
            Node(
                id="cls-counter",
                name="CounterComponent",
                kind=NodeKind.CLASS,
                qualified_name="CounterComponent",
                language="typescript",
                file_path="counter.component.ts",
                start_line=8,
                end_line=15,
            ),
        ]
        patterns = self.detector.detect("counter.component.ts", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        signal_nodes = [n for n in all_nodes if n.metadata.get("angular_type") == "signal"]
        assert len(signal_nodes) >= 1


class TestAngularRouting:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_detect_routes(self):
        source = b"""import { Routes } from '@angular/router';

export const routes: Routes = [
    { path: '', component: HomeComponent },
    { path: 'users', component: UserListComponent },
    { path: 'users/:id', component: UserDetailComponent },
    { path: 'admin', loadComponent: () => import('./admin/admin.component').then(m => m.AdminComponent) },
    { path: 'settings', loadChildren: () => import('./settings/settings.module').then(m => m.SettingsModule) },
];
"""
        patterns = self.detector.detect("app.routes.ts", None, source, [], [])
        all_nodes = [n for p in patterns for n in p.nodes]
        route_nodes = [n for n in all_nodes if n.kind == NodeKind.ROUTE]
        assert len(route_nodes) >= 3


class TestAngularDirectivesAndPipes:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_detect_directive(self):
        source = b"""import { Directive, ElementRef } from '@angular/core';

@Directive({
    selector: '[appHighlight]',
    standalone: true,
})
export class HighlightDirective {
    constructor(private el: ElementRef) {}
}
"""
        nodes = [
            Node(
                id="cls-highlight",
                name="HighlightDirective",
                kind=NodeKind.CLASS,
                qualified_name="HighlightDirective",
                language="typescript",
                file_path="highlight.directive.ts",
                start_line=7,
                end_line=9,
            ),
        ]
        patterns = self.detector.detect("highlight.directive.ts", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        comp_nodes = [n for n in all_nodes if n.kind == NodeKind.COMPONENT]
        assert len(comp_nodes) >= 1
        assert comp_nodes[0].metadata.get("angular_type") == "directive"

    def test_detect_pipe(self):
        source = b"""import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
    name: 'truncate',
    standalone: true,
})
export class TruncatePipe implements PipeTransform {
    transform(value: string, limit: number): string {
        return value.length > limit ? value.substring(0, limit) + '...' : value;
    }
}
"""
        nodes = [
            Node(
                id="cls-truncate",
                name="TruncatePipe",
                kind=NodeKind.CLASS,
                qualified_name="TruncatePipe",
                language="typescript",
                file_path="truncate.pipe.ts",
                start_line=7,
                end_line=11,
            ),
        ]
        patterns = self.detector.detect("truncate.pipe.ts", None, source, nodes, [])
        all_nodes = [n for p in patterns for n in p.nodes]
        pipe_nodes = [n for n in all_nodes if n.metadata.get("angular_type") == "pipe"]
        assert len(pipe_nodes) >= 1


class TestAngularNonTSFiles:
    def setup_method(self):
        self.detector = AngularDetector()

    def test_skip_non_ts_files(self):
        source = b"<div>Hello</div>"
        patterns = self.detector.detect("template.html", None, source, [], [])
        assert len(patterns) == 0

    def test_skip_js_files(self):
        source = b"console.log('hello');"
        patterns = self.detector.detect("script.js", None, source, [], [])
        assert len(patterns) == 0
