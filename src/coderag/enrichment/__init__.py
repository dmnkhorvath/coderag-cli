"""CodeRAG enrichment modules.

Provides post-extraction enrichment phases:
- GitEnricher: git metadata (change frequency, co-change, ownership, churn)
"""
from coderag.enrichment.git_enricher import GitEnricher

__all__ = ["GitEnricher"]
