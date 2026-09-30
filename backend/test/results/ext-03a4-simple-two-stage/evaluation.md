# EXT-03A.4 Simple Two-Stage CV Capability Experiment

{
  "milestone": "EXT-03A.4",
  "generated_at": "2026-09-08T10:03:24.585192+00:00",
  "fixture": {
    "fixture_name": "cv-nguyen-vu-minh-thien",
    "document_id": "40584171-3e68-4e6e-8497-089f830797fc",
    "storage_key": "documents/40584171-3e68-4e6e-8497-089f830797fc/faaf0ed7d35c311732f79f33994e156c",
    "filename": "cv-nguyen-vu-minh-thien.pdf",
    "mime_type": "application/pdf",
    "file_size": 186051,
    "sha256": "ff28e6315ae1f698e8277b6b572e2dcf8389eb70671a03c472f50a7b3c354ffa",
    "page_count": 3,
    "input_mode": "native_pdf",
    "reference_sha256": "ff28e6315ae1f698e8277b6b572e2dcf8389eb70671a03c472f50a7b3c354ffa"
  },
  "configuration": {
    "provider": "gemini",
    "model": "gemini-3.5-flash-lite",
    "thinking": "medium",
    "input_mode": "native_pdf",
    "provider_calls": 2
  },
  "stage1": {
    "experience_count": 17,
    "experience_recall": 1.0,
    "education_count": 2,
    "education_recall": 1.0,
    "statement_count": 35,
    "invalid_statement_refs": 0,
    "statement_grounding_rate": 1.0,
    "passed": true
  },
  "stage2": {
    "capability_count": 4,
    "capability_names": [
      "Distribution Management System Development",
      "Omni Channel Platform Development",
      "E-commerce and Delivery Project Development",
      "Mobile Payment Platform Development"
    ],
    "capability_family_coverage": {
      "Project Management": "FOUND",
      "Product Management": "NOT_FOUND",
      "eCommerce": "FOUND",
      "Omnichannel Commerce": "FOUND",
      "Order Management": "NOT_FOUND",
      "Warehouse Management": "NOT_FOUND",
      "Delivery / Logistics Management": "FOUND",
      "Operations Planning": "NOT_FOUND",
      "Digital Platform Development": "FOUND",
      "Team Leadership": "NOT_FOUND",
      "Process Optimization": "NOT_FOUND"
    },
    "capability_family_recall": 0.45454545454545453,
    "grounding_rate": 1.0,
    "unsupported_count": 0,
    "dangling_ref_count": 0,
    "duplicate_count": 0,
    "latency_ms": 4201
  },
  "candidate_profile_created": true,
  "decision": {
    "status": "TWO_STAGE_PARTIALLY_SUPPORTED",
    "gates": {
      "capability_family": false,
      "grounding": true,
      "unsupported": true,
      "dangling": true,
      "experience": true,
      "education": true
    },
    "next_action": "INVESTIGATE_CAPABILITY_TASK_FORMULATION_OR_ONTOLOGY"
  }
}
