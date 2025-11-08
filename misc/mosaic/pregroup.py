import os
import shutil
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import numpy as np
from sklearn.cluster import DBSCAN

def get_image_center(fits_path):
    try:
        with fits.open(fits_path) as hdul:
            wcs = WCS(hdul[0].header)
            ny, nx = hdul[0].data.shape
            center_pixel = [nx // 2, ny // 2]
            ra_dec = wcs.pixel_to_world(center_pixel[0], center_pixel[1])
            return ra_dec.ra.deg, ra_dec.dec.deg
    except Exception as e:
        print(f"Error reading {fits_path}: {e}")
        return None

def group_images_by_panel(input_folder, output_folder, eps_deg=0.1, min_samples=1):
    image_paths = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith('.fits')]
    centers = []
    valid_paths = []

    for path in image_paths:
        center = get_image_center(path)
        if center:
            centers.append(center)
            valid_paths.append(path)

    if not centers:
        print("No valid FITS images with WCS found.")
        return
    coords = SkyCoord(ra=[c[0] for c in centers], dec=[c[1] for c in centers], unit='deg')
    xyz = np.vstack((coords.cartesian.x, coords.cartesian.y, coords.cartesian.z)).T

    clustering = DBSCAN(eps=np.sin(np.deg2rad(eps_deg)), min_samples=min_samples, metric='euclidean').fit(xyz)
    labels = clustering.labels_

    for label in set(labels):
        panel_folder = os.path.join(output_folder, f"panel_{label}")
        os.makedirs(panel_folder, exist_ok=True)
        for i, img_path in enumerate(valid_paths):
            if labels[i] == label:
                shutil.copy(img_path, panel_folder)

    print(f"Grouped {len(valid_paths)} images into {len(set(labels))} panels.")

# Example usage
if __name__ == "__main__":
    input_folder = "smart_telescope_images"
    output_folder = "grouped_panels"
    group_images_by_panel(input_folder, output_folder)
