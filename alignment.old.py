import Metashape


def realign_selected_cameras(
    chunk, selected_cameras, downscale=2, generic_preselection=True, optimize=True
):
    """
    Realign selected cameras by resetting their matches and finding new connections
    with all other images in the chunk.

    Args:
        chunk: Metashape.Chunk
        selected_cameras: List of cameras to realign
        downscale: Downscale factor for matching (1=full, 2=half, 4=quarter)
        generic_preselection: Use generic preselection
        optimize: Run optimization after alignment

    Returns:
        dict: Results of realignment
    """
    print("\n" + "=" * 70)
    print("REALIGNING SELECTED CAMERAS")
    print("=" * 70)

    if not selected_cameras:
        print("No cameras selected!")
        return {"realigned": 0, "failed": 0}

    print(f"\nSelected cameras: {len(selected_cameras)}")

    # Show first few camera names
    for i, cam in enumerate(selected_cameras[:5]):
        print(f"  {cam.label}")
    if len(selected_cameras) > 5:
        print(f"  ... and {len(selected_cameras) - 5} more")

    # Step 1: Reset alignment for selected cameras
    print("\n" + "-" * 70)
    print("STEP 1: RESETTING SELECTED CAMERAS")
    print("-" * 70)

    for cam in selected_cameras:
        cam.transform = None

    print(f"Reset {len(selected_cameras)} camera transforms")

    # Step 2: Reset matches for selected cameras and match against ALL cameras
    print("\n" + "-" * 70)
    print("STEP 2: MATCHING AGAINST ALL CAMERAS")
    print("-" * 70)
    print(f"Downscale: {downscale}")
    print(f"Generic preselection: {generic_preselection}")

    try:
        # Match selected cameras against ALL cameras in the chunk
        # reset_matches=True ensures fresh matches
        chunk.matchPhotos(
            cameras=selected_cameras,
            downscale=downscale,
            generic_preselection=generic_preselection,
            reference_preselection=False,
            filter_mask=False,
            mask_tiepoints=False,
            keep_keypoints=True,
            reset_matches=True,  # Clear old matches
        )
        print("Matching complete!")
    except Exception as e:
        print(f"Matching failed: {e}")
        return {"realigned": 0, "failed": len(selected_cameras), "error": str(e)}

    # Step 3: Align the selected cameras
    print("\n" + "-" * 70)
    print("STEP 3: ALIGNING SELECTED CAMERAS")
    print("-" * 70)

    try:
        chunk.alignCameras(
            cameras=selected_cameras, adaptive_fitting=True, reset_alignment=False
        )
        print("Alignment complete!")
    except Exception as e:
        print(f"Alignment failed: {e}")
        return {"realigned": 0, "failed": len(selected_cameras), "error": str(e)}

    # Count how many got aligned
    realigned = []
    failed = []

    for cam in selected_cameras:
        if cam.transform is not None:
            realigned.append(cam)
        else:
            failed.append(cam)

    print(f"\nRealigned: {len(realigned)}")
    print(f"Failed: {len(failed)}")

    if len(realigned) > 0:
        sample_names = [cam.label for cam in realigned[:5]]
        print(f"Examples: {', '.join(sample_names)}")
        if len(realigned) > 5:
            print(f"... and {len(realigned) - 5} more")

    if len(failed) > 0 and len(failed) <= 10:
        print("\nFailed cameras:")
        for cam in failed:
            print(f"  {cam.label}")

    # Step 4: Optional optimization
    if optimize and len(realigned) > 0:
        print("\n" + "-" * 70)
        print("STEP 4: OPTIMIZING CAMERAS")
        print("-" * 70)

        try:
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
            print("Optimization complete!")
        except Exception as e:
            print(f"Warning: Optimization failed: {e}")

    print("\n" + "=" * 70)
    print("REALIGNMENT COMPLETE")
    print("=" * 70)

    return {
        "realigned": len(realigned),
        "failed": len(failed),
        "optimized": bool(optimize and len(realigned) > 0),
        "failed_cameras": failed,
    }


import numpy as np


def _np_to_ms_matrix(M):
    return Metashape.Matrix(M.tolist())


