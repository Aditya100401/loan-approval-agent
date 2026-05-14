"""Main LangGraph agent for loan approval.

This module defines the state machine that orchestrates the loan approval workflow:
Fetch Document → Classify → Extract → Validate → Retrieve Policies → Generate Decision → Create HITL Task
"""

import tempfile
import os
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from pydantic import BaseModel

from .models import (
    ClassificationResult,
    ExtractedData,
    ApplicantData,
    Decision,
    PolicyResult,
)

# Initialize UiPath SDK — skipped gracefully in local dev without credentials
try:
    from uipath.platform import UiPath as _UiPath
    _sdk = _UiPath()
except Exception:
    _sdk = None


# =============================================================================
# INPUT / OUTPUT SCHEMAS (exposed to UiPath runner)
# =============================================================================

class Input(BaseModel):
    """What the agent accepts from UiPath Orchestrator."""
    document_path: str
    bucket_name: str = "loan-applications"
    applicant_email: str | None = None


class Output(BaseModel):
    """What the agent returns to UiPath Orchestrator."""
    decision: Decision | None = None
    hitl_task_id: str | None = None
    error: str | None = None

from .tools.classifier import classify_document
from .tools.extractor import extract_information
from .tools.validator import validate_data
from .tools.policy_retriever import retrieve_policies
from .tools.decision_generator import generate_decision


# =============================================================================
# STATE DEFINITION
# =============================================================================

class LoanAgentState(TypedDict):
    """Shared state passed between agent nodes."""
    # Input
    document_path: str
    bucket_name: str
    applicant_email: str | None

    # Downloaded local path (set by fetch_document_node)
    local_document_path: str | None

    # Classification
    classification: ClassificationResult | None

    # Extraction
    extracted_data: ExtractedData | None

    # Validation
    applicant_data: ApplicantData | None

    # Policy Retrieval
    policies: list[PolicyResult]

    # Decision
    decision: Decision | None

    # HITL
    hitl_task_id: str | None

    # Error handling
    error: str | None
    error_node: str | None


# =============================================================================
# NODE FUNCTIONS
# =============================================================================

async def fetch_document_node(state: LoanAgentState) -> dict:
    """Download document from UiPath Storage Bucket to a local temp file.

    Falls back to using document_path directly when running locally without SDK.
    """
    if _sdk is None:
        return {"local_document_path": state["document_path"]}

    try:
        ext = os.path.splitext(state["document_path"])[1] or ".pdf"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.close()

        await _sdk.buckets.download_async(
            name=state["bucket_name"],
            blob_file_path=state["document_path"],
            destination_path=tmp.name,
        )
        return {"local_document_path": tmp.name}
    except Exception as e:
        return {"error": str(e), "error_node": "fetch_document"}


async def classify_node(state: LoanAgentState) -> dict:
    """Classify the document type."""
    if state.get("error"):
        return {}
    try:
        path = state.get("local_document_path") or state["document_path"]
        result = classify_document(path)
        return {"classification": result}
    except Exception as e:
        return {"error": str(e), "error_node": "classify"}


async def extract_node(state: LoanAgentState) -> dict:
    """Extract information from the document."""
    if state.get("error"):
        return {}
    try:
        classification = state.get("classification")
        doc_type = classification.document_type if classification else "unknown"
        path = state.get("local_document_path") or state["document_path"]
        result = extract_information(path, doc_type)
        return {"extracted_data": result}
    except Exception as e:
        return {"error": str(e), "error_node": "extract"}


async def validate_node(state: LoanAgentState) -> dict:
    """Validate extracted data and calculate metrics."""
    if state.get("error"):
        return {}
    try:
        extracted = state.get("extracted_data")
        if not extracted:
            return {"error": "No extracted data to validate", "error_node": "validate"}
        path = state.get("local_document_path") or state["document_path"]
        result = validate_data(extracted, [path])
        return {"applicant_data": result}
    except Exception as e:
        return {"error": str(e), "error_node": "validate"}


async def retrieve_policies_node(state: LoanAgentState) -> dict:
    """Retrieve relevant policies from Context Grounding."""
    if state.get("error"):
        return {}
    try:
        applicant_data = state.get("applicant_data")
        if not applicant_data:
            return {"policies": []}

        extracted = applicant_data.extracted_data
        from .tools.prompts import get_policy_queries

        queries = get_policy_queries(
            credit_score=extracted.credit_score,
            dti_ratio=applicant_data.dti_ratio,
            ltv_ratio=applicant_data.ltv_ratio
        )

        all_policies = []
        for query in queries:
            policies = retrieve_policies(query)
            all_policies.extend(policies)

        seen = set()
        unique_policies = []
        for p in all_policies:
            if p.source not in seen:
                seen.add(p.source)
                unique_policies.append(p)

        return {"policies": unique_policies}
    except Exception as e:
        return {"error": str(e), "error_node": "retrieve_policies"}


async def generate_decision_node(state: LoanAgentState) -> dict:
    """Generate the loan decision."""
    if state.get("error"):
        return {}
    try:
        applicant_data = state.get("applicant_data")
        policies = state.get("policies", [])

        if not applicant_data:
            return {"error": "No applicant data for decision", "error_node": "generate_decision"}

        result = generate_decision(applicant_data, policies)
        return {"decision": result}
    except Exception as e:
        return {"error": str(e), "error_node": "generate_decision"}


