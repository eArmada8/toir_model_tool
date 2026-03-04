# Tales of Innocence R mesh export
A script to get the mesh data out of the files from Tales of Innocence R (PS Vita).  The output is in .glb files, as well as .fmt/.ib/.vb/.vgmap files that are compatible with DarkStarSword Blender import plugin for 3DMigoto.  This is theoretically a work in progress since I'd like to actually mod the game, but there are quite a few hurdles to overcome and so there may never be an update for this.

## Credits:
I am as always very thankful for the dedicated reverse engineers at the Tales of ABCDE discord and Kiseki modding discord, for their brilliant work, and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
2. The output can be imported into Blender as .glb, or as raw buffers using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py (tested on commit [5fd206c](https://raw.githubusercontent.com/DarkStarSword/3d-fixes/5fd206c52fb8c510727d1d3e4caeb95dac807fb2/blender_3dmigoto.py))
3. toir_export_model.py is dependent on lib_fmtibvb.py, which must be in the same folder.  

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