def _ms_vec_to_np(v):
    return np.array([v[0], v[1], v[2]], dtype=float)


def _estimate_similarity_from_common_cameras(src_chunk, dst_chunk):
    """
    Estimate 7-parameter similarity transform that maps source-chunk coordinates to
    destination-chunk coordinates using cameras aligned in both chunks (matched by label).
    Returns a 4x4 numpy matrix or None if insufficient data.
    """
    # Collect common aligned camera centers
    src_by_label = {c.label: c for c in src_chunk.cameras if c.transform is not None}
    dst_by_label = {c.label: c for c in dst_chunk.cameras if c.transform is not None}

    common = []
    for label in src_by_label.keys() & dst_by_label.keys():
        src_cam = src_by_label[label]
        dst_cam = dst_by_label[label]
        if src_cam.center is None or dst_cam.center is None:
            continue
        common.append((_ms_vec_to_np(src_cam.center), _ms_vec_to_np(dst_cam.center)))

    if len(common) < 3:
        return None, 0  # Need at least 3 for a stable similarity

    P = np.stack([p for p, _ in common], axis=0)  # Nx3 (source)
    Q = np.stack([q for _, q in common], axis=0)  # Nx3 (dest)

    # Umeyama similarity (with scaling)
    mu_P = P.mean(axis=0)
    mu_Q = Q.mean(axis=0)
    X = P - mu_P
    Y = Q - mu_Q

    C = (Y.T @ X) / len(P)
    U, S, Vt = np.linalg.svd(C)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = U @ Vt

    var_P = (X**2).sum() / len(P)
    scale = (S.sum() / var_P) if var_P > 0 else 1.0
    t = mu_Q - scale * (R @ mu_P)

    T = np.eye(4)
    T[:3, :3] = scale * R
    T[:3, 3] = t
    return T, len(common)


def _ensure_camera_in_chunk(dst_chunk, src_cam):
    """Ensure camera with src_cam.label exists in dst_chunk; add photo if missing."""
    for cam in dst_chunk.cameras:
        if cam.label == src_cam.label:
            return cam

    # Not found: add photo
    photo = src_cam.photo
    if photo is None or photo.path is None:
        return None
    new_cams = dst_chunk.addPhotos([photo.path])
    return new_cams[0] if new_cams else None


