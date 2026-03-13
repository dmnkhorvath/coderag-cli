import pytest

from coderag.plugins.php.frameworks.symfony import SymfonyDetector


@pytest.fixture
def detector():
    return SymfonyDetector()


def test_detect_controller_fallback(detector):
    source = rb"""<?php
namespace App\Controller;
class MyController extends AbstractController {
    #[Route('/api/users', name: 'user_list', methods: ['GET'])]
    public function list() {
        $this->render('users/list.html.twig');
    }
}"""
    # Pass empty nodes list to trigger regex fallbacks
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0


def test_detect_entity_fallback(detector):
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
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0


def test_detect_dependency_injection_fallback(detector):
    source = b"""<?php
class MyService {
    public function __construct(private LoggerInterface $logger, public Mailer $mailer) {}
}"""
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0


def test_detect_events_fallback(detector):
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
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0


def test_detect_security_fallback(detector):
    source = b"""<?php
class MyController {
    #[IsGranted('ROLE_ADMIN')]
    public function admin() {}
}
class MyVoter extends Voter {}"""
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0
