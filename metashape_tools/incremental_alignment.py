from __future__ import annotations

import Metashape

from metashape_tools.utils import (
    ask_bool,
    ask_int,
    ask_save_file,
    require_active_chunk,
)


def get_alignment_stats(chunk: Metashape.Chunk) -> dict:
    aligned = [c for c in chunk.cameras if c.transform is not None]
    unaligned = [c for c in chunk.cameras if c.transform is None]
    return {
        "total": len(chunk.cameras),
        "aligned": aligned,
        "unaligned": unaligned,
        "aligned_count": len(aligned),
        "unaligned_count": len(unaligned),
    }


def match_unaligned_photos(
    chunk: Metashape.Chunk,
    cameras,
    downscale=2,
    generic_preselection=True,
    reset_matches=True,
) -> int:
    if not cameras:
        return 0
    chunk.matchPhotos(
        cameras=list(cameras),
        downscale=downscale,
        generic_preselection=generic_preselection,
        reference_preselection=False,
        filter_mask=False,
        mask_tiepoints=False,
        keep_keypoints=True,
        reset_matches=bool(reset_matches),
    )
    return len(list(cameras))


def realign_selected_cameras(
    chunk: Metashape.Chunk,
    selected_cameras,
    downscale=2,
    generic_preselection=True,
    optimize=True,
) -> dict:
    if not selected_cameras:
        return {"realigned": 0, "failed": 0}

    for cam in selected_cameras:
        cam.transform = None

    match_unaligned_photos(
        chunk,
        selected_cameras,
        downscale=downscale,
        generic_preselection=generic_preselection,
        reset_matches=True,
    )
    chunk.alignCameras(
        cameras=list(selected_cameras), adaptive_fitting=True, reset_alignment=False
    )

    realigned = [c for c in selected_cameras if c.transform is not None]
    failed = [c for c in selected_cameras if c.transform is None]

    if optimize and realigned:
        chunk.optimizeCameras(adaptive_fitting=True)

    return {"realigned": len(realigned), "failed": len(failed)}


def incremental_align_cameras(
    chunk: Metashape.Chunk, batch_size=20, max_iterations=10, optimize_each_batch=True
) -> dict:
    s0 = get_alignment_stats(chunk)
    if s0["aligned_count"] == 0:
        return {"error": "No aligned cameras present."}
    if s0["unaligned_count"] == 0:
        return {"iterations": 0, "newly_aligned": 0, "final_unaligned": 0}

    unaligned = s0["unaligned"][:]
    newly = 0
    it = 0

    while unaligned and it < max_iterations:
        it += 1
        batch = unaligned[:batch_size]
        chunk.alignCameras(cameras=batch, adaptive_fitting=True, reset_alignment=False)

        aligned_now = [c for c in batch if c.transform is not None]
        newly += len(aligned_now)
        unaligned = [c for c in unaligned if c.transform is None]

        if not aligned_now:
            break

        if optimize_each_batch:
            chunk.optimizeCameras(adaptive_fitting=True)

    s1 = get_alignment_stats(chunk)
    return {
        "iterations": it,
        "newly_aligned": newly,
        "final_unaligned": s1["unaligned_count"],
    }


# ----------------
# GUI dialogs
# ----------------


def realign_selected_cameras_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return
    selected = [c for c in chunk.cameras if getattr(c, "selected", False)]
    if not selected:
        Metashape.app.messageBox("Select cameras first.")
        return

    if not ask_bool(f"Realign {len(selected)} selected cameras?"):
        return

    downscale = ask_int("Downscale (1,2,4)", 2)
    if downscale is None:
        return

    res = realign_selected_cameras(chunk, selected, downscale=downscale, optimize=True)
    Metashape.app.messageBox(f"Realigned: {res['realigned']}\nFailed: {res['failed']}")


def incremental_alignment_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    st = get_alignment_stats(chunk)
    if st["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras.")
        return
    if st["aligned_count"] == 0:
        Metashape.app.messageBox(
            "No aligned cameras to bootstrap incremental alignment."
        )
        return

    if not ask_bool(f"Incrementally align {st['unaligned_count']} cameras?"):
        return

    downscale = ask_int("Downscale for matching unaligned cameras (1,2,4)", 2)
    if downscale is None:
        return

    match_unaligned_photos(
        chunk,
        st["unaligned"],
        downscale=downscale,
        generic_preselection=True,
        reset_matches=False,
    )

    batch = ask_int("Batch size", 20)
    if batch is None:
        return
    it = ask_int("Max iterations", 10)
    if it is None:
        return

    res = incremental_align_cameras(
        chunk, batch_size=batch, max_iterations=it, optimize_each_batch=True
    )
    if "error" in res:
        Metashape.app.messageBox(res["error"])
    else:
        Metashape.app.messageBox(
            f"Done.\nIterations: {res['iterations']}\nNewly aligned: {res['newly_aligned']}\nRemaining unaligned: {res['final_unaligned']}"
        )


# ------------------------------------------
# Export unaligned camera list
# ------------------------------------------


def export_unaligned_camera_list(chunk, file_path):
    """
    Write one camera label per line for every unaligned camera.

    Returns:
        int: number of unaligned cameras written.
    """
    stats = get_alignment_stats(chunk)
    with open(file_path, "w") as f:
        for cam in stats["unaligned"]:
            f.write("{}\n".format(cam.label))
    return stats["unaligned_count"]


