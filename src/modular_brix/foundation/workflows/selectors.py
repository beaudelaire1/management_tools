from django.db.models import QuerySet

from .models import WorkflowInstance


def list_workflow_instances_for_object(*, organization_id: str, object_type: str, object_id: str) -> QuerySet[WorkflowInstance]:
    return WorkflowInstance.objects.filter(
        organization_id=organization_id,
        object_type=object_type,
        object_id=object_id,
    )
