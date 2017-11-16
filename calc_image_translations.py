import cv2
import os
import pandas as pd
import glob
import image_registration
import json
import tqdm
import rasterio
import zipfile

def bool_from_string(s):

    if s.lower() == 'true':
        b = True
    elif s.lower() == 'false':
        b = False
    else:
        raise ValueError("Unexpected value: {}. Could not convert to boolean".format(s))

    return b


def convert_type(var, f, expected_type):

    # try to convert the inputs to correct types
    try:
        var = f(var)
    except ValueError, e:
        err = "Inputs {var} cannot be converted to type {expected_type}".format(var=var,
                                                                                expected_type=expected_type)
        raise ValueError(err)

    return var


def calc_translations(src_images, target_images, term_eps=1e-4, n_iter=1000):

    # get the target images folder
    target_images_path = os.path.dirname(target_images[0])

    results = []
    for src_image in tqdm.tqdm(src_images):

        # separate out the filename from the path
        tif_name = os.path.basename(src_image)

        # look for the file in the target images folder
        target_image = os.path.join(target_images_path, tif_name)
        if target_image not in target_images:

            print 'Warning: {} does not exist in target_images'.format(tif_name)
            results.append({'tif_name': tif_name,
                            'a'   : 1,
                            'b'   : 0,
                            'd'   : 0,
                            'e'   : 1,
                            'xoff': 0,
                            'yoff': 0})

        else:

            # do some initial checking on the input tifs and get the pixel sizes (needed later)
            with rasterio.open(src_image, 'r') as src, rasterio.open(target_image, 'r') as tgt:
                # do the crs's match?
                if src.crs <> tgt.crs:
                    raise ValueError('Source and reference raster do not have matching Coordinate Reference Systems.')

                # get the pixel sizes (x and y
                src_pixel_size_x = src.profile['transform'][0]
                src_pixel_size_y = src.profile['transform'][4] * -1

                tgt_pixel_size_x = tgt.profile['transform'][0]
                tgt_pixel_size_y = tgt.profile['transform'][4] * -1

                # make sure they match
                if abs(src_pixel_size_y-tgt_pixel_size_y) >= 1e-4:
                    err = "Source and target images for {} do not have matching pixel heights.".format(tif_name)
                    raise ValueError(err)

                if abs(src_pixel_size_x-tgt_pixel_size_x) >= 1e-4:
                    err = "Source and target images for {} do not have matching pixel widths.".format(tif_name)
                    raise ValueError(err)

                pixel_size_x = src_pixel_size_x
                pixel_size_y = tgt_pixel_size_y

            src = cv2.imread(src_image)
            ref = cv2.imread(target_image)

            # get the affine warp matrix needed to align the images
            warp_matrix = image_registration.calculate_warp_matrix(src, ref, term_eps=term_eps, n_iter=n_iter)
            # extract out the affine parameters
            a = warp_matrix[0][0]
            b = warp_matrix[0][1]
            # make sure to account for pixel size
            xoff = warp_matrix[0][2] * -1 * pixel_size_x
            d = warp_matrix[1][0]
            e = warp_matrix[1][1]
            # make sure to account for pixel size
            yoff = warp_matrix[1][2] * 1 * pixel_size_y

            results.append({'tif_name': tif_name,
                            'a': a,
                            'b': b,
                            'd': d,
                            'e': e,
                            'xoff': xoff,
                            'yoff': yoff})

    # compile results into a pandas dataframe
    df = pd.DataFrame(results)

    # return results
    return df

def main():

    # get the inputs
    input_source_images = '/mnt/work/input/source_images'
    input_target_images = '/mnt/work/input/target_images'
    string_ports = '/mnt/work/input/ports.json'

    # create output directory
    out_path = '/mnt/work/output/data'
    if os.path.exists(out_path) is False:
        os.makedirs(out_path)

    # read the inputs
    with open(string_ports) as ports:
        inputs = json.load(ports)
    n_iter = inputs.get('n_iter', '1000')
    term_eps = inputs.get('term_eps', '1e-4')
    inputs_are_zips = inputs.get('inputs_are_zips', 'false')
    # convert the inputs to the correct dtypes
    n_iter = convert_type(n_iter, int, 'Integer')
    term_eps = convert_type(term_eps, float, 'Float')
    inputs_are_zips = convert_type(inputs_are_zips, bool_from_string, 'Boolean')

    # make sure the input source images folder exists and contains tifs
    if os.path.exists(input_source_images):
        if inputs_are_zips is True:
            # get the zips
            source_zips = [os.path.join(input_source_images, t) for t in glob.glob1(input_source_images, '*.zip')]
            if len(source_zips) == 0:
                raise ValueError("No files with .zip extension found in input data port 'source_images'")
            elif len(source_zips) > 1:
                raise ValueError("Multiple files with .zip extension found in input data port 'source_images'")
            else:
                source_zip = os.path.join(input_source_images, source_zips[0])
            # unzip contents if provided as a zip
            with zipfile.ZipFile(source_zip, 'r') as z:
                z.extractall(input_source_images)
            # remove the original zip file
            os.remove(source_zip)
        # after unzipping (or if unzipping wasn't necessary), confirm that there are tifs
        source_tifs = [os.path.join(input_source_images, t) for t in glob.glob1(input_source_images, '*.tif')]
        if len(source_tifs) == 0:
            raise ValueError("No files with .tif extension found in input data port 'source_images'")
    else:
        raise Exception("Input source_images folder does not exist.")

    # make sure the input target images folder exists and contains tifs
    if os.path.exists(input_target_images):
        if inputs_are_zips is True:
            # get the zips
            target_zips = [os.path.join(input_target_images, t) for t in glob.glob1(input_target_images, '*.zip')]
            if len(target_zips) == 0:
                raise ValueError("No files with .zip extension found in input data port 'target_images'")
            elif len(target_zips) > 1:
                raise ValueError("Multiple files with .zip extension found in input data port 'target_images'")
            else:
                target_zip = os.path.join(input_target_images, target_zips[0])
            # unzip contents if provided as a zip
            with zipfile.ZipFile(target_zip, 'r') as z:
                z.extractall(input_target_images)
            # remove the original zip file
            os.remove(target_zip)
            # after unzipping (or if unzipping wasn't necessary), confirm that there are tifs
        target_tifs = [os.path.join(input_target_images, t) for t in glob.glob1(input_target_images, '*.tif')]
        if len(target_tifs) == 0:
            raise ValueError("No files with .tif extension found in input data port 'target_images'")
    else:
        raise Exception("Input target_images folder does not exist.")

    # run the processing
    df = calc_translations(source_tifs, target_tifs, term_eps, n_iter)

    out_csv = os.path.join(out_path, 'image_translations.csv')
    df.to_csv(out_csv, header=True, index=False)

    print "Image translations completed successfully."


if __name__ == '__main__':

    main()

