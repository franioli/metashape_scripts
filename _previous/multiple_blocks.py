import Metashape

# This script merges two chunks and removes duplicate images from the incoming chunk
# Duplicates are only removed if they exist in the target chunk and are already aligned


def rematch_for_block_linking(chunk, camera_group1=None, camera_group2=None,
                               downscale=1, tiepoint_limit=10000):
    """
    Re-match photos between two camera groups to improve block linking.
    Uses existing keypoints but finds new matches.

    Args:
        chunk: Metashape.Chunk
        camera_group1: First camera group name (None = all)
        camera_group2: Second camera group name (None = all)
        downscale: Matching quality (0=highest, 1=high, 2=medium)
        tiepoint_limit: Maximum tie points per image pair
    """
    print("\n=== Re-matching for Block Linking ===")

    # Option 1: Re-match specific camera groups
    if camera_group1 and camera_group2:
        # Get cameras from each group
        group1_cameras = []
        group2_cameras = []

        for cam in chunk.cameras:
            if cam.group and cam.group.label == camera_group1:
                group1_cameras.append(cam)
            elif cam.group and cam.group.label == camera_group2:
                group2_cameras.append(cam)

        print(f"Group 1 '{camera_group1}': {len(group1_cameras)} cameras")
        print(f"Group 2 '{camera_group2}': {len(group2_cameras)} cameras")

        # Match between groups
        print("\nMatching between camera groups...")
        chunk.matchPhotos(
            cameras=group1_cameras + group2_cameras,
            downscale=downscale,
            generic_preselection=False,  # Important: disable to find cross-block matches
            reference_preselection=False,  # Important: disable for merged blocks
            filter_mask=False,
            tiepoint_limit=tiepoint_limit,
            guided_matching=False,
            keep_keypoints=True,  # Reuse existing keypoints
            reset_matches=False  # Append new matches to existing ones
        )

    # Option 2: Re-match all photos with relaxed preselection
    else:
        print("\nRe-matching all photos with relaxed preselection...")
        chunk.matchPhotos(
            downscale=downscale,
            generic_preselection=False,  # Critical: allows finding new matches
            reference_preselection=False,  # Critical: allows cross-block matches
            filter_mask=False,
            tiepoint_limit=tiepoint_limit,
            guided_matching=False,
            keep_keypoints=True,  # Reuse existing keypoints
            reset_matches=False  # Append new matches
        )

    print("Re-matching complete!")


def improve_block_linking(chunk, camera_group1, camera_group2,
                         downscale=1, optimize_after=True):
    """
    Comprehensive approach to improve linking between two merged blocks.

    Args:
        chunk: Metashape.Chunk (merged chunk)
        camera_group1: Name of first camera group
        camera_group2: Name of second camera group
        downscale: Matching quality
        optimize_after: Run optimization after rematching
    """
    print("\n=== Improving Block Linking ===")

    # Step 1: Re-match with existing keypoints
    print("\nStep 1: Finding additional matches between blocks...")
    rematch_for_block_linking(chunk, camera_group1, camera_group2,
                              downscale=downscale, tiepoint_limit=10000)

    # Step 2: Optionally use guided matching for better cross-block linking
    print("\nStep 2: Guided matching for overlapping areas...")
    chunk.matchPhotos(
        downscale=downscale,
        generic_preselection=False,
        reference_preselection=False,
        guided_matching=True,  # Use existing geometry to guide matching
        keep_keypoints=True,
        reset_matches=False
    )

    # Step 3: Optimize alignment
    if optimize_after:
        print("\nStep 3: Optimizing alignment...")
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
            tiepoint_covariance=True
        )

        # Report results
        if chunk.tie_points:
            print(f"\nTotal tie points: {len(chunk.tie_points.points)}")
            print(f"Average reprojection error: {chunk.tie_points.reprojection_error:.3f} px")

    print("\n=== Block Linking Improvement Complete ===")


