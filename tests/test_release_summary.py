import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "ci" / "release_summary.py"
spec = importlib.util.spec_from_file_location("release_summary", SCRIPT)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

ENV = {
    "GITHUB_SHA": "decaa995a9078ff49c36d2b7802deda2c39af806",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_REPOSITORY": "owner/repo",
    "GITHUB_ACTOR": "mike",
}
SCHEDULE = {
    "State": "ENABLED",
    "ScheduleExpression": "cron(0 5 * * ? *)",
    "ScheduleExpressionTimezone": "America/Los_Angeles",
}
TASK_DEFINITION = "aws_ecs_task_definition.job"


def entry(address, actions, before=None):
    return {"address": address, "change": {"actions": actions, "before": before}}


def no_git(*command):
    raise FileNotFoundError("git")


# --- helpers ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("actions", "expected"),
    [
        (["create"], "create"),
        (["update"], "update"),
        (["delete"], "destroy"),
        (["delete", "create"], "replace"),
        (["create", "delete"], "replace"),
        (["forget"], "forget"),
        (["delete", "update"], "delete update"),
        (["no-op"], None),
        (["read"], None),
        ([], None),
    ],
)
def test_classify(actions, expected):
    assert rs.classify(actions) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("plain", "plain"),
        (
            "Handle `<details>` | a [b] \\ c",
            "Handle \\`&lt;details&gt;\\` \\| a \\[b\\] \\\\ c",
        ),
    ],
)
def test_escape_cell(text, expected):
    assert rs.escape_cell(text) == expected


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("short", 100, "short"),
        ("aaa\nbbb\nccc", 9, "aaa\nbbb\n... (truncated)"),  # cut at a line end
        ("é" * 10, 10, "ééééé\n... (truncated)"),  # bytes, not characters
    ],
)
def test_truncate(text, limit, expected):
    assert rs.truncate(text, limit) == expected


@pytest.mark.parametrize(
    ("text", "fence"),
    [("plain", "```"), ("a ``` b", "````"), ("x `````` y", "```````")],
)
def test_fence_for(text, fence):
    assert rs.fence_for(text) == fence


# --- markdown sections -----------------------------------------------------


def test_plan_without_changes_says_so():
    plan = {"resource_changes": [entry("a.b", ["no-op"]), entry("data.c.d", ["read"])]}

    text = rs.plan_markdown(plan, "No changes.", ENV, "Add a thing")

    assert "No infrastructure changes" in text
    assert "Full plan" not in text
    assert "[`decaa99`](https://github.com/owner/repo/commit/decaa995" in text
    assert "| Run by | mike |" in text
    assert "| Mode | Plan only |" in text


def test_plan_lists_each_change_and_counts_them():
    plan = {
        "resource_changes": [
            entry("aws_s3_bucket.new", ["create"]),
            entry(TASK_DEFINITION, ["delete", "create"]),
            entry("aws_iam_role.old", ["delete"]),
            entry(
                "aws_x.future", ["forget"]
            ),  # an unfamiliar action is shown, not hidden
            entry("aws_x.same", ["no-op"]),
        ]
    }

    text = rs.plan_markdown(
        plan, "the full plan", {**ENV, "APPLY": "true"}, "Handle `a` | b"
    )

    assert "### Changes (1 to create, 1 to replace, 1 to destroy, 1 to forget)" in text
    for row in (
        "| create | `aws_s3_bucket.new` |",
        f"| replace | `{TASK_DEFINITION}` |",
        "| destroy | `aws_iam_role.old` |",
        "| forget | `aws_x.future` |",
    ):
        assert row in text
    assert "aws_x.same" not in text
    assert "| Mode | Plan and apply |" in text
    assert "Handle \\`a\\` \\| b |" in text  # the commit subject can't break the table
    assert "<summary>Full plan</summary>" in text
    assert "the full plan" in text


@pytest.mark.parametrize(
    ("plan_text", "expected"),
    [
        (
            "a\n```\nb",
            "\n````\na\n```\nb\n````\n",
        ),  # a wider fence than any backticks in the plan
        ("x" * (rs.MAX_PLAN_BYTES + 10), "... (truncated)"),
    ],
)
def test_plan_text_is_fenced_safely_and_kept_small(plan_text, expected):
    plan = {"resource_changes": [entry("a.b", ["update"])]}

    assert expected in rs.plan_markdown(plan, plan_text, ENV)


