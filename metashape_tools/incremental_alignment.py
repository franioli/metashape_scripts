import Metashape

from metashape_tools.utils import ask_bool, ask_int, require_active_chunk


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
