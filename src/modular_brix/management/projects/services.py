from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Milestone, Project, ScopeChange, Task, TaskDependency


@transaction.atomic
def add_task(*, project_id: str, name: str, assignee_membership_id: str | None = None, due_date=None) -> Task:
    return Task.objects.create(
        project_id=project_id, name=name, assignee_id=assignee_membership_id, due_date=due_date
    )


def _would_create_cycle(task: Task, depends_on: Task) -> bool:
    """Depth-first walk from the dependency: a path back to the task means a cycle."""
    stack = [depends_on]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current.id == task.id:
            return True
        if str(current.id) in seen:
            continue
        seen.add(str(current.id))
        stack.extend(dependency.depends_on for dependency in current.dependencies.select_related("depends_on"))
    return False


@transaction.atomic
def add_dependency(*, task_id: str, depends_on_id: str) -> TaskDependency:
    """Dependencies form a directed acyclic graph; cycles are rejected (spec G08)."""
    task = Task.objects.get(id=task_id)
    depends_on = Task.objects.get(id=depends_on_id)
    if task.project_id != depends_on.project_id:
        raise ValueError("A task dependency must stay inside the same project.")
    if task.id == depends_on.id:
        raise ValueError("A task cannot depend on itself.")
    if _would_create_cycle(task, depends_on):
        raise ValueError("This dependency would create a cycle.")
    return TaskDependency.objects.create(task=task, depends_on=depends_on)


def blocked_tasks(*, project_id: str) -> list[Task]:
    """Tasks whose dependencies are not all done: the blocking path is visible."""
    return [
        task
        for task in Task.objects.filter(project_id=project_id).exclude(status="done")
        if task.dependencies.exclude(depends_on__status="done").exists()
    ]


def project_progress(*, project_id: str) -> Decimal:
    tasks = Task.objects.filter(project_id=project_id)
    total = tasks.count()
    if total == 0:
        return Decimal("0")
    done = tasks.filter(status="done").count()
    return (Decimal(done) / Decimal(total) * 100).quantize(Decimal("0.1"))


def late_milestones(*, project_id: str) -> list[Milestone]:
    today = timezone.now().date()
    return list(
        Milestone.objects.filter(project_id=project_id, reached_at__isnull=True, due_date__lt=today)
    )


@transaction.atomic
def record_scope_change(*, project_id: str, description: str) -> ScopeChange:
    if not description.strip():
        raise ValueError("A scope change requires a description.")
    return ScopeChange.objects.create(project_id=project_id, description=description.strip())


@transaction.atomic
def create_project(*, organization_id: str, name: str, party_id: str | None = None) -> Project:
    if party_id is not None:
        from modular_brix.management.parties.models import Party

        party = Party.objects.get(id=party_id)
        if str(party.organization_id) != str(organization_id):
            raise ValueError("A project party must belong to the same organization.")
    return Project.objects.create(organization_id=organization_id, name=name, party_id=party_id)
