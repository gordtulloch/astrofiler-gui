import numpy as np
from astropy.io import fits
from tensorflow.keras.models import load_model
from skimage.transform import resize

def denoise_image(model_path, input_fits_path, output_fits_path, target_size=(128, 128)):
    model = load_model(model_path)

    data = fits.getdata(input_fits_path)
    original_shape = data.shape
    data_resized = resize(data, target_size, preserve_range=True)
    data_norm = (data_resized - np.min(data_resized)) / (np.max(data_resized) - np.min(data_resized))
    input_data = data_norm[np.newaxis, ..., np.newaxis]

    denoised = model.predict(input_data)[0, ..., 0]
    denoised_rescaled = resize(denoised, original_shape, preserve_range=True)

    hdu = fits.PrimaryHDU(denoised_rescaled)
    hdu.writeto(output_fits_path, overwrite=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Denoise a FITS image using a trained model.")
    parser.add_argument("model_path", help="Path to the trained model")
    parser.add_argument("input_fits_path", help="Path to the noisy FITS image")
    parser.add_argument("output_fits_path", help="Path to save the denoised FITS image")
    args = parser.parse_args()

    denoise_image(args.model_path, args.input_fits_path, args.output_fits_path)
