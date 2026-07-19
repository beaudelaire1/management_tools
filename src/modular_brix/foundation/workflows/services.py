from django.db import transaction

from .models import ApprovalDecision, WorkflowDefinition, WorkflowInstance, WorkflowState, WorkflowTransition


@transaction.atomic
def create_workflow_definition(*, organization_id: str, code: str) -> WorkflowDefinition:
    definition = WorkflowDefinition.objects.create(
        organization_id=organization_id,
        code=code,
        version=1,
        is_active=True,
    )
    return definition


@transaction.atomic
def create_workflow_state(
    *,
    definition_id: str,
    code: str,
    label: str,
    is_initial: bool = False,
    is_terminal: bool = False,
) -> WorkflowState:
    if WorkflowInstance.objects.filter(definition_id=definition_id).exists():
        raise ValueError("A definition with running instances cannot be modified; create a new version.")
    if is_initial:
        WorkflowState.objects.filter(definition_id=definition_id, is_initial=True).update(is_initial=False)
    return WorkflowState.objects.create(
        definition_id=definition_id,
        code=code,
        label=label,
        is_initial=is_initial,
        is_terminal=is_terminal,
    )


@transaction.atomic
def create_workflow_transition(
    *,
    definition_id: str,
    code: str,
    source_state_id: str,
    target_state_id: str,
    require_separate_approver: bool = False,
) -> WorkflowTransition:
    if WorkflowInstance.objects.filter(definition_id=definition_id).exists():
        raise ValueError("A definition with running instances cannot be modified; create a new version.")
    source_state = WorkflowState.objects.get(id=source_state_id, definition_id=definition_id)
    target_state = WorkflowState.objects.get(id=target_state_id, definition_id=definition_id)
    return WorkflowTransition.objects.create(
        definition_id=definition_id,
        code=code,
        source_state=source_state,
        target_state=target_state,
        require_separate_approver=require_separate_approver,
    )


@transaction.atomic
def start_workflow_instance(
    *,
    organization_id: str,
    definition_id: str,
    object_type: str,
    object_id: str,
    requester_user_id: int | None,
) -> WorkflowInstance:
    definition = WorkflowDefinition.objects.get(id=definition_id, is_active=True)
    if str(definition.organization_id) != str(organization_id):
        raise ValueError("A workflow instance and its definition must belong to the same organization.")
    initial_state = WorkflowState.objects.get(definition=definition, is_initial=True)
    return WorkflowInstance.objects.create(
        organization_id=organization_id,
        definition=definition,
        current_state=initial_state,
        object_type=object_type,
        object_id=object_id,
        requester_user_id=requester_user_id,
    )


@transaction.atomic
def apply_transition(
    *,
    instance_id: str,
    transition_code: str,
    actor_user_id: int | None,
    idempotency_key: str,
    comment: str = "",
) -> ApprovalDecision:
    instance = WorkflowInstance.objects.select_for_update().select_related("current_state").get(id=instance_id)

    existing = ApprovalDecision.objects.filter(
        instance=instance,
        idempotency_key=idempotency_key,
    ).first()
    if existing is not None:
        return existing

    transition = WorkflowTransition.objects.get(
        definition=instance.definition,
        code=transition_code,
    )
    if transition.source_state_id != instance.current_state_id:
        raise ValueError("Illegal transition from current state")

    if transition.require_separate_approver and actor_user_id is not None and actor_user_id == instance.requester_user_id:
        raise ValueError("Requester cannot approve this transition")

    instance.current_state = transition.target_state
    instance.save(update_fields=["current_state", "updated_at"])

    return ApprovalDecision.objects.create(
        instance=instance,
        transition=transition,
        actor_user_id=actor_user_id,
        decision="approved",
        comment=comment,
        idempotency_key=idempotency_key,
    )
