import Metashape


def realign_selected_cameras(
    chunk, selected_cameras, downscale=2, generic_preselection=True, optimize=True
):
    """
    Reset transforms for selected cameras, rematch them against the chunk and align.
    Returns a simple result dict.
    """
    if not selected_cameras:
        return {"realigned": 0, "failed": 0}

    # reset transforms
    for cam in selected_cameras:
        cam.transform = None

    # rematch selected cameras against the whole chunk
    chunk.matchPhotos(
        cameras=selected_cameras,
        downscale=downscale,
        generic_preselection=generic_preselection,
        reference_preselection=False,
        filter_mask=False,
        mask_tiepoints=False,
        keep_keypoints=True,
        reset_matches=False,
    )

    # align selected cameras
    chunk.alignCameras(
        cameras=selected_cameras, adaptive_fitting=True, reset_alignment=False
    )

    realigned = [c for c in selected_cameras if c.transform is not None]
    failed = [c for c in selected_cameras if c.transform is None]

    if optimize and realigned:
        chunk.optimizeCameras(
            fit_f=True,
            fit_cx=True,
            fit_cy=True,
            fit_k1=True,
            fit_k2=True,
            fit_k3=True,
            fit_p1=True,
            fit_p2=True,
            adaptive_fitting=True,
        )

    return {
        "realigned": len(realigned),
        "failed": len(failed),
        "failed_cameras": failed,
    }


def get_alignment_stats(chunk):
    """Return alignment counts and lists for the chunk."""
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
    chunk, unaligned_cameras, downscale=2, generic_preselection=True
):
    """
    Match photos for unaligned cameras (resets matches for those cameras).
    """
    if not unaligned_cameras:
        return 0
    chunk.matchPhotos(
        cameras=unaligned_cameras,
        downscale=downscale,
        generic_preselection=generic_preselection,
        reference_preselection=False,
        filter_mask=False,
        mask_tiepoints=False,
        keep_keypoints=True,
        reset_matches=True,
    )
    return len(unaligned_cameras)


def incremental_align_cameras(
    chunk,
    batch_size=20,
    max_iterations=10,
    optimize_each_batch=True,
    adaptive_fitting=True,
):
    """
    Incrementally align unaligned cameras in batches until none left or max_iterations reached.
    Returns summary dict.
    """
    stats = get_alignment_stats(chunk)
    if stats["aligned_count"] == 0:
        return {
            "error": "No aligned cameras present to bootstrap incremental alignment."
        }
    if stats["unaligned_count"] == 0:
        return {
            "initial_aligned": stats["aligned_count"],
            "initial_unaligned": 0,
            "final_aligned": stats["aligned_count"],
            "final_unaligned": 0,
            "newly_aligned": 0,
            "iterations": 0,
        }

    unaligned = stats["unaligned"].copy()
    newly_aligned_total = 0
    iterations = 0

    while unaligned and iterations < max_iterations:
        iterations += 1
        batch = unaligned[:batch_size]

        # try align batch (no reset of already existing transforms)
        chunk.alignCameras(
            cameras=batch, adaptive_fitting=adaptive_fitting, reset_alignment=False
        )

        newly_aligned = [c for c in batch if c.transform is not None]
        newly_aligned_total += len(newly_aligned)
        unaligned = [c for c in unaligned if c.transform is None]

        if not newly_aligned:
            # stop if no camera aligned in this iteration
            break

        if optimize_each_batch:
            chunk.optimizeCameras(
                fit_f=True,
                fit_cx=True,
                fit_cy=True,
                fit_k1=True,
                fit_k2=True,
                fit_k3=True,
                fit_p1=True,
                fit_p2=True,
                adaptive_fitting=adaptive_fitting,
            )

    final_stats = get_alignment_stats(chunk)
    return {
        "initial_aligned": stats["aligned_count"],
        "initial_unaligned": stats["unaligned_count"],
        "final_aligned": final_stats["aligned_count"],
        "final_unaligned": final_stats["unaligned_count"],
        "newly_aligned": newly_aligned_total,
        "iterations": iterations,
        "unaligned_cameras": final_stats["unaligned"],
    }


def disable_unaligned_cameras(chunk):
    """Disable all unaligned cameras and return count."""
    stats = get_alignment_stats(chunk)
    for camera in stats["unaligned"]:
        camera.enabled = False
    return stats["unaligned_count"]


def show_alignment_statistics(chunk):
    """Print a short alignment summary to console."""
    stats = get_alignment_stats(chunk)
    print("\n" + "=" * 60)
    print("ALIGNMENT STATISTICS")
    print("=" * 60)
    print(f"Total cameras: {stats['total']}")
    print(
        f"Aligned: {stats['aligned_count']} ({stats['aligned_count'] / stats['total'] * 100:.1f}%)"
    )
    print(
        f"Unaligned: {stats['unaligned_count']} ({stats['unaligned_count'] / stats['total'] * 100:.1f}%)"
    )
    print("=" * 60)
    return stats


