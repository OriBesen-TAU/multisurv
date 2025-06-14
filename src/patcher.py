"""Run offline patching from GDC slides.

Generate WSI patches and save to disk as PNG files.
"""

import os
import threading
import uuid

from PIL import Image
from wsipre import slide


class PatchGenerator(object):
    """Generator of GDC WSI patches."""

    def __init__(self, slide_files, slide_level=0, random_tissue_patch=False,
                 patch_size=(299, 299), return_annotation=False):
        """
        Parameters
        ----------
        slide_files: list of 2-tuples
            WSI and .XML annotation file path pairs.
        slide_level: int
            Slide level to get patch from.
        random_tissue_patch: bool
            Whether to get random patch from tissue regions, ignoring
            annotations.
        patch_size: 2-tuple
            Patch size.
        return_annotation: bool
            Whether to output patch annotation.
        """
        self.slide_files = slide_files
        self.slide_level = slide_level
        self.random_tissue_patch = random_tissue_patch
        self.patch_size = patch_size
        self.return_annotation = return_annotation
        self.lock = threading.Lock()
        self.reset()
        self.n = len(slide_files)

    def _get_random_patch(self, selected_slide):
        wsi_file, xml_file = selected_slide

        wsi = slide.Slide(wsi_file, xml_file, 'asap')

        # Some slides have no detected tumor regions (label list is empty)
        # Just skip them
        if not wsi.labels:
            return 'No tumor annotations found.'

        patch, annotation = wsi.read_random_patch(
            level=self.slide_level, size=self.patch_size, target_class=1,
            min_class_area_ratio=0, polygon_type='area')

        if self.return_annotation:
            return patch, annotation, os.path.basename(wsi_file)
        else:
            return patch, os.path.basename(wsi_file)

    def _get_random_tissue_patch(self, selected_slide):
        if isinstance(selected_slide, (list, tuple)):
            wsi_file, _ = selected_slide
        else:
            wsi_file = selected_slide
    
        wsi = slide.Slide(wsi_file)
        patch = wsi.read_random_tissue_patch(
            level=self.slide_level, size=self.patch_size)
    
        if patch is None:
            raise IndexError("No valid tissue patch found.")
    
        return patch, os.path.basename(wsi_file)


    def reset(self):
        """Reset generator."""
        self.i = 0

    def __next__(self):
        with self.lock:
            while self.i < self.n:
                try:
                    if self.random_tissue_patch:
                        result = self._get_random_tissue_patch(self.slide_files[self.i])
                    else:
                        result = self._get_random_patch(self.slide_files[self.i])
    
                    self.i += 1
    
                    # Check if patch was invalid (e.g. tissue not found)
                    if isinstance(result, tuple) and result[0] == 'No valid tissue pixels found.':
                        continue  # Skip and move to next slide
    
                    return result
    
                except IndexError:
                    print(f"\n[!] Skipped slide {self.i + 1}/{self.n}: no valid tissue area.")
                    self.i += 1  # Move to next slide
                except Exception as e:
                    print(f"\n[!] Skipped slide {self.i + 1}/{self.n} due to error: {e}")
                    self.i += 1  # Skip on any other error
    
            # All slides processed
            self.reset()
            raise StopIteration



class OfflinePatcher(object):
    """Run offline patching."""

    def __init__(self, slide_files, target_dir, patch_size, slide_level=0,
                 get_random_tissue_patch=False):
        self.slide_files = slide_files
        self.target_dir = target_dir
        self.patch_size = patch_size
        self.slide_level = slide_level
        self.file_format = 'png'  # to preserve pixel values (unlike JPG...)
        self.filename = None

        self.patch_gen = PatchGenerator(
            slide_files=self.slide_files, slide_level=self.slide_level,
            random_tissue_patch=get_random_tissue_patch,
            patch_size=self.patch_size)

        # Make sure target directory exists
        if not os.path.isdir(self.target_dir):
            os.makedirs(self.target_dir)

    def _compose_path(self):
        # Make sure filename is unique
        unique_id = str(uuid.uuid4().hex)[:5]
        slide_file_name = os.path.splitext(self.filename)[0]
        # Remove 2nd part of name
        slide_file_name = os.path.splitext(slide_file_name)[0]
        unique_name = slide_file_name + '_' + unique_id

        unique_name += '.' + self.file_format.lower()  # Add file extension
        path = os.path.join(self.target_dir, unique_name)

        return path

    def _save(self, path):
        """Save WSI patch to disk.

        Save image to PNG format, in order to preserve the numpy array pixel
        values. There are many options to do this:
            - matplotlib.image.imsave
            - cv2.imwrite
            - skimage.io.imsave
            - PIL.Image.fromarray(patch).save
        Decided to use PIL.
        """
        self.patch.save(path)

    def _make_patch(self):
        self.patch, self.filename = next(self.patch_gen)
        file_path = self._compose_path()
        self._save(file_path)

    def run(self, n):
        """Generate and save `n` image patches per slide."""
        print('Generating WSI patches')
        print('----------------------')
        try:
            for slide_file in self.slide_files:
                print(f"\nProcessing: {os.path.basename(slide_file)}")
                for i in range(n):
                    print(f'\r{i+1}/{n}', end='')
    
                    try:
                        if self.patch_gen.random_tissue_patch:
                            patch, self.filename = self.patch_gen._get_random_tissue_patch(slide_file)
                        else:
                            patch, self.filename = self.patch_gen._get_random_patch(slide_file)
    
                        self.patch = patch
                        file_path = self._compose_path()
                        self._save(file_path)
    
                    except Exception as e:
                        print(f"\n[!] Failed on patch {i+1} for {slide_file}: {e}")
                        break  # optional: break this slide's loop if it repeatedly fails
    
        except KeyboardInterrupt:
            file_path = self._compose_path()
            self._save(file_path)
            print("\n[!] Interrupted — last patch saved.")


        print()
