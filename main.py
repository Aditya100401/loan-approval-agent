"""Main entry point for the Loan Approval Agent.

This module exposes the LangGraph agent for UiPath deployment.
The agent is defined in src/loan_approval_agent/agent.py
"""

import logging

# Suppress verbose INFO/DEBUG from LangGraph checkpoint serializer; WARNING and above
# (including real deserialization failures) still surface.
logging.getLogger("langgraph.checkpoint.serde.jsonplus").setLevel(logging.WARNING)
# Suppress OpenInferenceTracer callback error — missing on_interrupt in UiPath SDK tracer.
# Logged as WARNING by langchain_core.callbacks.manager.handle_event when a handler
# doesn't implement a lifecycle method (UiPath SDK bug, not our code).
logging.getLogger("langchain_core.callbacks.manager").setLevel(logging.ERROR)

from src.loan_approval_agent.agent import agent, Input, Output, LoanAgentState, build_graph

__all__ = ["agent", "Input", "Output", "LoanAgentState", "build_graph"]


if __name__ == "__main__":
    # Local testing
    import json
    
    # Example input
    test_input = {
        "document_path": "data/sample_credit_report.pdf",
        "applicant_email": None
    }
    
    print("Loan Approval Agent - Local Test")
    print("=" * 40)
    print(f"Input: {json.dumps(test_input, indent=2)}")
    print("\nRunning agent...")
    
    # Run the agent
    result = agent.invoke(test_input)
    
    print("\nResult:")
    print(json.dumps(result, indent=2, default=str))
