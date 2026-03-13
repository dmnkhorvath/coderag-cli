from coderag.plugins.php.extractor import PHPExtractor, _node_text


def test_node_text_none():
    assert _node_text(None, b"") == ""


def test_php_extractor_edge_cases():
    source = b"""<?php
    final class MyClass {
        static public $myProp;
    }
    function noParams { }
    namespace MyNamespace {
        class A {}
    }
    use App\\Models\User as UserModel;
    use \\Some\\Weird\NamespaceName;
    class {}
    interface {}
    interface MyInterface extends BaseInterface {}
    trait {}
    enum {}
    enum MyEnum implements SomeInterface {}
    class B {
        public function () {}
    }
    class C {
        public $;
    }
    class D {
        const ;
    }
    $ = 5;
    define();
    ()();
    $x = new \\GlobalClass();
    $y = new UserModel();
    """
    extractor = PHPExtractor()
    extractor.use_map = {"UserModel": "App\\Models\\User"}
    result = extractor.extract("edge_cases.php", source)
    assert result is not None
