"""Policy retrieval tool using UiPath Context Grounding."""

from typing import Optional

from ..models import PolicyResult
from ..config import get_settings


def retrieve_policies(
    query: str,
    index_name: Optional[str] = None,
    top_k: int = 3
) -> list[PolicyResult]:
    """Query UiPath Context Grounding for relevant policy sections.
    
    Args:
        query: Natural language query for policy search
        index_name: Name of the Context Grounding index (default from settings)
        top_k: Number of results to return
        
    Returns:
        List of PolicyResult objects with text, source, and score
    """
    settings = get_settings()
    index = index_name or settings.context_grounding_index
    
    # TODO: Implement actual Context Grounding call when connected to UiPath
    # The actual implementation would use:
    # 
    # from uipath import UiPath
    # client = UiPath()
    # results = client.context_grounding.search(
    #     index_name=index,
    #     query=query,
    #     top_k=top_k
    # )
    # return [
    #     PolicyResult(
    #         text=r["content"],
    #         source=r.get("source", "unknown"),
    #         score=r.get("score", 0.0)
    #     )
    #     for r in results
    # ]
    
    # Stub implementation for local development
    # Returns empty list - will be replaced with actual Context Grounding
    return []


def retrieve_policies_for_applicant(
    credit_score: Optional[int] = None,
    dti_ratio: Optional[float] = None,
    ltv_ratio: Optional[float] = None,
    has_delinquencies: bool = False
) -> list[PolicyResult]:
    """Retrieve all relevant policies for an applicant's data.
    
    Generates targeted queries based on applicant metrics and
    retrieves relevant policy sections.
    
    Args:
        credit_score: Applicant's credit score
        dti_ratio: Debt-to-Income ratio percentage
        ltv_ratio: Loan-to-Value ratio percentage
        has_delinquencies: Whether applicant has delinquent accounts
        
    Returns:
        Combined list of relevant policy results
    """
    from .prompts import get_policy_queries
    
    queries = get_policy_queries(credit_score, dti_ratio, ltv_ratio)
    
    if has_delinquencies:
        queries.append("delinquent accounts derogatory marks policy")
    
    all_policies = []
    seen_sources = set()
    
    for query in queries:
        policies = retrieve_policies(query, top_k=2)
        for p in policies:
            if p.source not in seen_sources:
                seen_sources.add(p.source)
                all_policies.append(p)
    
    return all_policies
