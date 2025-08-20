
🗂️ Folder Structure
Organize your dataset as follows:

project_folder/
├── bias/
├── dark/
├── flat/
└── light/
Each subfolder should contain raw or preprocessed images in a format supported by Siril (e.g., .fits, .tiff, .cr2, etc.).

🛠️ Step 1: Calibrate and Align Images with Siril
1. Place the preprocess.ssf in your working directory.
2. Launch Siril and set the working directory to project_folder.
3. Run the script: siril -s preprocess.ssf

This script performs the following:

Converts raw images to FITS
Creates master bias, dark, and flat frames
Calibrates light frames
Registers (aligns) calibrated frames
Stacks the registered frames using median combine
Saves the final result as final_result.fit

🧪 Step 2: Train the Denoising Model
1. Place multiple noisy FITS images of the same target in a folder (e.g., stacked_images/).
2. Run the training script:

This script:

Loads and normalizes all FITS images
Averages them to create a pseudo-clean target
Trains a U-Net model using noisy images as input and the average as target
Saves the trained model to denoising_model.h5

🧼 Step 3: Denoise a FITS Image
1. Place the noisy FITS image you want to denoise in a known location.
2. Run the denoising script:

This script:

Loads and normalizes the input image
Applies the trained model
Rescales and saves the denoised image as output_image.fits
