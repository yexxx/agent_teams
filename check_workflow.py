import json

workflow_status = {
    "workflow_id": "25c57950-8f99-4d4a-906c-0b5f27da501c",
    "stage": "spec",
    "status": "in_progress",
    "tasks": {
        "spec": "task_70159fceddde",
        "design": "task_a614987fb579",
        "code": "task_2bab526846d2",
        "verify": "task_aefa3802d718",
        "integration": "task_1be0feffc7e8"
    },
    "created_at": "2026-02-27T13:21:03Z",
    "updated_at": "2026-02-27T13:42:30Z",
    "subagents": {
        "spec_builder": "9a0965d2-f911-4e91-be2e-f569176e698c",
        "design_builder": "f17bb96d-280a-4f0c-a2fc-69302a88357e",
        "coder": "2072b350-f9df-4549-9ac4-70ee5e2becb7",
        "verify": "04550e8f-ac34-4353-856a-8bd79032edb0"
    }
}

print(json.dumps(workflow_status, indent=2))