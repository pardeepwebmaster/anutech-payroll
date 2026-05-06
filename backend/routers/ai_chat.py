"""AI chat router — proxies user queries to the orchestrator."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..agents import AgentContext
from ..agents.orchestrator import get_orchestrator
from ..core.database import get_master_session, get_tenant_session
from ..core.security import CurrentUser, get_current_user
from ..models.master_models import Tenant

router = APIRouter()
log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    text: str
    agent: str
    tool_calls: list[dict] = []
    usage: dict[str, int] = {}
    cached: bool = False


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_tenant_session),
    master: Session = Depends(get_master_session),
    current: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    tenant = master.query(Tenant).filter(Tenant.schema_name == current.tenant_schema).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    ctx = AgentContext(
        tenant_id=tenant.id,
        tenant_schema=tenant.schema_name,
        user_id=current.user_id,
        company_name=tenant.name,
        conversation_id=payload.conversation_id,
    )

    response = get_orchestrator().handle(payload.message, ctx)
    return ChatResponse(
        text=response.text,
        agent=response.agent_name,
        tool_calls=response.tool_calls,
        usage=response.usage,
        cached=response.cached,
    )


@router.get("/agents")
def list_agents(_: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        "agents": [
            {"name": "hr", "description": "Employees, leaves, approvals"},
            {"name": "payroll", "description": "Salary calculations, payslips, anomalies"},
            {"name": "finance", "description": "Spend aggregates, Zoho Books sync"},
            {"name": "compliance", "description": "PF, ESI, TDS, PT deadlines"},
        ]
    }


@router.get("/logs")
def recent_logs(
    db: Session = Depends(get_tenant_session),
    _: CurrentUser = Depends(get_current_user),
    limit: int = 50,
) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT agent_name, action, input_summary, created_at FROM agent_logs "
            "ORDER BY created_at DESC LIMIT :lim"
        ),
        {"lim": limit},
    ).all()
    return [
        {
            "agent_name": r.agent_name,
            "action": r.action,
            "query": r.input_summary,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
