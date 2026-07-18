from .models import WorkflowInstance


def can_access_workflow_instance(*, actor_organization_id: str, instance: WorkflowInstance) -> bool:
    return str(instance.organization_id) == str(actor_organization_id)
