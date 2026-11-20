"""Proposals API: draft + CRUD + outcome (US-D1/D3/E1, 02_AppFlow §4.7-4.8).

POST /jobs/{id}/draft — generate via LangGraph, deduct credit on success only.
GET/PATCH/DELETE /proposals, GET/PATCH /proposals/{id}."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import graph as agent_graph
from app.api.deps import get_current_user_id, get_tenant_db
from app.db.models.job import Job
from app.db.models.proposal import Proposal
from app.db.models.score import Score
from app.db.models.user import Profile
from app.db.session import system_session, tenant_session
from app.schemas.proposals import DraftOut, ProposalOut, ProposalPatch
from app.services.credits import check_and_reserve_credit, get_credit_status, release_credit

router = APIRouter(tags=["proposals"])


def _proposal_out(p: Proposal) -> ProposalOut:
    return ProposalOut(
        id=p.id,
        job_id=p.job_id,
        content=p.content,
        status=p.status,
        outcome=p.outcome,
        voice_matched=p.voice_matched,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.post("/jobs/{job_id}/draft", response_model=DraftOut)
async def create_draft(
    job_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DraftOut:
    async with tenant_session(str(user_id)) as session:
        job = await session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

        profile = await session.get(Profile, user_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Complete your profile first.")

        try:
            await check_and_reserve_credit(user_id, session)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))

        rate_part = f"Rate: ${profile.hourly_rate}/hr. " if profile.hourly_rate else ""
        profile_summary = (
            f"Skills: {', '.join(profile.skills or [])}. "
            f"Experience: {profile.experience_level}. "
            f"{rate_part}Category: {profile.primary_category}."
        )
        job_summary = f"Title: {job.title}. Description: {job.description[:1500]}."

        score_row = await session.scalar(
            select(Score)
            .where(Score.user_id == user_id, Score.job_id == job_id)
            .order_by(Score.created_at.desc())
            .limit(1)
        )
        score_val = score_row.score if score_row else None

        try:
            result = await agent_graph.ainvoke({
                "user_id": str(user_id),
                "job_id": str(job_id),
                "profile_summary": profile_summary,
                "job_summary": job_summary,
                "score": score_val,
                "voice_chunks": [],
                "draft": None,
                "voice_matched": False,
                "error": None,
            })
        except Exception as exc:
            await release_credit(user_id, session)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Draft generation failed: {exc}")

        if result.get("error") or not result.get("draft"):
            await release_credit(user_id, session)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Draft generation failed.")

        proposal = Proposal(
            user_id=user_id,
            job_id=job_id,
            content=result["draft"],
            voice_matched=result.get("voice_matched", False),
        )
        session.add(proposal)
        await session.flush()

        credits = await get_credit_status(user_id, session)

        return DraftOut(
            proposal_id=proposal.id,
            content=proposal.content,
            voice_matched=proposal.voice_matched,
            credits_remaining=credits["drafts_remaining"],
        )


@router.get("/proposals", response_model=list[ProposalOut])
async def list_proposals(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ProposalOut]:
    async with tenant_session(str(user_id)) as session:
        rows = await session.scalars(
            select(Proposal)
            .where(Proposal.user_id == user_id)
            .order_by(Proposal.created_at.desc())
            .limit(100)
        )
        return [_proposal_out(p) for p in rows.all()]


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
async def get_proposal(
    proposal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProposalOut:
    async with tenant_session(str(user_id)) as session:
        p = await session.get(Proposal, proposal_id)
        if p is None or p.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found.")
        return _proposal_out(p)


@router.patch("/proposals/{proposal_id}", response_model=ProposalOut)
async def patch_proposal(
    proposal_id: uuid.UUID,
    body: ProposalPatch,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProposalOut:
    async with tenant_session(str(user_id)) as session:
        p = await session.get(Proposal, proposal_id)
        if p is None or p.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found.")

        if body.content is not None:
            p.content = body.content
        if body.status is not None:
            p.status = body.status
        if body.outcome is not None:
            p.outcome = body.outcome

        await session.flush()
        return _proposal_out(p)


@router.delete("/proposals/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proposal(
    proposal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    async with tenant_session(str(user_id)) as session:
        p = await session.get(Proposal, proposal_id)
        if p is None or p.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found.")
        await session.delete(p)
