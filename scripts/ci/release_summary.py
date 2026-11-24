#!/usr/bin/env python3
"""Write the Release workflow's job summary: the markdown GitHub shows on the run page.

It appends to $GITHUB_STEP_SUMMARY, or prints to the screen when that is unset, so you can preview
it locally. Uses only the standard library, and `deployed` calls the terraform and aws CLIs from
the repository root.

    release_summary.py plan <plan.json> <plan.txt>        header, table of changes, full plan
    release_summary.py image <repository> <tag> <digest>  the image that was pushed
    release_summary.py deployed <plan.json>               what is live after the apply

plan.json is `terraform show -json <plan>` and plan.txt is `terraform show -no-color <plan>`.
"""

import html
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence

# GitHub caps a job summary at 1 MiB; keep the full plan well under that.
MAX_PLAN_BYTES = 200_000

# The kinds of change, in the order the summary lists them. Anything else is shown by its own name.
KINDS = ("create", "update", "replace", "destroy")


def classify(actions: Sequence[str]) -> str | None:
    """Name the kind of change a Terraform plan entry makes.

    Arguments:
    actions -- the entry's `change.actions` list, such as ["create"] or ["delete", "create"].

    Returns:
    "create", "update", "replace" or "destroy"; the action names joined by a space for a
    combination it doesn't know, so a new kind of change is never hidden; or None for entries
    that change nothing (no-op, a data source read, or no actions).
    """
    kinds = sorted(actions)
    if not kinds or kinds in (["no-op"], ["read"]):
        return None
    if kinds == ["create", "delete"]:
        return "replace"
    return {"create": "create", "update": "update", "delete": "destroy"}.get(
        kinds[0] if len(kinds) == 1 else "", " ".join(kinds)
    )


def escape_cell(text: str) -> str:
    """Make text safe to show in a markdown table cell.

    Arguments:
    text -- free text, such as a commit message.

    Returns:
    the text with HTML and markdown characters escaped, so it can't break the table.
    """
    escaped = html.escape(text, quote=False)
    for char in ("\\", "`", "|", "[", "]"):
        escaped = escaped.replace(char, "\\" + char)
    return escaped


def truncate(text: str, max_bytes: int) -> str:
    """Cut text to at most max_bytes bytes (UTF-8), at the end of a line.

    Arguments:
    text -- the text to shorten.
    max_bytes -- the size limit in bytes, which is what GitHub's summary limit counts.

    Returns:
    the text unchanged if it fits, otherwise its first whole lines plus a truncation note.
    """
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    head = text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    return head.rsplit("\n", 1)[0] + "\n... (truncated)"


def fence_for(text: str) -> str:
    """Pick a code fence that the text can't close early.

    Arguments:
    text -- the text that will go inside the fence.

    Returns:
    a run of backticks longer than any run inside the text, and at least three.
    """
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def plan_markdown(
    plan: Mapping, plan_text: str, env: Mapping[str, str], subject: str = ""
) -> str:
    """Render the header, the table of changes and the full plan.

    Arguments:
    plan -- the parsed `terraform show -json` output.
    plan_text -- the human-readable plan, shown in a collapsed section.
    env -- environment variables (GITHUB_SHA, GITHUB_ACTOR, APPLY and so on).
    subject -- first line of the commit message.

    Returns:
    the markdown for the top of the summary.
    """
    sha = env.get("GITHUB_SHA", "")
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    repo = env.get("GITHUB_REPOSITORY", "")
    mode = "Plan and apply" if env.get("APPLY") == "true" else "Plan only"
    commit = f"[`{sha[:7]}`]({server}/{repo}/commit/{sha}) {escape_cell(subject)}"
    lines = [
        "## Release",
        "",
        "| | |",
        "|---|---|",
        f"| Commit | {commit} |",
        f"| Run by | {env.get('GITHUB_ACTOR', 'unknown')} |",
        f"| Mode | {mode} |",
        "",
    ]

    changes = [
        (kind, entry["address"])
        for entry in plan.get("resource_changes", [])
        if (kind := classify(entry["change"]["actions"]))
    ]
    if not changes:
        lines += [
            "> [!NOTE]",
            "> No infrastructure changes. AWS already matches the configuration.",
        ]
        return "\n".join(lines) + "\n"

    present = {kind for kind, _ in changes}
    ordered = [k for k in KINDS if k in present] + sorted(present - set(KINDS))
    counts = [
        f"{sum(1 for k, _ in changes if k == kind)} to {kind}" for kind in ordered
    ]
    lines += [
        f"### Changes ({', '.join(counts)})",
        "",
        "| Change | Resource |",
        "|---|---|",
    ]
    lines += [f"| {kind} | `{address}` |" for kind, address in changes]
    shown = truncate(plan_text, MAX_PLAN_BYTES)
    fence = fence_for(shown)
    lines += [
        "",
        "<details><summary>Full plan</summary>",
        "",
        fence,
        shown,
        fence,
        "",
        "</details>",
    ]
    return "\n".join(lines) + "\n"


