"""Generate the golden Open-X-Tactile fixture tar (deterministic, synthetic).

Layout mirrors the real FTP-1 release tars on HuggingFace
(https://huggingface.co/datasets/MJJJJ1064/FTP-1-Dataset): one tar holding
several ``<Task>.zarr`` stores (zarr v2, ``meta/episode_ends`` plus time-major
``data/*`` arrays, blosc/zstd compressed chunk members). Two tasks are
generated to cover both tactile payload kinds:

- ``Wipe_Demo`` mirrors the VLA_touch gripper layout: a GelSightMini image
  stream (``right_tactile_data_gripper``, type ``image``).
- ``task_0001_Pick_Demo`` mirrors the RH20TCfg7Tactile layout verified in the
  release tar (task ``task_0050_Dish_on_rack``, sensor/type strings decoded
  from real chunks): two tactile streams — a uSkin taxel matrix
  (``right_tactile_data_gripper``, type ``matrix``, (T, 2, 4, 4, 3) float32
  for 2 fingertips x 4x4 taxels x 3 axes) and an ATIAxia80M20 force/torque
  stream (``right_tactile_data_grippertorque``, type ``state``, (T, 1, 6)) —
  plus poses, joints, base F/T and cameras as shipped.

All array CONTENT is synthetic; nothing is copied from the real datasets.

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

H = W = 32  # deliberately small; the adapter must not assume 224x224

# Wipe_Demo: FTP-1 gripper layout (VLA_touch-like), image stream
WIPE_EPISODE_ENDS = [10, 25, 40]  # 3 episodes, 40 frames total
WIPE_DATA_KEY = "right_tactile_data_gripper"
WIPE_AREA_KEY = "right_tactile_area_gripper"

# task_0001_Pick_Demo: FTP-1 RH20TCfg7Tactile-like layout with the two real
# tactile streams verified in the release tar (task_0050_Dish_on_rack):
# a uSkin taxel matrix (type "matrix") and an ATIAxia80M20 force/torque
# stream (type "state").
PICK_EPISODE_ENDS = [8, 20]  # 2 episodes, 20 frames total
PICK_USKIN_KEY = "right_tactile_data_gripper"  # (T, 2 areas, 4x4 taxels, 3 axes)
PICK_USKIN_SENSOR = "uSkin"
PICK_USKIN_TAXELS = 4  # 4x4 grid = 16 taxels per fingertip
PICK_FT_KEY = "right_tactile_data_grippertorque"  # (T, 1 area, 6) F/T
PICK_FT_SENSOR = "ATIAxia80M20"


def synthetic_frame(frame: int, area: int, height: int, width: int) -> np.ndarray:
    """Deterministic uint8 (H, W, 3) gradient with a moving contact blob."""
    yy, xx = np.mgrid[0:height, 0:width]
    cx = (frame * 3 + area * 11) % width
    cy = (frame * 2 + area * 7) % height
    blob = 255.0 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / 40.0))
    base = ((xx * 2 + yy + frame * 5 + area * 30) % 256).astype(np.float64)
    channels = np.stack([np.clip(base + blob + c * 17, 0, 255) for c in range(3)], axis=-1)
    return channels.astype(np.uint8)


def make_writer(root: pathlib.Path):
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

    return put


def build_wipe_task(root: pathlib.Path) -> None:
    put = make_writer(root)
    total = WIPE_EPISODE_ENDS[-1]
    put("meta/episode_ends", np.array(WIPE_EPISODE_ENDS, dtype="<i8"), (3,), compressor=None)

    tactile = np.stack(
        [np.stack([synthetic_frame(t, a, H, W) for a in range(2)], axis=0) for t in range(total)]
    )
    camera = np.stack([synthetic_frame(t, 2, H, W) for t in range(total)])

    put("data/timestamps", np.arange(total, dtype="<i8"), (10,))
    put("data/camera_main_rgb", camera, (10, H, W, 3))
    put(
        "data/right_arm_joints",
        np.sin(np.arange(total * 7, dtype=np.float64) * 0.1).reshape(total, 7).astype("<f4"),
        (10, 7),
    )
    put(
        "data/right_hand_joints",
        np.linspace(0.0, 0.9, total, dtype="<f4").reshape(total, 1),
        (10, 1),
    )
    put("data/right_hand_joints_idx", np.full((total, 1), 28, dtype="<i4"), (10, 1))
    put("data/" + WIPE_DATA_KEY, tactile, (10, 2, H, W, 3))
    put("data/" + WIPE_AREA_KEY, np.tile(np.array([0, 1], dtype="<i8"), (total, 1)), (10, 2))
    put("data/right_tactile_sensor_gripper", np.full(total, "GelSightMini", dtype="<U12"), (10,))
    put("data/right_tactile_type_gripper", np.full(total, "image", dtype="<U5"), (10,))
    put("data/sub_task_instruction", np.full(total, "wipe the table", dtype="<U16"), (10,))


def build_pick_task(root: pathlib.Path) -> None:
    put = make_writer(root)
    total = PICK_EPISODE_ENDS[-1]
    put("meta/episode_ends", np.array(PICK_EPISODE_ENDS, dtype="<i8"), (2,), compressor=None)

    # (T, 2 areas, 4x4 taxels, 3 axes) float32, like RH20T's uSkin fingertips
    axes = np.arange(total * 2 * PICK_USKIN_TAXELS**2 * 3, dtype=np.float64) * 0.05
    uskin = 0.5 + 0.5 * np.sin(axes).reshape(total, 2, PICK_USKIN_TAXELS, PICK_USKIN_TAXELS, 3)
    ft = np.sin(np.arange(total * 6, dtype=np.float64) * 0.3).reshape(total, 1, 6)
    camera = np.stack([synthetic_frame(t, 3, H, W) for t in range(total)])

    put("data/timestamps", np.arange(total, dtype="<i8"), (8,))
    put(
        "data/" + PICK_USKIN_KEY,
        uskin.astype("<f4"),
        (8, 2, PICK_USKIN_TAXELS, PICK_USKIN_TAXELS, 3),
    )
    put(
        "data/right_tactile_area_gripper",
        np.tile(np.array([0, 1], dtype="<i8"), (total, 1)),
        (8, 2),
    )
    put("data/right_tactile_sensor_gripper", np.full(total, PICK_USKIN_SENSOR, dtype="<U5"), (8,))
    put("data/right_tactile_type_gripper", np.full(total, "matrix", dtype="<U6"), (8,))
    put("data/" + PICK_FT_KEY, ft.astype("<f4"), (8, 1, 6))
    put("data/right_tactile_area_grippertorque", np.full((total, 1), 0, dtype="<i4"), (8, 1))
    put(
        "data/right_tactile_sensor_grippertorque",
        np.full(total, PICK_FT_SENSOR, dtype="<U12"),
        (8,),
    )
    put("data/right_tactile_type_grippertorque", np.full(total, "state", dtype="<U5"), (8,))
    put(
        "data/right_hand_pose",
        np.sin(np.arange(total * 6, dtype=np.float64) * 0.2).reshape(total, 1, 6).astype("<f4"),
        (8, 1, 6),
    )
    put(
        "data/right_wrist_pose",
        np.cos(np.arange(total * 6, dtype=np.float64) * 0.2).reshape(total, 6).astype("<f4"),
        (8, 6),
    )
    put(
        "data/robot_joint",
        np.sin(np.arange(total * 21, dtype=np.float64) * 0.1).reshape(total, 21).astype("<f4"),
        (8, 21),
    )
    put(
        "data/robot_ft_base",
        np.cos(np.arange(total * 6, dtype=np.float64) * 0.1).reshape(total, 6).astype("<f4"),
        (8, 6),
    )
    put(
        "data/gripper_width_m",
        np.linspace(0.0, 0.08, total, dtype="<f4").reshape(total, 1),
        (8, 1),
    )
    put("data/right_wrist_camera_rgb", camera, (8, H, W, 3))
    put("data/camera_main_rgb", np.roll(camera, 1, axis=0), (8, H, W, 3))
    put("data/sub_task_instruction", np.full(total, "pick up the dish", dtype="<U16"), (8,))


def tar_member_sort(path: str) -> tuple[str, str]:
    """Order members by path; dot-metadata files sort after siblings in their dir."""
    parent, _, base = path.rpartition("/")
    if base.startswith("."):
        return parent + "/~~" + base, base
    return parent + "/\x00" + base, base


def write_tar(roots: list[pathlib.Path], out: pathlib.Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w", format=tarfile.USTAR_FORMAT) as tf:
        for root in roots:
            members = sorted(
                str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()
            )
            members.sort(key=tar_member_sort)
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
        wipe = pathlib.Path(tmp) / "Wipe_Demo.zarr"
        pick = pathlib.Path(tmp) / "task_0001_Pick_Demo.zarr"
        build_wipe_task(wipe)
        build_pick_task(pick)
        write_tar([wipe, pick], args.out)
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