def merge_chunks_with_duplicate_removal(
    doc,
    source_chunk_index,
    target_chunk_index,
    source_image_group_name,
    target_image_group_name,
):
    """
    Merge two chunks while removing duplicate aligned images from the source chunk.

    Args:
        doc: Metashape.Document
        source_chunk_index: Index of the chunk to merge from (will be merged into target)
        target_chunk_index: Index of the chunk to merge into
        source_image_group_name: Name of the image group in source chunk
        target_image_group_name: Name of the image group in target chunk
    """

    if source_chunk_index >= len(doc.chunks) or target_chunk_index >= len(doc.chunks):
        print("Error: Invalid chunk indices")
        return

    source_chunk = doc.chunks[source_chunk_index]
    target_chunk = doc.chunks[target_chunk_index]

    print(f"Source chunk: {source_chunk.label}")
    print(f"Target chunk: {target_chunk.label}")

    # Find the image groups
    source_group = None
    for group in source_chunk.camera_groups:
        if group.label == source_image_group_name:
            source_group = group
            break

    target_group = None
    for group in target_chunk.camera_groups:
        if group.label == target_image_group_name:
            target_group = group
            break

    if not source_group:
        print(f"Error: Source image group '{source_image_group_name}' not found")
        return

    if not target_group:
        print(f"Error: Target image group '{target_image_group_name}' not found")
        return

    # Build a dictionary of target chunk images (path -> camera) for quick lookup
    # Only include aligned cameras from the target group
    target_images = {}
    for camera in target_chunk.cameras:
        if camera.group == target_group and camera.transform is not None:
            # Use the photo path as the key
            target_images[camera.photo.path] = camera

    print(
        f"\nTarget chunk has {len(target_images)} aligned images in group '{target_image_group_name}'"
    )

    # Find duplicates in source chunk that need to be removed
    cameras_to_remove = []
    for camera in source_chunk.cameras:
        if camera.group == source_group:
            photo_path = camera.photo.path

            # Check if this image exists in target chunk and is aligned
            if photo_path in target_images:
                if camera.transform is not None:
                    # Both are aligned - this is a duplicate, remove from source
                    cameras_to_remove.append(camera)
                    print(f"  Will remove duplicate (aligned in both): {photo_path}")
                else:
                    # Target is aligned but source is not - still remove source
                    cameras_to_remove.append(camera)
                    print(
                        f"  Will remove duplicate (aligned in target only): {photo_path}"
                    )

    # Remove the duplicate cameras from source chunk
    print(f"\nRemoving {len(cameras_to_remove)} duplicate images from source chunk...")
    source_chunk.remove(cameras_to_remove)

    print(f"Removed {len(cameras_to_remove)} duplicate images")
    print(
        f"Source chunk now has {len([c for c in source_chunk.cameras if c.group == source_group])} images in group '{source_image_group_name}'"
    )

    # Now merge the chunks
    print("\nMerging chunks...")
    target_chunk.copy(
        source_chunk,
        cameras=True,
        markers=True,
        copy_depth_maps=True,
        copy_dense_clouds=True,
        copy_models=True,
        copy_tiled_models=True,
    )

    print("Merge completed successfully!")
    print(
        f"Merged chunk '{target_chunk.label}' now has {len(target_chunk.cameras)} total cameras"
    )

    return target_chunk


# Main execution
if __name__ == "__main__":
    doc = Metashape.app.document

    if len(doc.chunks) < 2:
        print("Error: Document must have at least 2 chunks")
    else:
        # Configure these parameters according to your setup
        SOURCE_CHUNK_INDEX = 1  # Index of the chunk to merge from (0-based)
        TARGET_CHUNK_INDEX = 0  # Index of the chunk to merge into (0-based)
        SOURCE_IMAGE_GROUP_NAME = "Group2"  # Name of image group in source chunk
        TARGET_IMAGE_GROUP_NAME = "Group1"  # Name of image group in target chunk

        print("=== Metashape Chunk Merge with Duplicate Removal ===\n")

        merged_chunk = merge_chunks_with_duplicate_removal(
            doc,
            SOURCE_CHUNK_INDEX,
            TARGET_CHUNK_INDEX,
            SOURCE_IMAGE_GROUP_NAME,
            TARGET_IMAGE_GROUP_NAME,
        )

        # Improve block linking after merge
        print("\n" + "="*60)
        response = input("\nImprove linking between merged blocks? (yes/no): ")
        if response.lower() == 'yes':
            improve_block_linking(
                merged_chunk,
                TARGET_IMAGE_GROUP_NAME,
                SOURCE_IMAGE_GROUP_NAME,
                downscale=1,  # Use high quality for better cross-block matches
                optimize_after=True
            )

        print("\nDone! You may want to save your project now.")
