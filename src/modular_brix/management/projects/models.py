import uuid

from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="projects"
    )
    party = models.ForeignKey(
        "management_parties.Party", null=True, blank=True, on_delete=models.PROTECT, related_name="projects"
    )
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="open")  # open | on_hold | closed
    created_at = models.DateTimeField(auto_now_add=True)


class Milestone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=255)
    due_date = models.DateField()
    reached_at = models.DateField(null=True, blank=True)


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="todo")  # todo | doing | done
    assignee = models.ForeignKey(
        "foundation_accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="tasks"
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TaskDependency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="dependencies")
    depends_on = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="dependents")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "depends_on"], name="uq_task_dependency"),
            models.CheckConstraint(
                condition=~models.Q(task=models.F("depends_on")), name="ck_task_no_self_dependency"
            ),
        ]


class ScopeChange(models.Model):
    """History of project scope changes (spec G08: historique des changements de périmètre)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="scope_changes")
    description = models.CharField(max_length=500)
    changed_at = models.DateTimeField(auto_now_add=True)
