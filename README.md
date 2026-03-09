# Tales of Innocence R mesh export
A script to get the mesh and texture data in and out of the model files from Tales of Innocence R (PS Vita).  The output is in .glb files, as well as .fmt/.ib/.vb/.vgmap files that are compatible with DarkStarSword Blender import plugin for 3DMigoto.  A glTF file is also exported for purposes of weight painting, but the glTF file is not used for modding.

## Credits:
I am as always very thankful for the dedicated reverse engineers at the Tales of ABCDE discord and Kiseki modding discord, for their brilliant work, and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
2. The output can be imported into Blender as .glb, or as raw buffers using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py (tested on commit [5fd206c](https://raw.githubusercontent.com/DarkStarSword/3d-fixes/5fd206c52fb8c510727d1d3e4caeb95dac807fb2/blender_3dmigoto.py))
3. toir_export_model.py is dependent on lib_fmtibvb.py, which must be in the same folder.  toir_import_model.py is dependent on both toir_export_model.py and lib_fmtibvb.py, which again must be in the same folder.
4. The model files are stored in toidata_release.l7c.  Extract files and insert files with [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2).

## Usage:
### toir_export_model.py
Double click the python script and it will process all the .pck files in the folder and extract the models and textures.  Do not place any non-model .pck files, as the script will likely crash.  Also, at this time only character models have been tested; support for weapons, maps, etc have yet to be implemented.

**Command line arguments:**
`toir_export_model.py [-h] [-t] [-o] pck_filename`

`-t, --textformat`
Output .gltf/.bin format instead of .glb format.

`-h, --help`
Shows help message.

`-o, --overwrite`
Overwrite existing files without prompting.

### toir_import_model.py
Double click the python script and it will search the current folder for all .pck files with exported folders, and import the meshes in the folder back into the .pck files.  It will parse the 4 JSON files (`image_info.json`, `material_info.json`, `mesh_info.json` and `skeleton_info.json`) and use that information to rebuild the model sections.  It will pack in the require textures from the `textures` folder, using the original filenames specified in `image_info.json` in the model folder.  This script requires a working .pck file already be present as it does not reconstruct the entire file; only the known relevant sections (model and textures).  The remaining parts of the file are copied unaltered from the intact .pck file.

It will make a backup of the originals, then overwrite the originals.  It will not overwrite backups; for example if "model.pck.bak" already exists, then it will write the backup to "model.pck.bak1", then to "model.pck.bak2", and so on.

*NOTE:* Newer versions of the Blender plugin export .vb0 files instead of .vb files.  Do not attempt to rename .vb0 files to .vb files, just leave them as-is and the scripts will look for the correct file.

**Command line arguments:**
`toir_import_model.py [-h] model_filename`

`-h, --help`
Shows help message.