def image_markdown(repository: str, tag: str, digest: str) -> str:
    """Render the pushed image.

    Arguments:
    repository -- the ECR repository URL.
    tag -- the image tag (the commit SHA).
    digest -- the pushed image's digest, with or without the repository in front; may be empty.

    Returns:
    the markdown for the "Image" section.
    """
    shown_digest = digest.rsplit("@", maxsplit=1)[-1] or "not available"
    return (
        "\n### Image\n\n| | |\n|---|---|\n"
        f"| Repository | `{repository}` |\n"
        f"| Tag | `{tag}` |\n"
        f"| Digest | `{shown_digest}` |\n"
    )


def deployed_markdown(
    family: str,
    revision: str,
    before: str | None,
    schedule: Mapping[str, str],
    cluster: str,
    region: str,
) -> str:
    """Render what is live after the apply.

    Arguments:
    family -- the task definition family.
    revision -- the task definition revision that is now live.
    before -- the revision the plan replaced, or None if it wasn't replaced.
    schedule -- the live schedule's State, ScheduleExpression and ScheduleExpressionTimezone.
    cluster -- the ECS cluster name.
    region -- the AWS region, for the console link.

    Returns:
    the markdown for the "Deployed" section.
    """
    task_definition = f"`{family}:{revision}`"
    if before and before != revision:
        task_definition += f" (was `:{before}`)"
    state = schedule.get("State", "unknown")
    expression = schedule.get("ScheduleExpression", "unknown")
    # Scheduler leaves the time zone out of its answer when it is UTC.
    zone = schedule.get("ScheduleExpressionTimezone", "UTC")
    link = f"https://{region}.console.aws.amazon.com/ecs/v2/clusters/{cluster}/tasks?region={region}"
    return (
        "\n### Deployed\n\n| | |\n|---|---|\n"
        f"| Task definition | {task_definition} |\n"
        f"| Daily schedule | `{state}`, `{expression}` in {zone} |\n"
        f"| Tasks | [{cluster} in the ECS console]({link}) |\n"
    )


def replaced_revision(plan: Mapping) -> str | None:
    """Find the task definition revision a plan replaced.

    Arguments:
    plan -- the parsed `terraform show -json` output.

    Returns:
    the old revision as text, or None if the plan didn't touch the task definition.
    """
    for entry in plan.get("resource_changes", []):
        before = (entry["change"].get("before") or {}).get("revision")
        if entry["address"] == "aws_ecs_task_definition.job" and before is not None:
            return str(before)
    return None


def run(*command: str) -> str:
    """Run a command and return its output.

    Arguments:
    command -- the program and its arguments.

    Returns:
    the command's standard output, without the trailing newline.

    Raises:
    subprocess.CalledProcessError -- if the command fails.
    """
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def append(text: str, env: Mapping[str, str]) -> None:
    """Add text to the job summary, or print it when there is no summary file.

    Arguments:
    text -- the markdown to add.
    env -- environment variables; GITHUB_STEP_SUMMARY is the summary file.
    """
    path = env.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as summary:
            summary.write(text)
    else:
        sys.stdout.write(text)


def main(argv: Sequence[str], env: Mapping[str, str] = os.environ) -> int:
    """Run one of the summary commands (see the module docstring).

    Arguments:
    argv -- the command and its arguments.
    env -- environment variables.

    Returns:
    the process exit code: 0, or 2 for a usage error.

    Raises:
    subprocess.CalledProcessError -- in `deployed` mode, if the terraform or aws command fails.
    """
    command, args = (argv[0], argv[1:]) if argv else ("", [])
    if command == "plan" and len(args) == 2:
        with (
            open(args[0], encoding="utf-8") as plan_json,
            open(args[1], encoding="utf-8") as plan_text,
        ):
            plan, text = json.load(plan_json), plan_text.read()
        try:
            subject = run("git", "log", "-1", "--format=%s")
        except (OSError, subprocess.CalledProcessError):
            subject = ""
        append(plan_markdown(plan, text, env, subject), env)
    elif command == "image" and len(args) == 3:
        append(image_markdown(*args), env)
    elif command == "deployed" and len(args) == 1:
        with open(args[0], encoding="utf-8") as plan_json:
            plan = json.load(plan_json)
        region = env.get("AWS_REGION", "us-east-2")
        outputs = {
            name: run("terraform", "-chdir=infra", "output", "-raw", name)
            for name in ("task_definition_family", "ecs_cluster_name", "schedule_name")
        }
        revision = run(
            "aws",
            "ecs",
            "describe-task-definition",
            "--region",
            region,
            "--task-definition",
            outputs["task_definition_family"],
            "--query",
            "taskDefinition.revision",
            "--output",
            "text",
        )
        schedule = json.loads(
            run(
                "aws",
                "scheduler",
                "get-schedule",
                "--region",
                region,
                "--name",
                outputs["schedule_name"],
                "--output",
                "json",
            )
        )
        append(
            deployed_markdown(
                outputs["task_definition_family"],
                revision,
                replaced_revision(plan),
                schedule,
                outputs["ecs_cluster_name"],
                region,
            ),
            env,
        )
    else:
        sys.stderr.write(__doc__ or "")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
