"""Generate the synthetic example response with production scoring logic."""

from __future__ import annotations

from app.models.resume_analysis import (
    AnalysisMatchType,
    CriterionAnalysis,
    EducationMetadata,
    EvidenceSourceType,
    ResumeAnalysis,
    ResumeEvidence,
)
from app.models.resume_match_result import ResumeMatchResult
from app.services.job_definition import load_job_definition
from app.services.scoring import score_resume_analysis

def _matched_criterion(
    criterion_id: str,
    match_type: AnalysisMatchType,
    evidence_level: int,
    evidence_text: str,
    rationale: str,
    *,
    source_type: EvidenceSourceType = EvidenceSourceType.PROJECT,
) -> CriterionAnalysis:
    return CriterionAnalysis(
        criterion_id=criterion_id,
        match_type=match_type,
        evidence_level=evidence_level,
        evidence=[
            ResumeEvidence(
                text=evidence_text,
                page=1,
                source_type=source_type,
            )
        ],
        rationale=rationale,
    )


def build_example_result() -> ResumeMatchResult:
    """Build a stable example without Gemini, network access, or copied weights."""

    job = load_job_definition()
    matched = {
        "education.academic_relevance": _matched_criterion(
            "education.academic_relevance",
            AnalysisMatchType.DIRECT,
            3,
            "Bachelor of Science in Computer Science with NLP coursework",
            rationale="เรซูเม่ตัวอย่างระบุวุฒิวิทยาศาสตรบัณฑิตด้านวิทยาการคอมพิวเตอร์และรายวิชา NLP จึงเป็นพื้นฐานการศึกษาที่เกี่ยวข้องโดยตรงกับตำแหน่ง",
            source_type=EvidenceSourceType.EDUCATION,
        ),
        "skills.python": _matched_criterion(
            "skills.python",
            AnalysisMatchType.DIRECT,
            4,
            "Owned a Python FastAPI backend supporting three business workflows, including request validation, external API integrations, monitoring, and production incident fixes",
            rationale="ผู้สมัครมีประสบการณ์รับผิดชอบ Backend ด้วย Python และ FastAPI สำหรับหลาย Workflow รวมถึง Validation, Integration และการดูแลระบบ จึงมีหลักฐานเชิงปฏิบัติที่ชัดเจนสำหรับทักษะ Python",
        ),
        "skills.prompt_engineering": _matched_criterion(
            "skills.prompt_engineering",
            AnalysisMatchType.DIRECT,
            3,
            "Designed structured prompts for an LLM application",
            rationale="ผู้สมัครมีประสบการณ์ออกแบบ Structured Prompt สำหรับระบบ LLM และนำไปใช้กับงานจริง จึงตรงกับทักษะ Prompt Engineering โดยตรง",
        ),
        "skills.context_engineering": _matched_criterion(
            "skills.context_engineering",
            AnalysisMatchType.DIRECT,
            3,
            "Implemented RAG with retrieved context from an internal knowledge base",
            rationale="ผู้สมัครเคยพัฒนา RAG และจัดการ Context จากฐานความรู้ภายใน ซึ่งเป็นประสบการณ์ที่เกี่ยวข้องโดยตรงกับ Context Engineering",
        ),
        "skills.ai_system_workflow_design": _matched_criterion(
            "skills.ai_system_workflow_design",
            AnalysisMatchType.DIRECT,
            3,
            "Designed an LLM workflow from API input to grounded JSON output",
            rationale="ผู้สมัครออกแบบลำดับการทำงานของระบบ LLM ตั้งแต่รับข้อมูลผ่าน API จนสร้างผลลัพธ์ JSON ที่อ้างอิงข้อมูล จึงตรงกับการออกแบบ AI System Workflow",
        ),
        "skills.analytical_problem_solving": _matched_criterion(
            "skills.analytical_problem_solving",
            AnalysisMatchType.DIRECT,
            2,
            "Diagnosed retrieval failures and corrected document chunking",
            rationale="ผู้สมัครวิเคราะห์สาเหตุของปัญหาการค้นคืนข้อมูลและแก้ไขการแบ่งเอกสาร แสดงถึงการแก้ปัญหาอย่างเป็นขั้นตอนจากหลักฐานการทำงานจริง",
        ),
        "skills.requirement_collaboration": _matched_criterion(
            "skills.requirement_collaboration",
            AnalysisMatchType.DIRECT,
            3,
            "Gathered requirements from users and collaborated with backend engineers",
            rationale="ผู้สมัครรวบรวมความต้องการจากผู้ใช้และทำงานร่วมกับวิศวกร Backend จึงมีหลักฐานโดยตรงด้านการทำความเข้าใจ Requirement และการทำงานร่วมกัน",
        ),
        "skills.testing_evaluation": _matched_criterion(
            "skills.testing_evaluation",
            AnalysisMatchType.DIRECT,
            3,
            "Created automated tests and evaluated LLM responses against test cases",
            rationale="ผู้สมัครสร้าง Automated Test และประเมินคำตอบของ LLM เทียบกับ Test Case จึงมีประสบการณ์ตรงด้าน Testing และ Evaluation",
        ),
        "knowledge.llm_generative_ai": _matched_criterion(
            "knowledge.llm_generative_ai",
            AnalysisMatchType.DIRECT,
            3,
            "Built an LLM application with grounded responses",
            rationale="ผู้สมัครพัฒนาแอปพลิเคชัน LLM ที่สร้างคำตอบโดยอ้างอิงข้อมูล จึงมีหลักฐานเชิงปฏิบัติโดยตรงด้าน LLM และ Generative AI",
        ),
        "knowledge.nlp": _matched_criterion(
            "knowledge.nlp",
            AnalysisMatchType.DIRECT,
            2,
            "Completed NLP coursework covering text classification",
            rationale="ผู้สมัครเรียนรายวิชา NLP ที่ครอบคลุมการจำแนกข้อความ จึงมีหลักฐานพื้นฐานโดยตรงด้าน Natural Language Processing",
            source_type=EvidenceSourceType.COURSEWORK,
        ),
        "tools.api": _matched_criterion(
            "tools.api",
            AnalysisMatchType.DIRECT,
            4,
            "Owned a Python FastAPI backend supporting three business workflows, including request validation, external API integrations, monitoring, and production incident fixes",
            rationale="ผู้สมัครรับผิดชอบ FastAPI Backend ที่รองรับหลาย Workflow และเชื่อมต่อ External API พร้อมดูแล Validation และการทำงานจริง จึงมีประสบการณ์ API โดยตรงอย่างชัดเจน",
        ),
        "tools.json_structured_data": _matched_criterion(
            "tools.json_structured_data",
            AnalysisMatchType.DIRECT,
            3,
            "Validated JSON request and response payloads",
            rationale="ผู้สมัครตรวจสอบความถูกต้องของ JSON ทั้ง Request และ Response จึงมีประสบการณ์ตรงในการจัดการ Structured Data ภายในระบบ",
        ),
        "tools.automation_pipeline": _matched_criterion(
            "tools.automation_pipeline",
            AnalysisMatchType.DIRECT,
            3,
            "Built Make.com automation workflows for CRM synchronization",
            rationale="ผู้สมัครสร้าง Workflow บน Make.com เพื่อซิงโครไนซ์ข้อมูล CRM จึงมีหลักฐานโดยตรงด้าน Automation Pipeline และการเชื่อมต่อระบบ",
        ),
        "tools.n8n": _matched_criterion(
            "tools.n8n",
            AnalysisMatchType.TRANSFERABLE,
            4,
            "Owned five Make.com automation workflows integrating CRM, support, and notification services, reducing manual data-entry steps",
            rationale="ผู้สมัครไม่มีหลักฐานการใช้ n8n โดยตรง แต่มีประสบการณ์รับผิดชอบ Workflow Automation หลายชุดด้วย Make.com ซึ่งเป็นทักษะที่สามารถถ่ายโอนไปใช้กับ n8n ได้",
        ),
        "tools.sql": _matched_criterion(
            "tools.sql",
            AnalysisMatchType.EQUIVALENT,
            4,
            "Designed PostgreSQL schemas, wrote multi-table joins, added indexes, and optimized queries for application and reporting workloads",
            rationale="ผู้สมัครมีประสบการณ์ใช้ PostgreSQL ทั้งการออกแบบ Schema, เขียน Join, สร้าง Index และปรับประสิทธิภาพ Query จึงถือเป็นหลักฐานที่เทียบเท่ากับทักษะ SQL",
        ),
        "tools.docker": _matched_criterion(
            "tools.docker",
            AnalysisMatchType.ADJACENT,
            4,
            "Owned Kubernetes deployments across multiple services, configuring health checks, rollouts, autoscaling, and production incident recovery",
            rationale="ผู้สมัครมีประสบการณ์ดูแลระบบบน Kubernetes หลายบริการ ซึ่งเกี่ยวข้องกับเทคโนโลยี Container แต่ยังไม่ใช่หลักฐานการใช้งาน Docker โดยตรง จึงจัดเป็นทักษะที่ใกล้เคียง",
        ),
    }
    no_evidence_rationales = {
        "knowledge.machine_learning": (
            "ไม่พบหลักฐานเกี่ยวกับ Machine Learning ที่เพียงพอในเรซูเม่ตัวอย่างนี้"
        ),
        "tools.cloud": (
            "ไม่พบหลักฐานการใช้งาน Cloud Platform ที่เพียงพอในเรซูเม่ตัวอย่างนี้"
        ),
    }
    analysis = ResumeAnalysis(
        education=EducationMetadata(
            degree="Bachelor of Science",
            field_or_major="Computer Science",
            university="Synthetic University",
            coursework=["Natural Language Processing"],
        ),
        criteria=[
            matched[criterion.id]
            if criterion.id in matched
            else CriterionAnalysis(
                criterion_id=criterion.id,
                match_type=AnalysisMatchType.NONE,
                evidence_level=0,
                evidence=[],
                rationale=no_evidence_rationales[criterion.id],
            )
            for criterion in job.criteria
        ],
    )
    score = score_resume_analysis(analysis, job)
    return ResumeMatchResult(
        job_id=job.job_id,
        company=job.company,
        job_title=job.title,
        education=analysis.education,
        score_name=score.score_name,
        overall_score=score.overall_score,
        maximum_score=score.maximum_score,
        category_scores=score.category_scores,
        criterion_scores=score.criterion_scores,
    )


def main() -> None:
    """Print JSON suitable for examples/example_result.json."""

    print(build_example_result().model_dump_json(indent=2))


if __name__ == "__main__":
    main()
