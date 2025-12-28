import math

import Metashape

from metashape_tools.utils import check_compatibility

check_compatibility(["2.0", "2.1"])


def save_sparse(
    chunk: Metashape.Chunk,
    file_path: str,
    save_color: bool = True,
    save_cov: bool = True,
    sep: str = ",",
    header: bool = True,
):
    tie_points = chunk.tie_points
    T = chunk.transform.matrix
    if (
        chunk.transform.translation
        and chunk.transform.rotation
        and chunk.transform.scale
    ):
        T = chunk.crs.localframe(T.mulp(chunk.region.center)) * T
    R = T.rotation() * T.scale()

    with open(file_path, "w") as f:
        if header:
            header = [
                "track_id",
                "x",
                "y",
                "z",
            ]
            if save_color:
                header.extend(["r", "g", "b"])
            if save_cov:
                header.extend(
                    [
                        "sX",
                        "sY",
                        "sZ",
                        "covXX",
                        "covXY",
                        "covXZ",
                        "covYY",
                        "covYZ",
                        "covZZ",
                        "var",
                    ]
                )
            f.write(f"{sep.join(header)}\n")
        for point in tie_points.points:
            if not point.valid:
                continue

            coord = point.coord
            coord = T * coord
            line = [
                point.track_id,
                coord.x,
                coord.y,
                coord.z,
            ]
            if save_color:
                track_id = point.track_id
                color = tie_points.tracks[track_id].color
                line.extend([color[0], color[1], color[2]])
            if save_cov:
                cov = point.cov
                cov = R * cov * R.t()
                u, s, v = cov.svd()
                var = math.sqrt(sum(s))  # variance vector length
                line.extend(
                    [
                        math.sqrt(cov[0, 0]),
                        math.sqrt(cov[1, 1]),
                        math.sqrt(cov[2, 2]),
                        cov[0, 0],
                        cov[0, 1],
                        cov[0, 2],
                        cov[1, 1],
                        cov[1, 2],
                        cov[2, 2],
                        var,
                    ]
                )
            f.write(f"{sep.join([str(x) for x in line])}\n")


def main():
    path = Metashape.app.getSaveFileName("Save file with marker image coordinates:")
    chunk = Metashape.app.document.chunk
    save_sparse(chunk, path)


Metashape.app.addMenuItem("Scripts/Export/Export sparse points", main)
