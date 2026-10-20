import pytest
from setups_manager.model import Result, Status
from setups_manager.registry import check
from setups_manager.runner import run_all, run_one, select


def register_fakes():
    @check("b-repo", "repos", "repo check")
    def repo_check(ctx):
        yield Result("repo fine", Status.OK)

    @check("a-disk", "system", "disk check", slow=True)
    def disk_check(ctx):
        yield Result("disk 1", Status.OK)
        yield Result("disk 2", Status.WARN)

    @check("only-mac", "system", "not here", platforms=("darwin",))
    def mac_check(ctx):
        yield Result("never", Status.OK)

    @check("broken", "setup", "crashes")
    def broken(ctx):
        raise RuntimeError("boom")
        yield  # a generator, like the real checks


def test_select_orders_by_group_and_drops_other_platforms(registry, ctx):
    register_fakes()
    assert [c.id for c in select(ctx)] == ["a-disk", "broken", "b-repo"]


def test_select_filters(registry, ctx):
    register_fakes()
    assert [c.id for c in select(ctx, quick=True)] == ["broken", "b-repo"]
    assert [c.id for c in select(ctx, groups=["repos"])] == ["b-repo"]
    assert [c.id for c in select(ctx, ids=["a-disk"])] == ["a-disk"]
    with pytest.raises(ValueError, match="only-mac"):
        select(ctx, ids=["only-mac"])


def test_crashing_check_becomes_an_error_result(registry, ctx):
    register_fakes()
    [result] = run_one(select(ctx, ids=["broken"])[0], ctx)
    assert result.status is Status.ERROR
    assert "boom" in result.detail
    assert result.check == "broken"


def test_run_all_keeps_check_order_and_result_order(registry, ctx):
    register_fakes()
    titles = [r.title for r in run_all(select(ctx), ctx)]
    assert titles == ["disk 1", "disk 2", "crashes", "repo fine"]


def test_duplicate_ids_are_rejected(registry):
    register_fakes()
    with pytest.raises(ValueError, match="twice"):
        check("b-repo", "repos", "again")(lambda ctx: [])
