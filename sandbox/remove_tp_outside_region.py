import Metashape


def remove_tiepoints_outside_region():
    doc = Metashape.app.document
    chunk = doc.chunk
    R = chunk.region.rot  # Bounding box rotation matrix
    C = chunk.region.center  # Bounding box center vertor
    size = chunk.region.size

    for point in chunk.tie_points.points:
        if point.valid:
            v = point.coord
            v.size = 3
            v_c = v - C
            v_r = R.t() * v_c

            if abs(v_r.x) > abs(size.x / 2.0):
                point.valid = False
            elif abs(v_r.y) > abs(size.y / 2.0):
                point.valid = False
            elif abs(v_r.z) > abs(size.z / 2.0):
                point.valid = False
            else:
                continue

    print("Script finished. Points outside the region were removed.")


Metashape.app.addMenuItem(
    "Custom/Delete Points Outside Bounding Box", remove_tiepoints_outside_region
)
