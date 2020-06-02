#!/usr/bin/env python3
from PIL import Image
import numpy
import argparse
from os import scandir, path, remove
from hashlib import md5

def get_image(image_path, ignore_size=False, target_size=None):
    """Get a numpy array of an image so that one can access values[x][y]."""
    """Credits to https://stackoverflow.com/a/27960627"""
    try:
        image = Image.open(image_path, 'r')
    except:
        print(f"Invalid file or path at : {image_path}")
        return None
    if not target_size is None:
        image = image.resize(target_size)
    width, height = image.size
    if ignore_size == False and (width != 48 or height != 48):
        print(f"Invalid image size (should be 48x48) : width {width} height {height} ({image_path})")
        return None
    if not image.mode in ['RGB']:
        print(f"Unknown mode: {image.mode} ({image_path})")
        return None
    try:
        pixel_values = numpy.array(image.getdata()).reshape((width, height, 3))
    except:
        print(f"Error while converting pixel values into an numpy array")
        return None
    return pixel_values

def get_image_hash(image_path):
    image_hash = md5()
    with open(image_path, "rb") as image:
        for chunk in iter(lambda: image.read(4096), b""):
            image_hash.update(chunk)
    return image_hash.hexdigest()

def parse_mosaic_palette(mosaic_palette):
    total_elements = len(mosaic_palette) // 2
    parsed_mosaic_palette = [numpy.empty(total_elements, dtype=object), numpy.empty((total_elements, 3), dtype=int)]
    for i in range(total_elements):
        parsed_mosaic_palette[0][i] = mosaic_palette[i * 2]
        parsed_mosaic_palette[1][i] = numpy.fromstring(mosaic_palette[i * 2 + 1], dtype=float, sep=' ')
    return parsed_mosaic_palette

def get_mosaic_palette(delete_flag):
    print("Retrieving mosaic palette...")
    if path.exists("./cache"):
        with open("./cache", "r") as cache_file:
            saved_values = [line.rstrip('\n') for line in cache_file]
    else:
        saved_values = []
    cache = list()
    with scandir("mosaics") as mosaics:
        for entry in mosaics:
            if not entry.is_file() or entry.name == ".gitkeep":
                continue
            try:
                image_hash = get_image_hash(entry.path)
                if not image_hash in saved_values:
                    pixel_values = get_image(entry.path)
                    if pixel_values is None:
                        if delete_flag == True: remove(entry.path)
                        continue
                    pixel_values = numpy.average(pixel_values.transpose(2, 0, 1).reshape(3, -1), axis=1)
                    cache.append(image_hash)
                    cache.append(f"{pixel_values[0]} {pixel_values[1]} {pixel_values[2]}")
                else:
                    cache.append(image_hash)
                    cache.append(saved_values[saved_values.index(image_hash) + 1])
            except:
                print(f"Invalid image at mosaics/{entry.name}")
    if saved_values != cache:
        with open("./cache", "w") as cache_file:
            for element in cache:
                cache_file.write(f"{element}\n")
    print("Finished retrieving mosaic palette")
    return parse_mosaic_palette(cache)

def get_image_mask(pixel_values, mosaic_palette):
    shape = pixel_values.shape[:2]
    image_mask = numpy.empty(shape, dtype=object)
    print("Retrieving image mask...")
    for x in range(shape[0]):
        for y in range(shape[1]):
            pixel_md5_index = numpy.average(numpy.abs(mosaic_palette[1] - pixel_values[x, y]), axis=1).argmin()
            image_mask[x, y] = mosaic_palette[0][pixel_md5_index]
    print("Finished retrieving of image mask")
    return image_mask

def load_used_images(image_mask):
    images_data = {}
    print("Loading used images...")
    with scandir("mosaics") as mosaics:
        for entry in mosaics:
            if not entry.is_file():
                continue
            try:
                image_hash = get_image_hash(entry.path)
                if image_hash in image_mask:
                    images_data[image_hash] = Image.open(entry.path, 'r')
            except:
                print(f"Error while loading image at : mosaics/{entry.name}")
                return None
    print("Finished loading used images")
    return images_data

def generate_image(image_mask, loaded_data):
    shape = image_mask.shape[:2]
    print("Generating final image...")
    new_image = Image.new("RGB", (48 * shape[0], 48 * shape[1]), (255, 255, 255))
    for x in range(shape[0]):
        for y in range(shape[1]):
            image_data = loaded_data.get(image_mask[x, y])
            new_image.paste(image_data, (x * 48, y * 48))
    print("Finished generating final image")
    return new_image

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Transform images into mosaic filled images')
    parser.add_argument('image_path', type=str, help='path where is stored the image you want to process')
    parser.add_argument('-o', dest='save_path', type=str, action='store', default=None, help='destination where you want to save the result (default only preview the image)')
    parser.add_argument('-r', dest='resize', type=str, action='store', default=None, help='size in format \'width,height\' which the first image will be resized')
    parser.add_argument('-d', dest='delete', action='store_const', const=True, default=False, help='delete invalid images in mosaics/')
    args = parser.parse_args()
    pixel_values = get_image(args.image_path, True, None if args.resize is None else tuple(map(int, args.resize.split(',')[:2])))
    if pixel_values is None:
        quit(1)
    mosaic_palette = get_mosaic_palette(args.delete)
    if len(mosaic_palette[0]) == 0:
        print("Please supply more than one mosaic in the mosaics folder to perform the operation")
        quit(1)
    image_mask = get_image_mask(pixel_values, mosaic_palette)
    loaded_images = load_used_images(image_mask)
    if loaded_images is None:
        quit(1)
    new_image = generate_image(image_mask, loaded_images)
    if args.save_path is None:
        new_image.show()
    else:
        new_image.save(args.save_path)
    quit(0)