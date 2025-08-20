import os
import numpy as np
from astropy.io import fits
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, UpSampling2D, concatenate
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint
from sklearn.model_selection import train_test_split
from skimage.transform import resize

def load_fits_images(directory, target_size=(128, 128)):
    images = []
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".fits"):
            filepath = os.path.join(directory, filename)
            data = fits.getdata(filepath)
            data = resize(data, target_size, preserve_range=True)
            data = (data - np.min(data)) / (np.max(data) - np.min(data))  # Normalize to [0, 1]
            images.append(data)
    return np.array(images)

def build_unet(input_shape):
    inputs = Input(input_shape)
    c1 = Conv2D(32, (3, 3), activation='relu', padding='same')(inputs)
    c1 = Conv2D(32, (3, 3), activation='relu', padding='same')(c1)
    p1 = MaxPooling2D((2, 2))(c1)

    c2 = Conv2D(64, (3, 3), activation='relu', padding='same')(p1)
    c2 = Conv2D(64, (3, 3), activation='relu', padding='same')(c2)
    p2 = MaxPooling2D((2, 2))(c2)

    c3 = Conv2D(128, (3, 3), activation='relu', padding='same')(p2)
    c3 = Conv2D(128, (3, 3), activation='relu', padding='same')(c3)

    u1 = UpSampling2D((2, 2))(c3)
    u1 = concatenate([u1, c2])
    c4 = Conv2D(64, (3, 3), activation='relu', padding='same')(u1)
    c4 = Conv2D(64, (3, 3), activation='relu', padding='same')(c4)

    u2 = UpSampling2D((2, 2))(c4)
    u2 = concatenate([u2, c1])
    c5 = Conv2D(32, (3, 3), activation='relu', padding='same')(u2)
    c5 = Conv2D(32, (3, 3), activation='relu', padding='same')(c5)

    outputs = Conv2D(1, (1, 1), activation='sigmoid')(c5)

    model = Model(inputs, outputs)
    return model

def train_model(noisy_dir_1, noisy_dir_2, model_save_path, epochs=10, batch_size=4):
    images_1 = load_fits_images(noisy_dir_1)
    images_2 = load_fits_images(noisy_dir_2)

    images_1 = images_1[..., np.newaxis]
    images_2 = images_2[..., np.newaxis]

    x_train, x_val, y_train, y_val = train_test_split(images_1, images_2, test_size=0.2, random_state=42)

    model = build_unet(input_shape=x_train.shape[1:])
    model.compile(optimizer=Adam(), loss='mean_squared_error')

    checkpoint = ModelCheckpoint(model_save_path, save_best_only=True, monitor='val_loss', mode='min')
    model.fit(x_train, y_train, validation_data=(x_val, y_val), epochs=epochs, batch_size=batch_size, callbacks=[checkpoint])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train a denoising model using noisy FITS image pairs.")
    parser.add_argument("noisy_dir_1", help="Directory containing first set of noisy FITS images")
    parser.add_argument("noisy_dir_2", help="Directory containing second set of noisy FITS images")
    parser.add_argument("model_save_path", help="Path to save the trained model")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Training batch size")
    args = parser.parse_args()

    train_model(args.noisy_dir_1, args.noisy_dir_2, args.model_save_path, args.epochs, args.batch_size)