async def _send_email(connection_id: str, to: str, subject: str, body: str) -> None:
    """Send an email via UiPath Integration Service Gmail connector.

    Uses metadata_async to discover the correct activity path at runtime,
    then caches the result for subsequent calls.
    """
    if _sdk is None:
        return

    from uipath.platform.connections import ActivityMetadata, ActivityParameterLocationInfo

    # Discover activity metadata once per process lifetime
    if not hasattr(_send_email, "_metadata"):
        try:
            connections = await _sdk.connections.list_async(folder_path="Shared")
            conn = next(
                (c for c in connections if str(c.id) == connection_id), None
            )
            if conn is None:
                return

            raw = await _sdk.connections.metadata_async(
                element_instance_id=conn.element_instance_id,
                connector_key="uipath-google-gmail",
                tool_path="/messages/send",
            )
            _send_email._metadata = ActivityMetadata(
                object_path="/messages/send",
                method_name=raw.metadata.get("method", "POST"),
                content_type="application/json",
                parameter_location_info=ActivityParameterLocationInfo(
                    body_fields=["to", "subject", "body", "bodyType"],
                ),
            )
        except Exception:
            return

    await _sdk.connections.invoke_activity_async(
        activity_metadata=_send_email._metadata,
        connection_id=connection_id,
        activity_input={
            "to": to,
            "subject": subject,
            "body": body,
            "bodyType": "Html",
        },
    )


async def create_hitl_node(state: LoanAgentState) -> dict:
    """Create Action Center task, suspend for human approval, then apply reviewer's decision."""
    decision = state.get("decision")
    applicant_name = (decision.applicant_name or "Unknown") if decision else "Unknown"
    ai_recommendation = decision.decision.value if decision else "ERROR"
    applicant_email = state.get("applicant_email")

    # Retrieve Gmail connection ID from UiPath Asset
    gmail_connection_id = None
    if _sdk is not None:
        try:
            asset = await _sdk.assets.retrieve_async("gmail_connection_id")
            gmail_connection_id = asset.value
        except Exception:
            pass

    # Create Action Center task
    task_id = f"local-hitl-{applicant_name}"
    if _sdk is not None:
        try:
            task = await _sdk.tasks.create_async(
                title=f"Loan Review: {applicant_name} — {ai_recommendation}",
                data={
                    "applicant_name": applicant_name,
                    "ai_recommendation": ai_recommendation,
                    "reasoning": decision.reasoning if decision else "",
                    "credit_score": decision.credit_score if decision else None,
                    "dti_ratio": decision.dti_ratio if decision else None,
                    "ltv_ratio": decision.ltv_ratio if decision else None,
                },
                priority="High" if ai_recommendation == "YELLOW" else "Medium",
            )
            task_id = task.action_key
        except Exception:
            pass

    # Email reviewer before suspending
    if gmail_connection_id:
        try:
            await _send_email(
                connection_id=gmail_connection_id,
                to="adityasampath01@gmail.com",
                subject=f"Action Required: Loan Review — {applicant_name}",
                body=(
                    f"<p>A loan application requires your review.</p>"
                    f"<p><b>Applicant:</b> {applicant_name}<br>"
                    f"<b>AI Recommendation:</b> {ai_recommendation}<br>"
                    f"<b>Task ID:</b> {task_id}</p>"
                    f"<p>Please open <a href='https://cloud.uipath.com'>Action Center</a> to review.</p>"
                ),
            )
        except Exception:
            pass

    # Suspend — resumes when reviewer submits decision in Action Center
    # Expected resume payload: {"final_decision": "GREEN"|"YELLOW"|"RED", "comments": "..."}
    review = interrupt({
        "task_id": task_id,
        "ai_recommendation": ai_recommendation,
        "applicant_name": applicant_name,
    })

    # Apply reviewer's decision
    final_decision_value = review.get("final_decision", ai_recommendation)
    comments = review.get("comments", "")
    was_overridden = final_decision_value != ai_recommendation

    updated_decision = decision.model_copy(update={
        "decision": final_decision_value,
        "requires_human_review": False,
        "human_review_status": "overridden" if was_overridden else "approved",
        "human_review_comments": comments,
    }) if decision else decision

    # Email applicant with final decision
    if gmail_connection_id and applicant_email:
        try:
            decision_label = {
                "GREEN": "Approved",
                "YELLOW": "Conditionally Approved",
                "RED": "Declined",
            }.get(final_decision_value, final_decision_value)

            await _send_email(
                connection_id=gmail_connection_id,
                to=applicant_email,
                subject=f"Your Loan Application Decision — {decision_label}",
                body=(
                    f"<p>Dear {applicant_name},</p>"
                    f"<p>Your loan application has been reviewed. Decision: <b>{decision_label}</b>.</p>"
                    f"<p>{comments}</p>"
                    f"<p>A Meridian Lending representative will be in touch shortly.</p>"
                ),
            )
        except Exception:
            pass

    return {
        "hitl_task_id": task_id,
        "decision": updated_decision,
        "error": state.get("error"),
    }


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def build_graph() -> StateGraph:
    """Build and compile the LangGraph agent graph."""
    graph = StateGraph(LoanAgentState, input=Input, output=Output)

    graph.add_node("fetch_document", fetch_document_node)
    graph.add_node("classify", classify_node)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("retrieve_policies", retrieve_policies_node)
    graph.add_node("generate_decision", generate_decision_node)
    graph.add_node("create_hitl", create_hitl_node)

    graph.set_entry_point("fetch_document")

    graph.add_edge("fetch_document", "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "retrieve_policies")
    graph.add_edge("retrieve_policies", "generate_decision")
    graph.add_edge("generate_decision", "create_hitl")
    graph.add_edge("create_hitl", END)

    from langgraph.checkpoint.memory import MemorySaver
    return graph.compile(checkpointer=MemorySaver())


# =============================================================================
# AGENT INSTANCE
# =============================================================================

agent = build_graph()