@pytest.mark.parametrize(
    ("digest", "expected"),
    [("reg/repo@sha256:123", "sha256:123"), ("", "not available")],
)
def test_image_markdown(digest, expected):
    text = rs.image_markdown("reg/repo", "abc", digest)

    assert "| Repository | `reg/repo` |" in text
    assert "| Tag | `abc` |" in text
    assert f"| Digest | `{expected}` |" in text


@pytest.mark.parametrize(
    ("before", "schedule", "expected", "absent"),
    [
        ("5", SCHEDULE, ("| Task definition | `fam:6` (was `:5`) |",), None),
        (None, SCHEDULE, ("| Task definition | `fam:6` |",), "was"),
        ("6", SCHEDULE, ("| Task definition | `fam:6` |",), "was"),
        (
            None,
            SCHEDULE,
            (
                "`ENABLED`, `cron(0 5 * * ? *)` in America/Los_Angeles",
                "ecs/v2/clusters/clu/tasks?region=us-east-2",
            ),
            None,
        ),
        # Scheduler leaves the time zone out when it is UTC, and the answer can lack fields.
        (None, {"State": "ENABLED"}, ("`ENABLED`, `unknown` in UTC",), None),
        (None, {}, ("`unknown`, `unknown` in UTC",), None),
    ],
)
def test_deployed_markdown(before, schedule, expected, absent):
    text = rs.deployed_markdown("fam", "6", before, schedule, "clu", "us-east-2")

    for fragment in expected:
        assert fragment in text
    if absent:
        assert absent not in text


def test_replaced_revision_reads_the_task_definition_entry():
    plan = {
        "resource_changes": [
            entry("aws_iam_role.x", ["update"], {"revision": 9}),
            entry(TASK_DEFINITION, ["delete", "create"], {"revision": 5}),
        ]
    }

    assert rs.replaced_revision(plan) == "5"
    assert (
        rs.replaced_revision({"resource_changes": [entry("a.b", ["create"])]}) is None
    )


# --- running the commands --------------------------------------------------


def test_run_returns_stripped_output():
    assert rs.run("python3", "-c", "print('hi')") == "hi"


def test_append_prints_without_a_summary_file(capsys):
    rs.append("hello", {})

    assert capsys.readouterr().out == "hello"


@pytest.mark.parametrize(
    ("git", "subject"),
    [(lambda *command: "Commit subject", "Commit subject"), (no_git, "")],
)
def test_main_plan_writes_the_summary_file(tmp_path, monkeypatch, git, subject):
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(json.dumps({"resource_changes": [entry("a.b", ["create"])]}))
    plan_text = tmp_path / "plan.txt"
    plan_text.write_text("plan text")
    summary = tmp_path / "summary.md"
    monkeypatch.setattr(
        rs, "run", git
    )  # with no git, the commit subject is simply left out

    code = rs.main(
        ["plan", str(plan_json), str(plan_text)],
        {**ENV, "GITHUB_STEP_SUMMARY": str(summary)},
    )

    assert code == 0
    assert subject in summary.read_text()
    assert "`a.b`" in summary.read_text()


def test_main_image_appends_to_the_summary_file(tmp_path):
    summary = tmp_path / "summary.md"

    code = rs.main(
        ["image", "repo", "tag", "repo@sha256:9"], {"GITHUB_STEP_SUMMARY": str(summary)}
    )

    assert code == 0
    assert "sha256:9" in summary.read_text()


def test_main_deployed_reads_terraform_and_aws(tmp_path, monkeypatch):
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(
        json.dumps(
            {
                "resource_changes": [
                    entry(TASK_DEFINITION, ["delete", "create"], {"revision": 5})
                ]
            }
        )
    )
    summary = tmp_path / "summary.md"
    outputs = {
        "task_definition_family": "fam",
        "ecs_cluster_name": "clu",
        "schedule_name": "sched",
    }

    def fake_run(*command):
        if command[0] == "terraform":
            return outputs[command[-1]]
        return "6" if command[1] == "ecs" else json.dumps(SCHEDULE)

    monkeypatch.setattr(rs, "run", fake_run)

    code = rs.main(
        ["deployed", str(plan_json)],
        {"GITHUB_STEP_SUMMARY": str(summary), "AWS_REGION": "us-east-2"},
    )

    assert code == 0
    assert "`fam:6` (was `:5`)" in summary.read_text()


@pytest.mark.parametrize("argv", [[], ["plan"], ["image", "a"], ["nope"]])
def test_main_rejects_bad_usage(argv, capsys):
    assert rs.main(argv, {}) == 2
    assert "release_summary.py" in capsys.readouterr().err
