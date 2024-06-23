#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
0. s3에서 파일을 받아온다.
============
1. 용량 큰 파일을 for문에서 잡아올린다. (.ico 제외)
2. 리사이징으로 용량을 줄인다.
============
3. s3에 파일을 올린다.
"""
import os
from PIL import Image
import piexif
originalPath = '/usr/local/KOIN_BATCH/s3Image/' # 원본 폴더
resultPath = '/usr/local/KOIN_BATCH/s3Image/' # 대상 폴더
target_widths = [320, 640, 800, 1024, 2560] # 고정 가로 픽셀 수
def size_scaling(img, target_width):
    # 고정된 가로 픽셀 수를 기준으로 이미지 크기 조절
    if img.width > target_width:
        scaling_factor = target_width / img.width
        new_dimensions = (target_width, int(img.height * scaling_factor))
        img_resized = img.resize(new_dimensions, Image.Resampling.LANCZOS)
        return img_resized
    return None # 리사이징이 필요 없는 경우
# 메타 데이터를 활용한 회전 형태 유지
def rotate_image(img):
    try:
        exif_dict = piexif.load(img.info["exif"])
        orientation = exif_dict["0th"].pop(piexif.ImageIFD.Orientation)
        if orientation == 2:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            img = img.rotate(180)
        elif orientation == 4:
            img = img.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 5:
            img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            img = img.rotate(-90, expand=True)
        elif orientation == 7:
            img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            img = img.rotate(90, expand=True)
        return img
    except:
        return img
def createDirectory(dir):
    try:
        if not os.path.exists(dir):
            os.makedirs(dir)
    except OSError:
        print("Error: Failed to create the directory.")
for (path, dir, files) in os.walk(originalPath):
    for filename in files:
        # 이미 최적화된 파일은 스킵 (_{width}.webp로 끝나는 파일들)
        if any(filename.endswith(f"_{w}.webp") for w in target_widths):
            continue
        # 이미지 파일인 경우만 처리
        if filename.lower().endswith((
                '.jpeg', '.jpeg2000', '.jpg', '.tiff', '.gif', '.bmp', '.png', '.apng', '.tif', '.tga',
                '.j2k', '.jp2', '.dicom', '.emf', '.svg', '.wmf', '.psd', '.eps', '.cdr', '.cmx',
                '.otg', '.odg', '.webp')):
            base_filename = os.path.splitext(filename)[0]
            resultPath2 = resultPath + path.replace(originalPath, "")
            createDirectory(resultPath2)
            file = os.path.join(path, filename)
            img = Image.open(file)
            img = rotate_image(img)
            img = img.convert('RGB')
            for target_width in target_widths:
                # 원본의 width가 target_width보다 작은 경우 스킵
                if img.width <= target_width:
                    continue
                output_filename = os.path.join(resultPath2, f"{base_filename}_{target_width}.webp")
                # 이미 최적화된 이미지가 존재한다면 최적화를 진행하지 않는다
                if not os.path.exists(output_filename):
                    resized_img = size_scaling(img, target_width)
                    if resized_img: # 리사이징이 필요한 경우만 저장
                        resized_img.save(output_filename, 'WEBP') (편집됨)

