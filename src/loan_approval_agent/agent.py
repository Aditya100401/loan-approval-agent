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
    DecisionType,
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
from .tools.decision_generator import generate_llm_decision


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
    print(f"[fetch_document] bucket={state['bucket_name']} path={state['document_path']}")
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
        print(f"[fetch_document] downloaded to {tmp.name}")
        return {"local_document_path": tmp.name}
    except Exception as e:
        print(f"[fetch_document] ERROR: {e}")
        return {"error": str(e), "error_node": "fetch_document"}


async def classify_node(state: LoanAgentState) -> dict:
    """Classify the document type."""
    if state.get("error"):
        print(f"[classify] skipped due to earlier error: {state.get('error')}")
        return {}
    try:
        path = state.get("local_document_path") or state["document_path"]
        result = classify_document(path)
        print(f"[classify] type={result.document_type} confidence={result.confidence}")
        return {"classification": result}
    except Exception as e:
        print(f"[classify] ERROR: {e}")
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
        print(f"[extract] name={result.applicant_name} credit={result.credit_score} income={result.annual_income}")
        return {"extracted_data": result}
    except Exception as e:
        print(f"[extract] ERROR: {e}")
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
    """Call the LLM to evaluate the applicant and generate a decision with email draft."""
    if state.get("error"):
        print(f"[generate_decision] skipped due to earlier error: {state.get('error')}")
        return {}
    try:
        applicant_data = state.get("applicant_data")
        policies = state.get("policies", [])

        if not applicant_data:
            print("[generate_decision] ERROR: no applicant data")
            return {"error": "No applicant data for decision", "error_node": "generate_decision"}

        result = await generate_llm_decision(applicant_data, policies)
        print(f"[generate_decision] decision={result.decision} applicant={result.applicant_name}")
        return {"decision": result}
    except Exception as e:
        print(f"[generate_decision] ERROR: {e}")
        return {"error": str(e), "error_node": "generate_decision"}


async def _send_email(connection_id: str, to: str, subject: str, body: str) -> None:
    """Send an email via Gmail REST API using an OAuth token from the UiPath connection."""
    if _sdk is None:
        return

    import base64
    import httpx
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from uipath.platform.connections.connections import ConnectionTokenType

    token_info = await _sdk.connections.retrieve_token_async(
        key=connection_id,
        token_type=ConnectionTokenType.DIRECT,
    )
    access_token = token_info.access_token

    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
            timeout=30,
        )
        resp.raise_for_status()
    print(f"[_send_email] sent to {to}")


async def setup_hitl_node(state: LoanAgentState) -> dict:
    """Create the Action Center task and notify the reviewer.

    This node runs ONCE and completes before the interrupt node, so its side
    effects (task creation, reviewer email) are not repeated on resume.
    The task_id is persisted to state before the graph pauses.
    """
    decision = state.get("decision")
    if isinstance(decision, dict):
        decision = Decision.model_validate(decision)

    applicant_name = (decision.applicant_name or "Unknown") if decision else "Unknown"
    ai_recommendation = decision.decision.value if decision else "ERROR"

    # Retrieve Gmail connection ID and Action Center app name from UiPath Assets
    gmail_connection_id = None
    loan_review_app_name = None
    if _sdk is not None:
        try:
            asset = await _sdk.assets.retrieve_async("gmail_connection_id", folder_path="Shared")
            gmail_connection_id = asset.value
        except Exception:
            pass
        try:
            app_asset = await _sdk.assets.retrieve_async("loan_review_app_name", folder_path="Shared")
            loan_review_app_name = app_asset.value
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
                app_name=loan_review_app_name,
                priority="High" if ai_recommendation == "YELLOW" else "Medium",
            )
            task_id = task.action_key
            print(f"[setup_hitl] task created: {task_id}")
        except Exception as e:
            print(f"[setup_hitl] task creation failed: {e}")

    # Email reviewer
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
        except Exception as e:
            print(f"[setup_hitl] reviewer email failed: {e}")

    # Persist task_id to state — the checkpoint captures this before the graph pauses
    return {"hitl_task_id": task_id}


