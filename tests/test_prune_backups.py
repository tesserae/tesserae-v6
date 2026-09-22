"""The backup cull must never take a file's last copy.

Written after the by-hand cull of 2026-09-22, where the grouping treated a
plain `la_index.db.bak` as a file in its own right rather than as a backup
of `la_index.db`. That made the report claim five files were about to lose
their only backup when they were not, and the same mistake in the other
direction would delete a real last copy.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.prune_backups import DAY, collect, group_of, plan  # noqa: E402


class TestWhichLiveFileABackupBelongsTo:
    def test_a_dated_tag(self):
        assert group_of('la_index.db.bak-canonical-20260921-231348') == 'la_index.db'

    def test_a_pre_tag_that_also_ends_in_bak(self):
        assert group_of('cop_index.db.pre-rebuild-20260808.bak') == 'cop_index.db'

    def test_a_bare_bak(self):
        """The case that was wrong: no tag after `.bak` at all."""
        assert group_of('la_index.db.bak') == 'la_index.db'

    def test_a_pre_tag_without_a_date(self):
        assert group_of('en_index.db.pre-stage1a.bak') == 'en_index.db'

    def test_all_four_spellings_group_together(self):
        names = ['la_index.db.bak', 'la_index.db.bak-stale-20260921-2313',
                 'la_index.db.pre-stage1a.bak', 'la_index.db.pre-rebuild.bak']
        assert len({group_of(n) for n in names}) == 1


def _write(tmp_path, name, age_days, size=16):
    p = tmp_path / name
    p.write_bytes(b'x' * size)
    t = time.time() - age_days * DAY
    os.utime(p, (t, t))
    return str(p)


class TestTheRule:
    def test_the_newest_copy_is_kept_however_old_it_is(self, tmp_path):
        only = _write(tmp_path, 'grc_bigrams.json.pre-rebuild-20260912.bak', 240)
        groups = collect([str(tmp_path)])
        keep, drop = plan(groups, keep_days=30)
        assert [r[2] for r in keep] == [only]
        assert drop == []

    def test_a_second_copy_survives_while_it_is_fresh(self, tmp_path):
        new = _write(tmp_path, 'la_index.db.bak-a', 1)
        second = _write(tmp_path, 'la_index.db.bak-b', 5)
        old = _write(tmp_path, 'la_index.db.bak-c', 90)
        keep, drop = plan(collect([str(tmp_path)]), keep_days=30)
        assert sorted(r[2] for r in keep) == sorted([new, second])
        assert [r[2] for r in drop] == [old]

    def test_a_stale_second_copy_goes(self, tmp_path):
        new = _write(tmp_path, 'x.db.bak-a', 1)
        stale = _write(tmp_path, 'x.db.bak-b', 60)
        keep, drop = plan(collect([str(tmp_path)]), keep_days=30)
        assert [r[2] for r in keep] == [new]
        assert [r[2] for r in drop] == [stale]

    def test_a_bare_bak_is_pruned_against_its_own_live_file(self, tmp_path):
        """`la_index.db.bak` from February is a backup of `la_index.db`, so a
        recent copy of that file outranks it and it goes."""
        recent = _write(tmp_path, 'la_index.db.bak-canonical-20260921', 1)
        ancient = _write(tmp_path, 'la_index.db.bak', 225)
        keep, drop = plan(collect([str(tmp_path)]), keep_days=30)
        assert [r[2] for r in keep] == [recent]
        assert [r[2] for r in drop] == [ancient]

    def test_no_group_is_ever_emptied(self, tmp_path):
        for n, age in [('a.db.bak-1', 1), ('a.db.bak-2', 200), ('a.db.bak-3', 400),
                       ('b.json.pre-x.bak', 500), ('c.db.bak', 90)]:
            _write(tmp_path, n, age)
        groups = collect([str(tmp_path)])
        keep, drop = plan(groups, keep_days=30)
        dropped = {r[2] for r in drop}
        for copies in groups.values():
            assert any(p not in dropped for _t, _s, p in copies)

    def test_live_files_are_left_alone(self, tmp_path):
        live = _write(tmp_path, 'la_index.db', 1)
        _write(tmp_path, 'la_index.db.bak-old', 200)
        keep, drop = plan(collect([str(tmp_path)]), keep_days=30)
        assert live not in {r[2] for r in keep + drop}
