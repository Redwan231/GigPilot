"""MCP server for GigPilot (04_TRD §10).

Exposes: search_jobs, score_job, draft_proposal, list_proposals, set_outcome.
Auth: MCP_AUTH_TOKEN env var → maps to a user_id via a lookup in the DB.
Enforces the same tenant scope / credits / caps / guardrails as the HTTP API.
Never bypasses RLS."""

import os
import uuid

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("gigpilot")

MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
MCP_USER_ID = os.environ.get("MCP_USER_ID", "")


def _require_auth(token: str | None) -> uuid.UUID:
    if not token or token != MCP_AUTH_TOKEN or not MCP_USER_ID:
        raise PermissionError("Invalid or missing MCP_AUTH_TOKEN")
    return uuid.UUID(MCP_USER_ID)


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_jobs",
            description="Search aggregated job listings with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "MCP_AUTH_TOKEN"},
                    "platform": {"type": "string"},
                    "category": {"type": "string"},
                    "skill": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["token"],
            },
        ),
        Tool(
            name="score_job",
            description="Compute or retrieve a cached fit score for a job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string"},
                    "job_id": {"type": "string", "description": "UUID of the job"},
                },
                "required": ["token", "job_id"],
            },
        ),
        Tool(
            name="draft_proposal",
            description="Generate a proposal draft for a job. Consumes one draft credit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string"},
                    "job_id": {"type": "string"},
                },
                "required": ["token", "job_id"],
            },
        ),
        Tool(
            name="list_proposals",
            description="List the user's proposals.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string"},
                },
                "required": ["token"],
            },
        ),
        Tool(
            name="set_outcome",
            description="Set the outcome for a proposal (won/lost/no_response).",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string"},
                    "proposal_id": {"type": "string"},
                    "outcome": {
                        "type": "string",
                        "enum": ["won", "lost", "no_response", "pending"],
                    },
                },
                "required": ["token", "proposal_id", "outcome"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    import json

    token = arguments.get("token")

    try:
        user_id = _require_auth(token)
    except PermissionError as exc:
        return [TextContent(type="text", text=f"Error: {exc}")]

    try:
        if name == "search_jobs":
            result = await _search_jobs(user_id, arguments)
        elif name == "score_job":
            result = await _score_job(user_id, arguments)
        elif name == "draft_proposal":
            result = await _draft_proposal(user_id, arguments)
        elif name == "list_proposals":
            result = await _list_proposals(user_id)
        elif name == "set_outcome":
            result = await _set_outcome(user_id, arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    return [TextContent(type="text", text=json.dumps(result, default=str))]


async def _search_jobs(user_id: uuid.UUID, args: dict) -> dict:
    from sqlalchemy import select

    from app.db.models.job import Job
    from app.db.session import system_session

    limit = min(int(args.get("limit", 10)), 50)
    async with system_session() as session:
        q = select(Job).where(Job.is_active.is_(True))
        if args.get("platform"):
            q = q.where(Job.platform == args["platform"])
        if args.get("category"):
            q = q.where(Job.category == args["category"])
        if args.get("skill"):
            q = q.where(Job.skills.any(args["skill"]))
        q = q.order_by(Job.fetched_at.desc()).limit(limit)
        rows = (await session.scalars(q)).all()

    return {
        "jobs": [
            {"id": str(j.id), "title": j.title, "platform": j.platform, "url": j.url}
            for j in rows
        ]
    }


async def _score_job(user_id: uuid.UUID, args: dict) -> dict:
    from app.db.session import system_session
    from app.services.scoring import score_job

    job_id = uuid.UUID(args["job_id"])
    async with system_session() as session:
        s = await score_job(user_id, job_id, session)

    return {
        "score": s.score,
        "confidence": float(s.confidence),
        "dimensions": s.dimensions,
        "profile_version": s.profile_version,
    }


async def _draft_proposal(user_id: uuid.UUID, args: dict) -> dict:
    from app.agents.graph import graph as agent_graph
    from app.db.models.job import Job
    from app.db.models.score import Score
    from app.db.models.user import Profile
    from app.db.session import tenant_session
    from app.services.credits import check_and_reserve_credit, get_credit_status, release_credit
    from sqlalchemy import select

    job_id = uuid.UUID(args["job_id"])
    async with tenant_session(str(user_id)) as session:
        job = await session.get(Job, job_id)
        if not job:
            return {"error": "Job not found"}
        profile = await session.get(Profile, user_id)
        if not profile:
            return {"error": "Profile required"}

        await check_and_reserve_credit(user_id, session)

        profile_summary = f"Skills: {', '.join(profile.skills or [])}. Experience: {profile.experience_level}."
        job_summary = f"Title: {job.title}. {job.description[:1000]}."

        score_row = await session.scalar(
            select(Score)
            .where(Score.user_id == user_id, Score.job_id == job_id)
            .order_by(Score.created_at.desc()).limit(1)
        )

        try:
            result = await agent_graph.ainvoke({
                "user_id": str(user_id), "job_id": str(job_id),
                "profile_summary": profile_summary, "job_summary": job_summary,
                "score": score_row.score if score_row else None,
                "voice_chunks": [], "draft": None, "voice_matched": False, "error": None,
            })
        except Exception as exc:
            await release_credit(user_id, session)
            return {"error": str(exc)}

        if result.get("error") or not result.get("draft"):
            await release_credit(user_id, session)
            return {"error": "Draft failed"}

        from app.db.models.proposal import Proposal
        p = Proposal(
            user_id=user_id, job_id=job_id,
            content=result["draft"], voice_matched=result.get("voice_matched", False),
        )
        session.add(p)
        await session.flush()
        credits = await get_credit_status(user_id, session)

        return {
            "proposal_id": str(p.id),
            "content": p.content,
            "voice_matched": p.voice_matched,
            "credits_remaining": credits["drafts_remaining"],
        }


async def _list_proposals(user_id: uuid.UUID) -> dict:
    from sqlalchemy import select

    from app.db.models.proposal import Proposal
    from app.db.session import tenant_session

    async with tenant_session(str(user_id)) as session:
        rows = (await session.scalars(
            select(Proposal).where(Proposal.user_id == user_id)
            .order_by(Proposal.created_at.desc()).limit(50)
        )).all()

    return {
        "proposals": [
            {"id": str(p.id), "job_id": str(p.job_id), "status": p.status, "outcome": p.outcome}
            for p in rows
        ]
    }


async def _set_outcome(user_id: uuid.UUID, args: dict) -> dict:
    from app.db.models.proposal import Proposal
    from app.db.session import tenant_session

    proposal_id = uuid.UUID(args["proposal_id"])
    outcome = args["outcome"]

    async with tenant_session(str(user_id)) as session:
        p = await session.get(Proposal, proposal_id)
        if not p or p.user_id != user_id:
            return {"error": "Proposal not found"}
        p.outcome = outcome
        await session.flush()

    return {"proposal_id": str(p.id), "outcome": p.outcome}


async def run():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="gigpilot",
                server_version="0.1.0",
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