async def wait_for_review_node(state: LoanAgentState) -> dict:
    """Suspend for human approval, then apply the reviewer's decision.

    This node is safe to restart from the beginning on resume: interrupt() simply
    returns the resume payload on the second entry instead of pausing again.
    Side effects here (applicant email) only execute after the review is received.
    """
    decision = state.get("decision")
    if isinstance(decision, dict):
        decision = Decision.model_validate(decision)

    task_id = state.get("hitl_task_id", "unknown")
    applicant_name = (decision.applicant_name or "Unknown") if decision else "Unknown"
    ai_recommendation = decision.decision.value if decision else "ERROR"
    applicant_email = state.get("applicant_email")

    # Suspend — on resume, interrupt() immediately returns the reviewer's payload.
    # Expected payload: {"final_decision": "GREEN"|"YELLOW"|"RED", "comments": "..."}
    review = interrupt({
        "task_id": task_id,
        "ai_recommendation": ai_recommendation,
        "applicant_name": applicant_name,
    })

    # UiPath runtime passes the Action Center resume payload as a JSON string, not a dict.
    if isinstance(review, str):
        import json
        try:
            review = json.loads(review)
        except (json.JSONDecodeError, ValueError):
            review = {"final_decision": review}

    # Apply reviewer's decision
    final_decision_value = review.get("final_decision", ai_recommendation)
    comments = review.get("comments", "")
    was_overridden = final_decision_value != ai_recommendation

    updated_decision = decision.model_copy(update={
        "decision": DecisionType(final_decision_value),
        "requires_human_review": False,
        "human_review_status": "overridden" if was_overridden else "approved",
        "human_review_comments": comments,
    }) if decision else decision

    # Retrieve Gmail connection ID (re-fetch; cheap and avoids stale process-cached state)
    gmail_connection_id = None
    if _sdk is not None:
        try:
            asset = await _sdk.assets.retrieve_async("gmail_connection_id", folder_path="Shared")
            gmail_connection_id = asset.value
        except Exception:
            pass

    # Email applicant with final decision
    if gmail_connection_id and applicant_email:
        try:
            decision_label = {
                "GREEN": "Approved",
                "YELLOW": "Conditionally Approved",
                "RED": "Declined",
            }.get(final_decision_value, final_decision_value)

            if not was_overridden and updated_decision and updated_decision.email_draft:
                email_body = updated_decision.email_draft
            else:
                outcome_line = {
                    "GREEN": (
                        f"We are pleased to inform you that your loan application has been "
                        f"<b>approved</b>. A member of our team will be in touch to walk you "
                        f"through the next steps."
                    ),
                    "YELLOW": (
                        f"Your loan application has been <b>conditionally approved</b>. "
                        f"There are a few outstanding items we will need to discuss with you "
                        f"before finalising your offer."
                    ),
                    "RED": (
                        f"After careful review by our underwriting team, we are unable to "
                        f"approve your loan application at this time."
                    ),
                }.get(final_decision_value, f"Your application outcome is: <b>{decision_label}</b>.")

                underwriter_note = (
                    f"<p><b>Note from our underwriting team:</b> {comments}</p>"
                    if comments else ""
                )

                email_body = (
                    f"<p>Dear {applicant_name},</p>"
                    f"<p>Thank you for your loan application with Meridian Lending. "
                    f"{outcome_line}</p>"
                    f"{underwriter_note}"
                    f"<p>If you have any questions, please do not hesitate to contact us. "
                    f"A Meridian Lending representative will be in touch with you shortly.</p>"
                    f"<p>Sincerely,<br/><b>The Meridian Lending Team</b><br/>"
                    f"<small style='color:#888;'>Meridian Lending, LLC — NMLS #000000 — "
                    f"Equal Housing Lender</small></p>"
                )

            await _send_email(
                connection_id=gmail_connection_id,
                to=applicant_email,
                subject="Your Loan Application — Meridian Lending",
                body=email_body,
            )
        except Exception as e:
            print(f"[wait_for_review] applicant email failed: {e}")

    return {
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
    # HITL is split into two nodes so setup side-effects run exactly once:
    # setup_hitl completes and persists task_id before the graph pauses;
    # wait_for_review safely restarts from the top on resume (interrupt() returns
    # the resume payload immediately on the second entry).
    graph.add_node("setup_hitl", setup_hitl_node)
    graph.add_node("wait_for_review", wait_for_review_node)

    graph.set_entry_point("fetch_document")

    graph.add_edge("fetch_document", "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "retrieve_policies")
    graph.add_edge("retrieve_policies", "generate_decision")
    graph.add_edge("generate_decision", "setup_hitl")
    graph.add_edge("setup_hitl", "wait_for_review")
    graph.add_edge("wait_for_review", END)

    from langgraph.checkpoint.memory import MemorySaver
    return graph.compile(checkpointer=MemorySaver())


# =============================================================================
# AGENT INSTANCE
# =============================================================================

agent = build_graph()
