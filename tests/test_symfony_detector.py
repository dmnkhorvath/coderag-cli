import pytest

from coderag.core.models import Node, NodeKind
from coderag.plugins.php.frameworks.symfony import SymfonyDetector


@pytest.fixture
def detector():
    return SymfonyDetector()


def test_detect_framework(detector, tmp_path):
    assert not detector.detect_framework(str(tmp_path))
    (tmp_path / "symfony.lock").touch()
    assert detector.detect_framework(str(tmp_path))


def test_detect_controller_and_routes(detector):
    source = rb"""<?php
namespace App\Controller;
class MyController extends AbstractController {
    #[Route('/api/users', name: 'user_list', methods: ['GET'])]
    public function list() {
        $this->render('users/list.html.twig');
    }
}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="MyController",
            qualified_name="App\\Controller\\MyController",
            file_path="test.php",
            start_line=3,
            end_line=8,
            language="php",
        ),
        Node(
            id="m1",
            kind=NodeKind.METHOD,
            name="list",
            qualified_name="App\\Controller\\MyController::list",
            file_path="test.php",
            start_line=5,
            end_line=7,
            language="php",
        ),
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_entity(detector):
    source = rb"""<?php
namespace App\Entity;
#[ORM\Entity(repositoryClass: UserRepository::class)]
#[ORM\Table(name: 'users')]
class User {
    #[ORM\Id]
    #[ORM\Column(type: 'integer')]
    private $id;
    #[ORM\OneToMany(targetEntity: Post::class)]
    private $posts;
}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="User",
            qualified_name="App\\Entity\\User",
            file_path="test.php",
            start_line=5,
            end_line=11,
            language="php",
        )
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_dependency_injection(detector):
    source = b"""<?php
class MyService {
    public function __construct(private LoggerInterface $logger, public Mailer $mailer) {}
}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="MyService",
            qualified_name="MyService",
            file_path="test.php",
            start_line=2,
            end_line=4,
            language="php",
        ),
        Node(
            id="m1",
            kind=NodeKind.METHOD,
            name="__construct",
            qualified_name="MyService::__construct",
            file_path="test.php",
            start_line=3,
            end_line=3,
            language="php",
        ),
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_events(detector):
    source = b"""<?php
class MyListener {
    #[AsEventListener(event: 'kernel.request')]
    public function onKernelRequest() {}
}
class MySubscriber implements EventSubscriberInterface {
    public function doSomething() {
        $dispatcher->dispatch(new UserRegisteredEvent());
    }
}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="MyListener",
            qualified_name="MyListener",
            file_path="test.php",
            start_line=2,
            end_line=5,
            language="php",
        ),
        Node(
            id="m1",
            kind=NodeKind.METHOD,
            name="onKernelRequest",
            qualified_name="MyListener::onKernelRequest",
            file_path="test.php",
            start_line=4,
            end_line=4,
            language="php",
        ),
        Node(
            id="c2",
            kind=NodeKind.CLASS,
            name="MySubscriber",
            qualified_name="MySubscriber",
            file_path="test.php",
            start_line=6,
            end_line=10,
            language="php",
        ),
        Node(
            id="m2",
            kind=NodeKind.METHOD,
            name="doSomething",
            qualified_name="MySubscriber::doSomething",
            file_path="test.php",
            start_line=7,
            end_line=9,
            language="php",
        ),
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_form_types(detector):
    source = b"""<?php
class UserType extends AbstractType {}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="UserType",
            qualified_name="UserType",
            file_path="test.php",
            start_line=2,
            end_line=2,
            language="php",
        )
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_commands(detector):
    source = b"""<?php
#[AsCommand(name: 'app:create-user')]
class CreateUserCommand extends Command {}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="CreateUserCommand",
            qualified_name="CreateUserCommand",
            file_path="test.php",
            start_line=3,
            end_line=3,
            language="php",
        )
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_security(detector):
    source = b"""<?php
class MyController {
    #[IsGranted('ROLE_ADMIN')]
    public function admin() {}
}
class MyVoter extends Voter {}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="MyController",
            qualified_name="MyController",
            file_path="test.php",
            start_line=2,
            end_line=5,
            language="php",
        ),
        Node(
            id="m1",
            kind=NodeKind.METHOD,
            name="admin",
            qualified_name="MyController::admin",
            file_path="test.php",
            start_line=4,
            end_line=4,
            language="php",
        ),
        Node(
            id="c2",
            kind=NodeKind.CLASS,
            name="MyVoter",
            qualified_name="MyVoter",
            file_path="test.php",
            start_line=6,
            end_line=6,
            language="php",
        ),
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0