def export_unaligned_list_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return
    stats = get_alignment_stats(chunk)
    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras.")
        return

    path = ask_save_file(
        "Save unaligned camera list", filter="Text files (*.txt);;All files (*.*)"
    )
    if not path:
        return

    n = export_unaligned_camera_list(chunk, path)
    Metashape.app.messageBox("Exported {} unaligned cameras.".format(n))


# ------------------------------------------
# Transfer oriented cameras between chunks
# ------------------------------------------


def _ensure_camera_in_chunk(dst_chunk, src_cam):
    """Return camera with src_cam.label in dst_chunk; add its photo if missing."""
    for cam in dst_chunk.cameras:
        if cam.label == src_cam.label:
            return cam
    photo = src_cam.photo
    if photo is None or photo.path is None:
        return None
    new_cams = dst_chunk.addPhotos([photo.path])
    return new_cams[0] if new_cams else None


def transfer_oriented_cameras_from_chunk(
    src_chunk, dst_chunk, downscale=2, generic_preselection=True, optimize=True
):
    """
    Transfer camera poses from src_chunk to dst_chunk for cameras that are
    aligned in src but not in dst, then match and refine.

    Assumes chunks are already aligned (same coordinate system).

    Returns:
        dict with transferred, matched and optimized counts.
    """
    src_aligned = {c.label: c for c in src_chunk.cameras if c.transform is not None}
    dst_by_label = {c.label: c for c in dst_chunk.cameras}

    to_transfer = []
    for label, s_cam in src_aligned.items():
        d_cam = dst_by_label.get(label)
        if d_cam is None or d_cam.transform is None:
            to_transfer.append(label)

    if not to_transfer:
        return {"transferred": 0, "matched": 0, "optimized": False}

    transferred_cams = []
    for label in to_transfer:
        s_cam = src_aligned[label]
        d_cam = _ensure_camera_in_chunk(dst_chunk, s_cam)
        if d_cam is None:
            print("Warning: could not add camera {} to destination".format(label))
            continue

        # Transform position: src internal -> world -> dst internal
        world_pos = src_chunk.transform.matrix.mulp(s_cam.center)
        dst_internal_pos = dst_chunk.transform.matrix.inv().mulp(world_pos)

        # Transform rotation
        src_rotation = (
            src_chunk.transform.matrix
            * s_cam.transform
            * Metashape.Matrix.Diag([1, 1, 1, 0])
        )
        dst_rotation = dst_chunk.transform.matrix.inv() * src_rotation

        d_cam.transform = Metashape.Matrix.Translation(dst_internal_pos) * dst_rotation
        d_cam.enabled = True
        transferred_cams.append(d_cam)

    # Match and refine
    if transferred_cams:
        match_unaligned_photos(
            dst_chunk,
            transferred_cams,
            downscale=downscale,
            generic_preselection=generic_preselection,
            reset_matches=False,
        )
        try:
            dst_chunk.alignCameras(
                cameras=transferred_cams, adaptive_fitting=True, reset_alignment=False
            )
        except Exception as e:
            print("Warning: alignCameras failed: {}".format(e))

        if optimize:
            try:
                dst_chunk.optimizeCameras(adaptive_fitting=True)
            except Exception as e:
                print("Warning: optimization failed: {}".format(e))

    return {
        "transferred": len(transferred_cams),
        "matched": len(transferred_cams),
        "optimized": bool(optimize),
    }


def transfer_oriented_cameras_dialog():
    doc = Metashape.app.document
    if not doc or len(doc.chunks) < 2:
        Metashape.app.messageBox("Need at least two chunks.")
        return

    labels = [
        "{}: {} (cams: {})".format(i, c.label, len(c.cameras))
        for i, c in enumerate(doc.chunks)
    ]

    msg = "Select SOURCE chunk:\n\n" + "\n".join(labels)
    src_idx = ask_int(msg, 1)
    if src_idx is None or src_idx < 0 or src_idx >= len(doc.chunks):
        return

    msg = "Select DESTINATION chunk:\n\n" + "\n".join(labels)
    dst_idx = ask_int(msg, 0)
    if (
        dst_idx is None
        or dst_idx < 0
        or dst_idx >= len(doc.chunks)
        or dst_idx == src_idx
    ):
        return

    if not ask_bool(
        "Have you already aligned the chunks?\n(Workflow -> Align Chunks)\n\nContinue?"
    ):
        return

    downscale = ask_int("Downscale for matching (1=full, 2=half, 4=quarter)", 2)
    if downscale is None or downscale < 1:
        return

    optimize = ask_bool("Optimize cameras after transfer?")

    src = doc.chunks[src_idx]
    dst = doc.chunks[dst_idx]

    try:
        res = transfer_oriented_cameras_from_chunk(
            src, dst, downscale=downscale, optimize=optimize
        )
        Metashape.app.messageBox(
            "Transfer complete.\n\nTransferred: {}\nMatched: {}\nOptimized: {}".format(
                res["transferred"], res["matched"], res["optimized"]
            )
        )
    except Exception as e:
        Metashape.app.messageBox("Transfer failed:\n\n{}".format(e))
