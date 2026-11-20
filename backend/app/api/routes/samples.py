"""Writing samples CRUD: POST/GET/DELETE /me/samples. Derives: US-A4.
Size/count limits enforced (04_TRD §7.4: <=1MB/sample ~= 20k chars, <=5 samples).
Samples are created under the tenant session for RLS; chunk embedding (P2-3) hooks
into the create path later."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_tenant_db
from app.db.models.sample import SampleChunk, WritingSample
from app.schemas.samples import MAX_SAMPLES_PER_USER, SampleCreate, SampleOut

router = APIRouter(prefix="/me/samples", tags=["samples"])


@router.get("", response_model=list[SampleOut])
async def list_samples(
    db: AsyncSession = Depends(get_tenant_db),
) -> list[SampleOut]:
    rows = (
        await db.scalars(
            select(WritingSample).order_by(WritingSample.created_at.desc())
        )
    ).all()
    return [
        SampleOut(
            id=s.id,
            user_id=s.user_id,
            source_type=s.source_type,
            content=s.content,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.post("", response_model=SampleOut, status_code=status.HTTP_201_CREATED)
async def create_sample(
    payload: SampleCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_tenant_db),
) -> SampleOut:
    count = await db.scalar(
        select(func.count()).select_from(WritingSample)
    )
    if (count or 0) >= MAX_SAMPLES_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum {MAX_SAMPLES_PER_USER} samples allowed. Delete one first.",
        )

    sample = WritingSample(
        user_id=user_id,
        source_type=payload.source_type,
        content=payload.content,
    )
    db.add(sample)
    await db.flush()

    return SampleOut(
        id=sample.id,
        user_id=sample.user_id,
        source_type=sample.source_type,
        content=sample.content,
        created_at=sample.created_at,
    )


@router.delete("/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample(
    sample_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    sample = await db.get(WritingSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    await db.execute(
        delete(SampleChunk).where(SampleChunk.sample_id == sample_id)
    )
    await db.delete(sample)
