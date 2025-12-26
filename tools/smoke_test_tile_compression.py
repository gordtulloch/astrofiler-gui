import os

import numpy as np
from astropy.io import fits

from astrofiler.core.compress_files import get_fits_compressor


def main() -> int:
    path = 'tmp_tile_test.fits'

    # Create a simple primary-image FITS
    arr = (np.random.rand(64, 32) * 1000).astype('float32')
    hdr = fits.Header()
    hdr['OBJECT'] = ('TEST', 'object name')
    hdr['EXPTIME'] = (12.3, 'exposure')
    fits.writeto(path, arr, header=hdr, overwrite=True)

    orig_size = os.path.getsize(path)

    comp = get_fits_compressor('astrofiler.ini')
    out_path = comp.process_file_for_compression(path)

    new_size = os.path.getsize(path)
    print('out_path:', out_path)
    print('size:', orig_size, '->', new_size)

    with fits.open(path, memmap=False) as hdul:
        comp_hdu = None
        for hdu in hdul:
            if isinstance(hdu, fits.CompImageHDU):
                comp_hdu = hdu
                break

        print('has CompImageHDU:', comp_hdu is not None)
        if comp_hdu is not None:
            # astropy presents CompImageHDU.header as an image-like view; the actual
            # FITS tile-compression keywords live in the underlying BINTABLE header.
            bt = getattr(comp_hdu, '_bintable', None)
            bt_header = bt.header if bt is not None else comp_hdu.header
            for k in ['ZIMAGE', 'ZCMPTYPE', 'ZNAXIS', 'ZBITPIX', 'ZNAXIS1', 'ZNAXIS2']:
                print(f'{k}:', bt_header.get(k))

        data = None
        for hdu in hdul:
            if getattr(hdu, 'data', None) is not None:
                data = hdu.data
                break

        print('data shape:', None if data is None else data.shape)
        print('OBJECT in primary:', hdul[0].header.get('OBJECT'))
        print('EXPTIME in primary:', hdul[0].header.get('EXPTIME'))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
