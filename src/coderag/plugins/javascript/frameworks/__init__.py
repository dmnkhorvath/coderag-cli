"""Framework detectors for JavaScript/TypeScript projects."""

from coderag.plugins.javascript.frameworks.express import ExpressDetector
from coderag.plugins.javascript.frameworks.nextjs import NextJSDetector
from coderag.plugins.javascript.frameworks.react import ReactDetector
from coderag.plugins.javascript.frameworks.vue import VueDetector

__all__ = [
    "ExpressDetector",
    "NextJSDetector",
    "ReactDetector",
    "VueDetector",
]
