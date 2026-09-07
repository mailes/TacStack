"""Generate the golden Open-X-Tactile fixture tar (deterministic, synthetic).

Layout mirrors the real FTP-1 release tars (e.g. VLA_touch.tar on HuggingFace:
https://huggingface.co/datasets/MJJJJ1064/FTP-1-Dataset, task sub-stores named
``<Task>.zarr`` with ``meta/episode_ends`` and time-major ``data/*`` arrays,
blosc/zstd compressed chunk members). All array CONTENT is synthetic; nothing
is copied from the real dataset.

Determinism: content is derived from frame indices only (no RNG), tar member
mtimes/ids are zeroed, and member order is a fixed permutation that places
dot-metadata files after chunk files within each directory (mirroring the
member order observed in real release tars). Re-running reproduces identical
bytes, which the test suite relies on via the committed fixture.

Usage: uv run python scripts/make_oxt_fixture.py [--out tests/fixtures/...]
This script is a development tool; CI only uses the committed fixture.
"""

import argparse
import pathlib
import tarfile
import tempfile

import numcodecs
import numpy as np
import zarr

EPISODE_ENDS = [10, 25, 40]  # 3 episodes, 40 frames total
T = EPISODE_ENDS[-1]
H = W = 32  # deliberately small; the adapter must not assume 224x224
AREA_KEY = "right_tactile_area_gripper"
DATA_KEY = "right_tactile_data_gripper"


def synthetic_frame(frame: int, area: int, height: int, width: int) -> np.ndarray:
    """Deterministic uint8 (H, W, 3) gradient with a moving contact blob."""
    yy, xx = np.mgrid[0:height, 0:width]
    cx = (frame * 3 + area * 11) % width
    cy = (frame * 2 + area * 7) % height
    blob = 255.0 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / 40.0))
    base = ((xx * 2 + yy + frame * 5 + area * 30) % 256).astype(np.float64)
    channels = np.stack([np.clip(base + blob + c * 17, 0, 255) for c in range(3)], axis=-1)
    return channels.astype(np.uint8)


def build_zarr_tree(root: pathlib.Path) -> None:
    blosc = numcodecs.Blosc(cname="zstd", clevel=5, shuffle=numcodecs.Blosc.SHUFFLE)

    def put(
        name: str, data: np.ndarray, chunks: tuple[int, ...], compressor: object = blosc
    ) -> None:
        zarr.create_array(
            store=root,
            name=name,
            data=data,
            chunks=chunks,
            zarr_format=2,
            compressors=compressor,
        )

    put("meta/episode_ends", np.array(EPISODE_ENDS, dtype="<i8"), (3,), compressor=None)

    tactile = np.stack(
        [np.stack([synthetic_frame(t, a, H, W) for a in range(2)], axis=0) for t in range(T)]
    )
    camera = np.stack([synthetic_frame(t, 2, H, W) for t in range(T)])

    put("data/timestamps", np.arange(T, dtype="<i8"), (10,))
    put("data/camera_main_rgb", camera, (10, H, W, 3))
    put(
        "data/right_arm_joints",
        np.sin(np.arange(T * 7, dtype=np.float64) * 0.1).reshape(T, 7).astype("<f4"),
        (10, 7),
    )
    put("data/right_hand_joints", np.linspace(0.0, 0.9, T, dtype="<f4").reshape(T, 1), (10, 1))
    put("data/right_hand_joints_idx", np.full((T, 1), 28, dtype="<i4"), (10, 1))
    put("data/" + DATA_KEY, tactile, (10, 2, H, W, 3))
    put("data/" + AREA_KEY, np.tile(np.array([0, 1], dtype="<i8"), (T, 1)), (10, 2))
    put("data/right_tactile_sensor_gripper", np.full(T, "GelSightMini", dtype="<U12"), (10,))
    put("data/right_tactile_type_gripper", np.full(T, "image", dtype="<U5"), (10,))
    put("data/sub_task_instruction", np.full(T, "wipe the table", dtype="<U16"), (10,))


def tar_member_sort(path: str) -> tuple[str, str]:
    """Order members by path; dot-metadata files sort after siblings in their dir."""
    parent, _, base = path.rpartition("/")
    if base.startswith("."):
        return parent + "/~~" + base, base
    return parent + "/\x00" + base, base


def write_tar(root: pathlib.Path, out: pathlib.Path) -> None:
    members = sorted(
        str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()
    )
    members.sort(key=tar_member_sort)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w", format=tarfile.USTAR_FORMAT) as tf:
        for name in members:
            info = tarfile.TarInfo(name=f"TacStackDemo/{root.name}/{name}")
            info.size = (root / name).stat().st_size
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with open(root / name, "rb") as f:
                tf.addfile(info, f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("tests/fixtures/open_x_tactile/demo_wipe.tar"),
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp) / "Wipe_Demo.zarr"
        build_zarr_tree(root)
        write_tar(root, args.out)
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
