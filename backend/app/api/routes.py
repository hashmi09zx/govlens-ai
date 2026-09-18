import uuid
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import JobModel, RecruitmentModel, SourceModel, FactModel, ConflictModel, ReportModel, UserRequestModel
from app.schemas.api_schemas import (
    ResearchRequest,
    ResearchResponse,
    ResolveRecruitmentRequest,
    RequestChangeInput,
    JobStatusResponse,
    ReportResponse,
    ReportVersionItem,
)
from app.graph.research_graph import research_graph
from app.pdf.generator import generate_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter()


def run_research_background_task(job_id: str, user_query: str, user_profile: Optional[dict]):
    """Background task running the full research graph."""
    db = next(get_db())
    try:
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return

        job.status = "running"
        job.current_step = "query_agent"
        db.commit()

        initial_state = {
            "user_query": user_query,
            "user_profile": user_profile,
            "recruitment": None,
            "candidates": None,
            "official_sources": [],
            "secondary_sources": [],
            "extracted_facts": [],
            "conflicts": [],
            "verified_facts": [],
            "report": {},
            "user_requests": [],
            "affected_sections": [],
            "research_status": {"query_agent": "running"},
            "confidence": {},
            "selected_candidate_id": None,
            "field_retry_counts": {},
        }

        # Execute graph thread with checkpointing
        config = {"configurable": {"thread_id": job_id}}
        final_state = research_graph.invoke(initial_state, config=config)

        res_status = final_state.get("research_status", {})
        recruitment = final_state.get("recruitment")

        if res_status.get("recruitment_id") == "ambiguous":
            job.status = "ambiguous"
            job.current_step = "recruitment_id_agent"
            job.candidates_json = json.dumps(final_state.get("candidates", []))
            db.commit()
            return

        # Save resolved recruitment
        if recruitment:
            rec_id = recruitment.get("id", job_id)
            job.recruitment_id = rec_id
            db_rec = db.query(RecruitmentModel).filter(RecruitmentModel.id == rec_id).first()
            if not db_rec:
                db_rec = RecruitmentModel(
                    id=rec_id,
                    name=recruitment.get("name", user_query),
                    org=recruitment.get("org", "Official Board"),
                    year=recruitment.get("year", "2026"),
                    advt_number=recruitment.get("advt_number", "01/2026"),
                    post=recruitment.get("post"),
                )
                db.add(db_rec)
                db.commit()

        # Save initial Report v1.0
        report_dict = final_state.get("report", {})
        if report_dict:
            rec_id = job.recruitment_id or job_id
            db_report = ReportModel(
                id=str(uuid.uuid4()),
                recruitment_id=rec_id,
                version="1.0",
                changed_sections_json=json.dumps([]),
                sections_json=json.dumps(report_dict),
            )
            db.add(db_report)

        job.status = "completed"
        job.current_step = "completed"
        db.commit()

    except Exception as e:
        logger.error(f"Error in research background task for job {job_id}: {e}")
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/research", response_model=ResearchResponse)
def start_research(request: ResearchRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    profile_dict = request.user_profile.model_dump() if request.user_profile else None

    new_job = JobModel(
        id=job_id,
        status="pending",
        current_step="initialized",
    )
    db.add(new_job)
    db.commit()

    background_tasks.add_task(run_research_background_task, job_id, request.user_query, profile_dict)

    return ResearchResponse(
        job_id=job_id,
        status="pending",
        message="Research job initiated successfully.",
    )


@router.get("/research/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidates = None
    if job.candidates_json:
        try:
            candidates = json.loads(job.candidates_json)
        except Exception:
            candidates = []

    config = {"configurable": {"thread_id": job_id}}
    res_status = {}
    try:
        checkpoint_state = research_graph.get_state(config)
        if checkpoint_state and checkpoint_state.values:
            res_status = checkpoint_state.values.get("research_status", {})
    except Exception:
        pass

    return JobStatusResponse(
        job_id=job.id,
        recruitment_id=job.recruitment_id,
        status=job.status,
        current_step=job.current_step,
        research_status=res_status,
        candidates=candidates,
        error=job.error,
    )


@router.post("/research/{job_id}/resolve-recruitment")
def resolve_recruitment(job_id: str, payload: ResolveRecruitmentRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "ambiguous":
        raise HTTPException(status_code=400, detail="Job is not in ambiguous state")

    # Update job state immediately so UI polling moves from ambiguous -> running
    job.status = "running"
    job.current_step = "source_agent"
    db.commit()

    def resume_graph_task():
        db_inner = next(get_db())
        try:
            config = {"configurable": {"thread_id": job_id}}
            checkpoint = research_graph.get_state(config)
            current_state = checkpoint.values if checkpoint else {}

            updated_state = {
                **current_state,
                "selected_candidate_id": payload.selected_candidate_id,
                "research_status": {**current_state.get("research_status", {}), "recruitment_id": "resolved"},
            }

            final_state = research_graph.invoke(updated_state, config=config)

            job_rec = db_inner.query(JobModel).filter(JobModel.id == job_id).first()
            if job_rec:
                job_rec.status = "completed"
                job_rec.current_step = "completed"

                # Save initial report v1.0
                report_dict = final_state.get("report", {})
                rec_id = job_rec.recruitment_id or job_id
                db_report = ReportModel(
                    id=str(uuid.uuid4()),
                    recruitment_id=rec_id,
                    version="1.0",
                    changed_sections_json=json.dumps([]),
                    sections_json=json.dumps(report_dict),
                )
                db_inner.add(db_report)
                db_inner.commit()
        except Exception as e:
            logger.error(f"Error resuming graph for job {job_id}: {e}")
            job_rec = db_inner.query(JobModel).filter(JobModel.id == job_id).first()
            if job_rec:
                job_rec.status = "failed"
                job_rec.error = str(e)
                db_inner.commit()
        finally:
            db_inner.close()

    background_tasks.add_task(resume_graph_task)
    return {"message": "Recruitment selection accepted, research resumed."}


@router.get("/research/{job_id}/report", response_model=ReportResponse)
def get_report(job_id: str, version: Optional[str] = None, db: Session = Depends(get_db)):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    rec_id = job.recruitment_id or job_id
    query = db.query(ReportModel).filter(ReportModel.recruitment_id == rec_id)

    if version:
        report = query.filter(ReportModel.version == version).first()
    else:
        report = query.order_by(ReportModel.created_at.desc()).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not generated yet")

    return ReportResponse(
        id=report.id,
        recruitment_id=report.recruitment_id,
        version=report.version,
        sections=json.loads(report.sections_json),
        changed_sections=json.loads(report.changed_sections_json),
        created_at=report.created_at.isoformat(),
    )


@router.get("/research/{job_id}/report/versions", response_model=List[ReportVersionItem])
def get_report_versions(job_id: str, db: Session = Depends(get_db)):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    rec_id = job.recruitment_id or job_id
    reports = db.query(ReportModel).filter(ReportModel.recruitment_id == rec_id).order_by(ReportModel.created_at.desc()).all()

    return [
        ReportVersionItem(
            id=r.id,
            version=r.version,
            changed_sections=json.loads(r.changed_sections_json),
            source_request_id=r.source_request_id,
            created_at=r.created_at.isoformat(),
        )
        for r in reports
    ]


@router.post("/research/{job_id}/request-change")
def request_change(job_id: str, payload: RequestChangeInput, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    request_id = str(uuid.uuid4())
    rec_id = job.recruitment_id or job_id

    user_req = UserRequestModel(
        id=request_id,
        recruitment_id=rec_id,
        request_text=payload.request_text,
        affected_sections_json=json.dumps(payload.target_sections or []),
    )
    db.add(user_req)
    db.commit()

    # Background task for HITL partial graph execution & immutable report versioning
    def run_hitl_task():
        db_inner = next(get_db())
        try:
            config = {"configurable": {"thread_id": job_id}}
            checkpoint = research_graph.get_state(config)
            current_state = checkpoint.values if checkpoint else {}

            user_reqs = list(current_state.get("user_requests", []))
            user_reqs.append({"id": request_id, "request_text": payload.request_text})

            updated_state = {
                **current_state,
                "user_requests": user_reqs,
            }

            # Resume graph at request_agent node
            final_state = research_graph.invoke(updated_state, config=config)
            affected_sections = final_state.get("affected_sections", [])
            new_report_dict = final_state.get("report", {})

            # Calculate version number (e.g. 1.0 -> 1.1)
            existing_reports = db_inner.query(ReportModel).filter(ReportModel.recruitment_id == rec_id).all()
            new_version = f"1.{len(existing_reports)}"

            db_new_report = ReportModel(
                id=str(uuid.uuid4()),
                recruitment_id=rec_id,
                version=new_version,
                changed_sections_json=json.dumps(affected_sections),
                source_request_id=request_id,
                sections_json=json.dumps(new_report_dict),
            )
            db_inner.add(db_new_report)
            db_inner.commit()

        except Exception as e:
            logger.error(f"Error executing HITL request for job {job_id}: {e}")
        finally:
            db_inner.close()

    background_tasks.add_task(run_hitl_task)
    return {"message": "Change request submitted successfully.", "request_id": request_id}


@router.get("/research/{job_id}/sources")
def get_sources(job_id: str, db: Session = Depends(get_db)):
    config = {"configurable": {"thread_id": job_id}}
    try:
        checkpoint_state = research_graph.get_state(config)
        if checkpoint_state and checkpoint_state.values:
            val = checkpoint_state.values
            return {
                "official_sources": val.get("official_sources", []),
                "secondary_sources": val.get("secondary_sources", []),
            }
    except Exception:
        pass
    return {"official_sources": [], "secondary_sources": []}


@router.get("/research/{job_id}/conflicts")
def get_conflicts(job_id: str, db: Session = Depends(get_db)):
    config = {"configurable": {"thread_id": job_id}}
    try:
        checkpoint_state = research_graph.get_state(config)
        if checkpoint_state and checkpoint_state.values:
            return {"conflicts": checkpoint_state.values.get("conflicts", [])}
    except Exception:
        pass
    return {"conflicts": []}


@router.get("/research/{job_id}/pdf")
def download_pdf(job_id: str, version: Optional[str] = None, db: Session = Depends(get_db)):
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    rec_id = job.recruitment_id or job_id
    query = db.query(ReportModel).filter(ReportModel.recruitment_id == rec_id)

    if version:
        report = query.filter(ReportModel.version == version).first()
    else:
        report = query.order_by(ReportModel.created_at.desc()).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not generated yet")

    sections_dict = json.loads(report.sections_json)
    rec_info = {"name": job.id, "org": "Government Board", "advt_number": "Official"}

    pdf_bytes = generate_pdf_report(sections_dict, rec_info, version=report.version)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="exam_research_report_v{report.version}.pdf"'},
    )
