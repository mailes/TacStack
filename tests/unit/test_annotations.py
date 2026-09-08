import pytest

from tacstack.annotations import AnnotationLog, TactileMark, normalize_mark, now_ns


def _mark(mark: str = "C", user: str = "tester", frame: int = 0) -> TactileMark:
    return TactileMark(
        source="demo.tar",
        task="Task",
        episode=0,
        stream="stream",
        frame_index=frame,
        oxt_frame_index=frame + 3,
        timestamp_ns=frame * 10**9,
        mark=mark,
        user=user,
        created_ns=now_ns(),
    )


def test_normalize_mark_accepts_codes_and_words() -> None:
    assert normalize_mark("c") == "C"
    assert normalize_mark("S") == "S"
    assert normalize_mark(" slip ") == "S"
    assert normalize_mark("unstable_grasp") == "U"
    with pytest.raises(ValueError, match="unknown mark"):
        normalize_mark("X")


def test_add_and_reload_round_trip(tmp_path) -> None:
    path = tmp_path / "marks.parquet"
    log = AnnotationLog(path)
    log.add(_mark(frame=0))
    log.add(_mark(mark="S", frame=4))
    reloaded = AnnotationLog(path)
    assert len(reloaded) == 2
    marks = reloaded.marks()
    assert marks[0].mark == "C" and marks[0].label == "contact"
    assert marks[1].mark == "S" and marks[1].oxt_frame_index == 7
    assert marks[1].schema_version == "1.0"


def test_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="mark must be one of"):
        _mark(mark="X")
    with pytest.raises(ValueError, match="user must not be empty"):
        _mark(user="   ")
    with pytest.raises(ValueError, match="frame_index must be"):
        _mark(frame=-1)
    with pytest.raises(ValueError, match="timestamp_ns must be"):
        TactileMark(
            source="s",
            task="t",
            episode=0,
            stream="x",
            frame_index=0,
            oxt_frame_index=0,
            timestamp_ns=-5,
            mark="C",
            user="u",
            created_ns=0,
        )