def transfer_oriented_cameras_from_chunk(
    src_chunk, dst_chunk, downscale=2, generic_preselection=True, optimize=True
):
    """
    Transfer camera poses from src_chunk to dst_chunk for cameras that are aligned in src
    but not aligned in dst, then match+refine so they link to existing tie points.
    """
    # 1) Estimate transform between chunks using common aligned cameras
    T_np, used = _estimate_similarity_from_common_cameras(src_chunk, dst_chunk)
    if T_np is None:
        raise RuntimeError(
            "Not enough common aligned cameras to estimate transform. Align chunks or add markers first."
        )
    T = _np_to_ms_matrix(T_np)

    # 2) Find candidates to transfer
    src_aligned = {c.label: c for c in src_chunk.cameras if c.transform is not None}
    dst_by_label = {c.label: c for c in dst_chunk.cameras}
    to_transfer = []

    for label, s_cam in src_aligned.items():
        d_cam = dst_by_label.get(label, None)
        if d_cam is None or d_cam.transform is None:
            to_transfer.append(label)

    if not to_transfer:
        return {
            "transferred": 0,
            "matched": 0,
            "optimized": False,
            "common_cameras": used,
        }

    # 3) Create or update destination cameras with transformed poses
    transferred_cams = []
    for label in to_transfer:
        s_cam = src_aligned[label]
        d_cam = _ensure_camera_in_chunk(dst_chunk, s_cam)
        if d_cam is None:
            continue
        # Pose in dst frame: T_dst = T * T_src
        d_cam.transform = T * s_cam.transform
        d_cam.enabled = True
        transferred_cams.append(d_cam)

    # 4) Match these cameras against the already aligned block and refine
    if transferred_cams:
        # Reuse existing matcher
        match_unaligned_photos(
            dst_chunk,
            transferred_cams,
            downscale=downscale,
            generic_preselection=generic_preselection,
        )

        try:
            dst_chunk.alignCameras(
                cameras=transferred_cams, adaptive_fitting=True, reset_alignment=False
            )
        except Exception as e:
            print(f"Warning: alignCameras on transferred set failed: {e}")

        if optimize:
            try:
                dst_chunk.optimizeCameras(
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
            except Exception as e:
                print(f"Warning: Optimization failed: {e}")

    return {
        "transferred": len(transferred_cams),
        "matched": len(transferred_cams),
        "optimized": bool(optimize),
        "common_cameras": used,
    }


def transfer_oriented_cameras_dialog():
    """
    Dialog to transfer oriented cameras from one chunk (small) to another (main) and link them.
    """
    doc = Metashape.app.document
    if not doc or len(doc.chunks) < 2:
        Metashape.app.messageBox("Need at least two chunks in the document.")
        return

    # List chunks for selection
    labels = [
        f"{i}: {c.label} (cams: {len(c.cameras)})" for i, c in enumerate(doc.chunks)
    ]
    msg = "Select source chunk (small) index:\n" + "\n".join(labels)
    src_idx = Metashape.app.getInt(msg, 1)
    if src_idx is None or src_idx < 0 or src_idx >= len(doc.chunks):
        return

    msg = "Select destination chunk (main) index:\n" + "\n".join(labels)
    dst_idx = Metashape.app.getInt(msg, 0)
    if (
        dst_idx is None
        or dst_idx < 0
        or dst_idx >= len(doc.chunks)
        or dst_idx == src_idx
    ):
        return

    downscale = Metashape.app.getInt(
        "Downscale for matching:\n1=full, 2=half (recommended), 4=quarter", 2
    )
    if downscale is None or downscale < 1:
        return

    generic_preselection = Metashape.app.getBool(
        "Use generic preselection for matching?\nYes=faster, No=more thorough"
    )

    optimize = Metashape.app.getBool("Optimize cameras after transfer?")

    src = doc.chunks[src_idx]
    dst = doc.chunks[dst_idx]

    try:
        res = transfer_oriented_cameras_from_chunk(
            src,
            dst,
            downscale=downscale,
            generic_preselection=generic_preselection,
            optimize=optimize,
        )
        Metashape.app.messageBox(
            f"Transfer complete.\n\n"
            f"Common aligned cameras used for registration: {res['common_cameras']}\n"
            f"Cameras transferred: {res['transferred']}\n"
            f"Matched: {res['matched']}\n"
            f"Optimized: {res['optimized']}"
        )
    except Exception as e:
        Metashape.app.messageBox(f"Transfer failed:\n\n{str(e)}")


def get_alignment_stats(chunk):
    """
    Get statistics about camera alignment.

    Args:
        chunk: Metashape.Chunk

    Returns:
        dict: Statistics about aligned/unaligned cameras
    """
    aligned = []
    unaligned = []

    for camera in chunk.cameras:
        if camera.transform is None:
            unaligned.append(camera)
        else:
            aligned.append(camera)

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
    Match photos specifically for unaligned cameras.
    Resets existing matches for these cameras first.

    Args:
        chunk: Metashape.Chunk
        unaligned_cameras: List of unaligned cameras
        downscale: Downscale factor for matching (1=full, 2=half, 4=quarter)
        generic_preselection: Use generic preselection
    """
    print(f"\nMatching {len(unaligned_cameras)} unaligned cameras...")
    print(f"Downscale: {downscale}")
    print(f"Generic preselection: {generic_preselection}")

    try:
        # Match photos for unaligned cameras
        # reset_matches=True will clear existing matches for these cameras
        chunk.matchPhotos(
            cameras=unaligned_cameras,
            downscale=downscale,
            generic_preselection=generic_preselection,
            reference_preselection=False,
            filter_mask=False,
            mask_tiepoints=False,
            keep_keypoints=True,
            reset_matches=True,  # Important: reset matches for these cameras
        )
        print("Matching complete!")
    except Exception as e:
        print(f"Matching failed: {e}")
        raise


def incremental_align_cameras(
    chunk,
    batch_size=20,
    max_iterations=10,
    optimize_each_batch=True,
    adaptive_fitting=True,
):
    """
    Incrementally align unaligned cameras to already aligned ones.

    Args:
        chunk: Metashape.Chunk
        batch_size: Number of cameras to try aligning per iteration
        max_iterations: Maximum number of iterations
        adaptive_fitting: Use adaptive camera model fitting
        optimize_each_batch: Run optimization after each successful batch

    Returns:
        dict: Results of incremental alignment
    """
    print("\n" + "=" * 70)
    print("INCREMENTAL CAMERA ALIGNMENT")
    print("=" * 70)

    initial_stats = get_alignment_stats(chunk)

    if initial_stats["aligned_count"] == 0:
        print("ERROR: No aligned cameras found!")
        print("Run initial alignment first to get at least some cameras aligned.")
        return None

    if initial_stats["unaligned_count"] == 0:
        print("All cameras are already aligned!")
        return {
            "initial_aligned": initial_stats["aligned_count"],
            "initial_unaligned": 0,
            "final_aligned": initial_stats["aligned_count"],
            "final_unaligned": 0,
            "newly_aligned": 0,
            "iterations": 0,
        }

    print("\nInitial state:")
    print(f"  Aligned cameras: {initial_stats['aligned_count']}")
    print(f"  Unaligned cameras: {initial_stats['unaligned_count']}")
    print("\nIncremental alignment settings:")
    print(f"  Batch size: {batch_size} cameras")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Adaptive fitting: {adaptive_fitting}")
    print(f"  Optimize each batch: {optimize_each_batch}")

    iteration = 0
    newly_aligned_total = 0
    unaligned_cameras = initial_stats["unaligned"].copy()

    while unaligned_cameras and iteration < max_iterations:
        iteration += 1

        print("\n" + "-" * 70)
        print(f"Iteration {iteration}:")
        print(f"  Remaining unaligned: {len(unaligned_cameras)}")

        # Select batch of cameras to align
        batch = unaligned_cameras[:batch_size]

        print(f"  Attempting to align {len(batch)} cameras...")

        # Try to align this batch
        try:
            chunk.alignCameras(
                cameras=batch, adaptive_fitting=adaptive_fitting, reset_alignment=False
            )
        except Exception as e:
            print(f"  Warning: Alignment failed - {e}")
            continue

        # Check which cameras got aligned
        newly_aligned = []
        still_unaligned = []

        for camera in batch:
            if camera.transform is not None:
                newly_aligned.append(camera)
            else:
                still_unaligned.append(camera)

        newly_aligned_count = len(newly_aligned)
        newly_aligned_total += newly_aligned_count

        print(f"  Newly aligned: {newly_aligned_count}")

        if newly_aligned_count > 0:
            # Show some camera names
            sample_names = [cam.label for cam in newly_aligned[:5]]
            print(f"  Examples: {', '.join(sample_names)}")

            if len(newly_aligned) > 5:
                print(f"  ... and {len(newly_aligned) - 5} more")

        # Update unaligned list
        unaligned_cameras = [
            cam for cam in unaligned_cameras if cam not in newly_aligned
        ]

        # If no cameras were aligned in this iteration, stop
        if newly_aligned_count == 0:
            print("\n  No cameras aligned in this iteration. Stopping.")
            break

        # Optional: Optimize after each batch
        if optimize_each_batch and newly_aligned_count > 0:
            print("  Optimizing alignment...")
            try:
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
            except Exception as e:
                print(f"  Warning: Optimization failed - {e}")

    # Final statistics
    final_stats = get_alignment_stats(chunk)

    print("\n" + "=" * 70)
    print("INCREMENTAL ALIGNMENT COMPLETE")
    print("=" * 70)
    print(f"Initial aligned: {initial_stats['aligned_count']}")
    print(f"Newly aligned: {newly_aligned_total}")
    print(f"Final aligned: {final_stats['aligned_count']}")
    print(f"Still unaligned: {final_stats['unaligned_count']}")
    print(f"Iterations performed: {iteration}")
    if initial_stats["unaligned_count"] > 0:
        print(
            f"Success rate: {newly_aligned_total / initial_stats['unaligned_count'] * 100:.1f}%"
        )

    results = {
        "initial_aligned": initial_stats["aligned_count"],
        "initial_unaligned": initial_stats["unaligned_count"],
        "final_aligned": final_stats["aligned_count"],
        "final_unaligned": final_stats["unaligned_count"],
        "newly_aligned": newly_aligned_total,
        "iterations": iteration,
        "unaligned_cameras": final_stats["unaligned"],
    }

    return results


def disable_unaligned_cameras(chunk):
    """
    Disable all unaligned cameras to exclude them from processing.

    Args:
        chunk: Metashape.Chunk

    Returns:
        int: Number of cameras disabled
    """
    stats = get_alignment_stats(chunk)

    for camera in stats["unaligned"]:
        camera.enabled = False

    print(f"\nDisabled {stats['unaligned_count']} unaligned cameras")
    return stats["unaligned_count"]


def show_alignment_statistics(chunk):
    """
    Display detailed alignment statistics.

    Args:
        chunk: Metashape.Chunk
    """
    stats = get_alignment_stats(chunk)

    print("\n" + "=" * 70)
    print("CAMERA ALIGNMENT STATISTICS")
    print("=" * 70)
    print(f"Total cameras: {stats['total']}")
    print(
        f"Aligned cameras: {stats['aligned_count']} ({stats['aligned_count'] / stats['total'] * 100:.1f}%)"
    )
    print(
        f"Unaligned cameras: {stats['unaligned_count']} ({stats['unaligned_count'] / stats['total'] * 100:.1f}%)"
    )

    # Group by sensor
    if stats["unaligned_count"] > 0:
        print("\nUnaligned cameras by sensor:")
        sensor_groups = {}
        for camera in stats["unaligned"]:
            sensor_label = camera.sensor.label if camera.sensor else "Unknown"
            if sensor_label not in sensor_groups:
                sensor_groups[sensor_label] = []
            sensor_groups[sensor_label].append(camera)

        for sensor_label, cameras in sensor_groups.items():
            print(f"  {sensor_label}: {len(cameras)} cameras")

    print("=" * 70)


def export_unaligned_camera_list(chunk, output_path):
    """
    Export list of unaligned cameras to a text file.

    Args:
        chunk: Metashape.Chunk
        output_path: Path to output text file
    """
    stats = get_alignment_stats(chunk)

    with open(output_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("UNALIGNED CAMERAS LIST\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total cameras: {stats['total']}\n")
        f.write(f"Aligned cameras: {stats['aligned_count']}\n")
        f.write(f"Unaligned cameras: {stats['unaligned_count']}\n\n")
        f.write("=" * 70 + "\n")
        f.write("UNALIGNED CAMERA NAMES\n")
        f.write("=" * 70 + "\n\n")

        for camera in stats["unaligned"]:
            f.write(f"{camera.label}\n")

    print(f"\nUnaligned camera list exported to: {output_path}")


# ============================================================================
# GUI DIALOG FUNCTIONS
# ============================================================================


def incremental_alignment_dialog():
    """
    Main dialog for incremental camera alignment with photo matching.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    stats = get_alignment_stats(chunk)

    if stats["aligned_count"] == 0:
        Metashape.app.messageBox(
            "No aligned cameras found!\n\n"
            "Run initial alignment first (Workflow -> Align Photos)\n"
            "to get at least some cameras aligned."
        )
        return

    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("All cameras are already aligned!")
        return

    # Show current status
    message = (
        f"Current alignment status:\n\n"
        f"Total cameras: {stats['total']}\n"
        f"Aligned: {stats['aligned_count']}\n"
        f"Unaligned: {stats['unaligned_count']}\n\n"
        f"This will:\n"
        f"1. Reset and rematch photos for unaligned cameras\n"
        f"2. Incrementally align them to existing cameras\n\n"
        f"Continue?"
    )

    proceed = Metashape.app.getBool(message)
    if not proceed:
        return

    # Ask for downscale for matching
    downscale = Metashape.app.getInt(
        "Enter downscale factor for photo matching:\n\n"
        "1 = Full resolution (slower, more accurate)\n"
        "2 = Half resolution (recommended)\n"
        "4 = Quarter resolution (faster)\n",
        2,
    )

    if downscale is None or downscale < 1:
        return

    # Ask if should use generic preselection
    generic_preselection = Metashape.app.getBool(
        "Use generic preselection for matching?\n\n"
        "Yes = Faster, may miss some matches\n"
        "No = Slower, more thorough"
    )

    # Ask for batch size
    batch_size = Metashape.app.getInt(
        "Enter batch size (cameras per iteration):\n\n"
        "Smaller = more conservative, slower\n"
        "Larger = more aggressive, faster\n\n"
        "Recommended: 10-50",
        20,
    )

    if batch_size is None or batch_size < 1:
        return

    # Ask for max iterations
    max_iterations = Metashape.app.getInt(
        "Enter maximum number of iterations:\n\n"
        "Stop after this many attempts even if\n"
        "some cameras remain unaligned.\n\n"
        "Recommended: 10-50",
        20,
    )

    if max_iterations is None or max_iterations < 1:
        return

    # Ask if should optimize each batch
    optimize_each_batch = Metashape.app.getBool(
        "Optimize alignment after each batch?\n\n"
        "Yes = More accurate, slower\n"
        "No = Faster, may be less stable"
    )

    try:
        # Step 1: Match photos for unaligned cameras
        print("\n" + "=" * 70)
        print("STEP 1: MATCHING PHOTOS FOR UNALIGNED CAMERAS")
        print("=" * 70)

        match_unaligned_photos(
            chunk, stats["unaligned"], downscale, generic_preselection
        )

        # Step 2: Incremental alignment
        print("\n" + "=" * 70)
        print("STEP 2: INCREMENTAL ALIGNMENT")
        print("=" * 70)

        results = incremental_align_cameras(
            chunk,
            batch_size=batch_size,
            max_iterations=max_iterations,
            optimize_each_batch=optimize_each_batch,
            adaptive_fitting=True,
        )

        if results:
            # Show results
            message = (
                f"Incremental Alignment Complete!\n\n"
                f"Initial aligned: {results['initial_aligned']}\n"
                f"Newly aligned: {results['newly_aligned']}\n"
                f"Final aligned: {results['final_aligned']}\n"
                f"Still unaligned: {results['final_unaligned']}\n"
                f"Iterations: {results['iterations']}\n\n"
            )

            if results["initial_unaligned"] > 0:
                success_rate = (
                    results["newly_aligned"] / results["initial_unaligned"] * 100
                )
                message += f"Success rate: {success_rate:.1f}%"

            Metashape.app.messageBox(message)

            # Ask what to do with remaining unaligned cameras
            if results["final_unaligned"] > 0:
                response = Metashape.app.getBool(
                    f"{results['final_unaligned']} cameras remain unaligned.\n\n"
                    f"Disable them to exclude from further processing?"
                )

                if response:
                    disable_unaligned_cameras(chunk)
                    Metashape.app.messageBox(
                        f"Disabled {results['final_unaligned']} unaligned cameras.\n\n"
                        f"You can re-enable them later from the Photos pane."
                    )
    except Exception as e:
        Metashape.app.messageBox(f"Error during incremental alignment:\n\n{str(e)}")
        print(f"\nError: {e}")


def show_alignment_stats_dialog():
    """
    Show alignment statistics dialog.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    show_alignment_statistics(chunk)

    stats = get_alignment_stats(chunk)

    message = (
        f"Camera Alignment Statistics:\n\n"
        f"Total cameras: {stats['total']}\n"
        f"Aligned: {stats['aligned_count']} ({stats['aligned_count'] / stats['total'] * 100:.1f}%)\n"
        f"Unaligned: {stats['unaligned_count']} ({stats['unaligned_count'] / stats['total'] * 100:.1f}%)\n\n"
        f"See console for detailed breakdown."
    )

    Metashape.app.messageBox(message)


def disable_unaligned_cameras_dialog():
    """
    Dialog to disable unaligned cameras.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    stats = get_alignment_stats(chunk)

    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras to disable!")
        return

    response = Metashape.app.getBool(
        f"Disable {stats['unaligned_count']} unaligned cameras?\n\n"
        f"This will exclude them from processing but\n"
        f"you can re-enable them later.\n\n"
        f"Continue?"
    )

    if response:
        count = disable_unaligned_cameras(chunk)
        Metashape.app.messageBox(f"Disabled {count} unaligned cameras.")


def export_unaligned_list_dialog():
    """
    Dialog to export unaligned camera list.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    stats = get_alignment_stats(chunk)

    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras to export!")
        return

    # Ask for output path
    output_path = Metashape.app.getSaveFileName(
        "Save unaligned camera list", filter="Text files (*.txt);;All files (*.*)"
    )

    if output_path:
        export_unaligned_camera_list(chunk, output_path)
        Metashape.app.messageBox(
            f"Exported {stats['unaligned_count']} camera names to:\n{output_path}"
        )


# ============================================================================
# INITIALIZATION
# ============================================================================


def realign_selected_cameras_dialog():
    """
    Dialog to realign selected cameras with fresh matches.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    # Get selected cameras from the GUI
    selected = [cam for cam in chunk.cameras if cam.selected]

    if not selected:
        Metashape.app.messageBox(
            "No cameras selected!\n\nPlease select cameras in the Photos pane first."
        )
        return

    # Count currently aligned
    aligned_count = sum(1 for cam in selected if cam.transform is not None)
    unaligned_count = len(selected) - aligned_count

    # Show status
    message = (
        f"Selected cameras: {len(selected)}\n"
        f"Currently aligned: {aligned_count}\n"
        f"Currently unaligned: {unaligned_count}\n\n"
        f"This will:\n"
        f"1. Reset alignment for selected cameras\n"
        f"2. Reset and rematch against ALL cameras\n"
        f"3. Realign with new matches\n\n"
        f"Continue?"
    )

    proceed = Metashape.app.getBool(message)
    if not proceed:
        return

    # Ask for matching parameters
    downscale = Metashape.app.getInt(
        "Enter downscale factor for matching:\n\n"
        "1 = Full resolution (slower, more accurate)\n"
        "2 = Half resolution (recommended)\n"
        "4 = Quarter resolution (faster)",
        2,
    )

    if downscale is None or downscale < 1:
        return

    generic_preselection = Metashape.app.getBool(
        "Use generic preselection for matching?\n\n"
        "Yes = Faster, may miss some matches\n"
        "No = Slower, more thorough"
    )

    optimize = Metashape.app.getBool(
        "Optimize cameras after realignment?\n\n"
        "Yes = More accurate, slower\n"
        "No = Faster"
    )

    try:
        results = realign_selected_cameras(
            chunk,
            selected,
            downscale=downscale,
            generic_preselection=generic_preselection,
            optimize=optimize,
        )

        if "error" in results:
            Metashape.app.messageBox(f"Realignment failed:\n\n{results['error']}")
        else:
            message = (
                f"Realignment Complete!\n\n"
                f"Successfully realigned: {results['realigned']}\n"
                f"Failed to realign: {results['failed']}\n"
                f"Optimized: {results['optimized']}\n\n"
            )

            if results["failed"] > 0:
                message += (
                    f"{results['failed']} cameras could not be realigned.\n"
                    f"They may need more overlap with other images."
                )

            Metashape.app.messageBox(message)

    except Exception as e:
        Metashape.app.messageBox(f"Error during realignment:\n\n{str(e)}")
        print(f"\nError: {e}")


def add_menu_items():
    """
    Add custom menu items to Metashape.
    """
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
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Transfer Oriented Cameras From Chunk...",
        transfer_oriented_cameras_dialog,
    )


# ============================================================================
# INITIALIZATION
# ============================================================================

label = "Custom/Incremental Alignment"
add_menu_items()

print("\n" + "=" * 70)
print("INCREMENTAL ALIGNMENT TOOLS LOADED")
print("=" * 70)
print("Available in menu: Custom -> Incremental Alignment")
print("  - Align Unaligned Cameras...")
print("  - Show Alignment Statistics")
print("  - Disable Unaligned Cameras")
print("  - Enable All Cameras")
print("  - Export Unaligned Camera List...")
print("=" * 70)