def export_unaligned_camera_list(chunk, output_path):
    """Write names of unaligned cameras to a text file."""
    stats = get_alignment_stats(chunk)
    with open(output_path, "w") as fh:
        fh.write("UNALIGNED CAMERAS\n")
        fh.write("=" * 40 + "\n")
        fh.write(f"Total: {stats['total']}\n")
        fh.write(f"Unaligned: {stats['unaligned_count']}\n\n")
        for cam in stats["unaligned"]:
            fh.write(f"{cam.label}\n")
    return output_path


# GUI Dialog wrappers (thin, simple)
def realign_selected_cameras_dialog():
    chunk = Metashape.app.document.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return
    selected = [c for c in chunk.cameras if getattr(c, "selected", False)]
    if not selected:
        Metashape.app.messageBox("Select cameras in the Photos pane first.")
        return

    proceed = Metashape.app.getBool(
        f"Realign {len(selected)} selected cameras?\nContinue?"
    )
    if not proceed:
        return

    downscale = Metashape.app.getInt(
        "Downscale for matching (1=full,2=half,4=quarter)", 2
    )
    if downscale is None:
        return
    generic_preselection = Metashape.app.getBool(
        "Use generic preselection for matching?"
    )
    optimize = Metashape.app.getBool("Optimize after realignment?")

    res = realign_selected_cameras(
        chunk,
        selected,
        downscale=downscale,
        generic_preselection=generic_preselection,
        optimize=optimize,
    )
    Metashape.app.messageBox(f"Realigned: {res['realigned']}\nFailed: {res['failed']}")


def incremental_alignment_dialog():
    chunk = Metashape.app.document.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return
    stats = get_alignment_stats(chunk)
    if stats["aligned_count"] == 0:
        Metashape.app.messageBox(
            "No aligned cameras available to bootstrap incremental alignment."
        )
        return
    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras to process.")
        return

    proceed = Metashape.app.getBool(
        f"Incrementally align {stats['unaligned_count']} unaligned cameras?\nContinue?"
    )
    if not proceed:
        return

    downscale = Metashape.app.getInt(
        "Downscale for matching when required (1=full,2=half,4=quarter)", 2
    )
    if downscale is None:
        return
    generic_preselection = Metashape.app.getBool(
        "Use generic preselection for matching?"
    )

    # ensure matches for unaligned cameras before attempting incremental alignment
    unaligned = stats["unaligned"]
    match_unaligned_photos(
        chunk, unaligned, downscale=downscale, generic_preselection=generic_preselection
    )

    batch = Metashape.app.getInt("Batch size for alignment:", 20)
    if batch is None:
        return
    iterations = Metashape.app.getInt("Max iterations:", 10)
    if iterations is None:
        return
    optimize_each = Metashape.app.getBool("Optimize after each batch?")

    res = incremental_align_cameras(
        chunk,
        batch_size=batch,
        max_iterations=iterations,
        optimize_each_batch=optimize_each,
    )
    Metashape.app.messageBox(
        f"Incremental alignment finished.\nNewly aligned: {res.get('newly_aligned', 0)}\nRemaining unaligned: {res.get('final_unaligned', 0)}"
    )


def show_alignment_stats_dialog():
    chunk = Metashape.app.document.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return
    stats = show_alignment_statistics(chunk)
    Metashape.app.messageBox(
        f"Cameras: {stats['total']}\nAligned: {stats['aligned_count']}\nUnaligned: {stats['unaligned_count']}\nSee console for details."
    )


def disable_unaligned_cameras_dialog():
    chunk = Metashape.app.document.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return
    stats = get_alignment_stats(chunk)
    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras.")
        return
    proceed = Metashape.app.getBool(
        f"Disable {stats['unaligned_count']} unaligned cameras?\nContinue?"
    )
    if not proceed:
        return
    count = disable_unaligned_cameras(chunk)
    Metashape.app.messageBox(f"Disabled {count} unaligned cameras.")


def export_unaligned_list_dialog():
    chunk = Metashape.app.document.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return
    stats = get_alignment_stats(chunk)
    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras to export.")
        return
    path = Metashape.app.getSaveFileName(
        "Save unaligned list", filter="Text files (*.txt);;All files (*.*)"
    )
    if not path:
        return
    export_unaligned_camera_list(chunk, path)
    Metashape.app.messageBox(f"Exported unaligned camera list to:\n{path}")


def add_menu_items():
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Realign Selected Cameras...",
        realign_selected_cameras_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Align Unaligned Cameras...",
        incremental_alignment_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Show Alignment Statistics",
        show_alignment_stats_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Disable Unaligned Cameras",
        disable_unaligned_cameras_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Export Unaligned Camera List...",
        export_unaligned_list_dialog,
    )


# initialization
label = "Custom/Incremental Alignment"
add_menu_items()

print("\n" + "=" * 70)
print("INCREMENTAL ALIGNMENT TOOLS LOADED")
print("=" * 70)
print("Available in menu: Custom -> Incremental Alignment")
print("  - Realign Selected Cameras...")
print("  - Align Unaligned Cameras...")
print("  - Show Alignment Statistics")
print("  - Disable Unaligned Cameras")
print("  - Export Unaligned Camera List...")
print("=" * 70)
