# Tool to manipulate Tales of Innocence R models in pck format.  Replaces mesh and texture sections of
# the .pck file with individual buffers previously exported.
# Usage:  Run by itself without commandline arguments and it will read only the mesh section of
# every model it finds in the folder and replace them with fmt / ib / vb files in the same named
# directory.  Additionally, it import the textures (original .tga format) in the `textures` folder.
#
# For command line options, run:
# /path/to/python3 toir_import_model.py --help
#
# Requires both toir_export_model.py and lib_fmtibvb.py, place in the same folder.
#
# GitHub eArmada8/toir_model_tool

try:
    import struct, json, shutil, glob, os, sys
    from lib_fmtibvb import *
    from toir_export_model import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def write_string (string, str_len = 0x20):
    str_ = bytearray(string.encode())
    str_.extend(b'\x00')
    while len(str_) < str_len:
        str_.extend(b'\x00')
    return(str_)

def round_up (val, align_size):
    if val % align_size == 0:
        return(val)
    else:
        return(val + (align_size - (val % align_size)))

def write_model_data_block (model_filename):
    def write_child_skel_block (skel_struct, i, ii, skel_block, current_offset):
        offset_locations = []
        for j in range(len(skel_struct[i][ii]['children'])):
            child = skel_struct[i][ii]['children'][j]
            skel_block.extend(struct.pack("<I", skel_struct[i][child]['internal_id']))
            skel_block.extend(write_string(skel_struct[i][child]['name'], str_len = 0x20))
            skel_block.extend(struct.pack("<16f", *skel_struct[i][child]['matrix']))
            skel_block.extend(struct.pack("<I", len(skel_struct[i][child]['children'])))
            offset_locations.append(len(skel_block))
            skel_block.extend(struct.pack("<I", 0)) # Temporary
        while len(skel_block) % 0x10:
            skel_block.extend(b'\x00')
        next_offset = current_offset + round_up(0x6C * len(skel_struct[i][ii]['children']), 0x10)
        for j in range(len(skel_struct[i][ii]['children'])):
            child = skel_struct[i][ii]['children'][j]
            if len(skel_struct[i][child]['children']) > 0:
                skel_block[offset_locations[j]:offset_locations[j]+4] = struct.pack("<I", next_offset)
            skel_block, next_offset = write_child_skel_block (skel_struct, i, skel_struct[i][ii]['children'][j], skel_block, next_offset)
        return(skel_block, next_offset)
    model_basename = model_filename[:-4]
    image_struct = json.loads(open(model_basename + '/image_info.json').read())
    material_struct = json.loads(open(model_basename + '/material_info.json').read())
    mesh_struct = json.loads(open(model_basename + '/mesh_info.json').read())
    skel_struct = json.loads(open(model_basename + '/skeleton_info.json').read())
    # Header, Materials, Mesh Data, Primary Node, Texture header
    section_sizes = [0x70, round_up((0x44 * len(material_struct)), 0x10),
        round_up((0xEC * len(mesh_struct)), 0x10), round_up(0x6C, 0x10),
        round_up(0x8 * len(image_struct), 0x10)]
    section_start = [] # Materials, Mesh Data, Primary Node, Texture header, Vertices
    section_counter = 0
    for i in range(len(section_sizes)):
        section_counter += section_sizes[i]
        section_start.append(section_counter)
    # Header
    model_data_block = bytearray()
    header = bytearray(b'IMDL')
    header.extend(struct.pack("<2h", 4, 1))
    header.extend(struct.pack("<8I", len(material_struct), section_start[0],
        len(mesh_struct), section_start[1], len(image_struct), section_start[3], 1, section_start[2]))
    while len(header) < 0x70:
        header.extend(b'\x00')
    model_data_block.extend(header)
    # Materials
    material_block = bytearray()
    for i in range(len(material_struct)):
        material_block.extend(write_string(material_struct[i]['name'], str_len = 0x20))
        material_block.extend(struct.pack("<5i8h", *material_struct[i]['vals']))
    while len(material_block) % 0x10:
        material_block.extend(b'\x00')
    model_data_block.extend(material_block)
    # Meshes
    mesh_block_start = section_start[4]
    mesh_header_block = bytearray()
    mesh_data_block = bytearray()
    skel_dict = {z['internal_id']:z['name'] for z in [x for y in skel_struct for x in y]}
    vgmap_map = {skel_dict[x]:x for x in skel_dict}
    for i in range(len(mesh_struct)):
        mesh_header_block.extend(write_string(mesh_struct[i]['name'], str_len = 0x20))
        mesh_header_block.extend(write_string(mesh_struct[i]['node'], str_len = 0x20))
        mesh_header_block.extend(write_string(mesh_struct[i]['unk_str'], str_len = 0x20))
        predicted_vgmap = {skel_dict[mesh_struct[i]['palette'][j]]:j for j in range(len(mesh_struct[i]['palette']))}
        fmt = make_fmt()
        vb = [{'SemanticName':fmt['elements'][i]['SemanticName'], 'SemanticIndex': fmt['elements'][i]['SemanticIndex'],
            'Buffer': []} for i in range(len(fmt['elements']))]
        all_ib = []
        for j in range(len(mesh_struct[i]['sub_indices_info'])):
            mesh_filename = model_filename[:-4] + "/{0:02d}_{1}_{2:02d}".format(i, mesh_struct[i]['name'], j)
            print("Processing submesh {0}...".format(mesh_filename))
            try:
                fmt_i = read_fmt(mesh_filename + '.fmt')
                ib_i = [x for y in read_ib(mesh_filename + '.ib', fmt) for x in y]
                vb_i = read_vb(mesh_filename + '.vb', fmt)
                vgmap_i = json.loads(open(mesh_filename + '.vgmap','rb').read())
                assert fmt_i == fmt
            except (FileNotFoundError, AssertionError) as err:
                print("Submesh {0} not found or corrupt, generating an empty submesh...".format(mesh_filename))
                # Generate an empty submesh
                fmt_i = fmt
                ib_i = [0,0,0]
                vb_i = [{'Buffer':[[0.0, 0.0, 0.0]]}, {'Buffer':[[0.0, 0.0]]}, {'Buffer':[[0.0, 0.0, 0.0]]},
                    {'Buffer':[[0, 0, 0, 0]]}, {'Buffer':[[1.0, 0.0, 0.0, 0.0]]}]
                vgmap_i = predicted_vgmap
            if not vgmap_i == predicted_vgmap:
                print("Warning! VGMap does not match the expected map, the model may be distorted!")
            # If the vgmap does not match the predicted map but could be rearranged, try to use it
            vgmap_map_i = {vgmap_i[x]:x for x in vgmap_i}
            if all([x in vgmap_map for x in list(vgmap_map_i.values())]) and not vgmap_i == predicted_vgmap:
                print("VGMap appears compatible for remapping, will remap.")
                vgmap_to_palette = {x:vgmap_map[vgmap_map_i[x]] for x in vgmap_map_i}
            else:
                vgmap_to_palette = {k:vgmap_map[skel_dict[mesh_struct[i]['palette'][k]]]
                    for k in range(len(mesh_struct[i]['palette']))}
            # Remap vertex groups back to internal IDs
            for k in range(len(vb_i[3]['Buffer'])):
                for l in range(len(vb_i[3]['Buffer'][k])):
                    if vb_i[4]['Buffer'][k][l] > 0.000001:
                        vb_i[3]['Buffer'][k][l] = vgmap_to_palette[vb_i[3]['Buffer'][k][l]]
            vertex_index = len(vb[0]['Buffer'])
            for k in range(len(vb)):
                vb[k]['Buffer'].extend(vb_i[k]['Buffer'])
            all_ib.append([x + vertex_index for x in ib_i])
        mesh_header_block.extend(struct.pack("<2I", len(vb[0]['Buffer']), mesh_block_start + len(mesh_data_block)))
        for j in range(len(vb[0]['Buffer'])):
            mesh_data_block.extend(struct.pack("<3f", *vb[0]['Buffer'][j]))
            mesh_data_block.extend(struct.pack("<2f", *vb[1]['Buffer'][j]))
            mesh_data_block.extend(struct.pack("<3f", *vb[2]['Buffer'][j]))
            mesh_data_block.extend(struct.pack("<4b", -1, -1, -1, -1))
            mesh_data_block.extend(struct.pack("<4B", *vb[3]['Buffer'][j]))
            mesh_data_block.extend(struct.pack("<4f", *vb[4]['Buffer'][j]))
        while len(mesh_data_block) % 0x10:
            mesh_data_block.extend(b'\x00')
        # Build matrices and palette first, so we know what their sizes are
        inv_mtx_block = bytearray()
        for j in range(len(mesh_struct[i]['inv_mtx'])):
            inv_mtx_block.extend(struct.pack("<16f", *mesh_struct[i]['inv_mtx'][j]))
        palette_block = bytearray(struct.pack("<{}h".format(len(mesh_struct[i]['palette'])),  *mesh_struct[i]['palette']))
        while len(palette_block) % 0x10:
            palette_block.extend(b'\x00')
        len_index_header_block = round_up(len(all_ib) * 0xC, 0x10)
        # Finish mesh header block
        mesh_header_block.extend(struct.pack("<3I", len(mesh_struct[i]['inv_mtx']),
            mesh_block_start + len(mesh_data_block) + len_index_header_block,
            mesh_block_start + len(mesh_data_block) + len_index_header_block + len(inv_mtx_block)))
        mesh_header_block.extend(struct.pack("<16f", *mesh_struct[i]['unk_matrix']))
        mesh_header_block.extend(struct.pack("<9f", *mesh_struct[i]['unk_floats']))
        mesh_header_block.extend(struct.pack("<5I", len(all_ib), mesh_block_start + len(mesh_data_block),
            mesh_struct[i]['unk0'], mesh_struct[i]['unk1'], mesh_struct[i]['unk2']))
        # Build indices
        index_header_block = bytearray()
        index_data_block = bytearray()
        index_data_block_offset = (mesh_block_start + len(mesh_data_block)
            + len_index_header_block + len(inv_mtx_block) + len(palette_block)) # Yeah I know this is confusing
        for j in range(len(all_ib)):
            index_header_block.extend(struct.pack("<3I", mesh_struct[i]['sub_indices_info'][j]['flags'],
                len(all_ib[j]), index_data_block_offset + len(index_data_block)))
            index_data_block.extend(struct.pack("<{}H".format(len(all_ib[j])), *all_ib[j]))
            while len(index_data_block) % 0x10:
                index_data_block.extend(b'\x00')
        while len(index_header_block) % 0x10:
            index_header_block.extend(b'\x00')
        # Attach index header block, matrices, bone palette, and indices (in that order)
        mesh_data_block.extend(index_header_block)
        mesh_data_block.extend(inv_mtx_block)
        mesh_data_block.extend(palette_block)
        mesh_data_block.extend(index_data_block)
    while len(mesh_header_block) % 0x10:
        mesh_header_block.extend(b'\x00')
    model_data_block.extend(mesh_header_block)
    # Hierarchy
    skel_header_block = bytearray()
    skel_block = bytearray()
    for i in range(len(skel_struct)):
        start_h_offset = mesh_block_start + len(mesh_data_block) + len(skel_block)
        skel_header_block.extend(struct.pack("<I", skel_struct[i][0]['internal_id']))
        skel_header_block.extend(write_string(skel_struct[i][0]['name'], str_len = 0x20))
        skel_header_block.extend(struct.pack("<16f", *skel_struct[i][0]['matrix']))
        skel_header_block.extend(struct.pack("<I", len(skel_struct[i][0]['children'])))
        skel_header_block.extend(struct.pack("<I", start_h_offset)) # Temporary
        skel_block, _ = write_child_skel_block (skel_struct, i, 0, skel_block, start_h_offset)
    while len(skel_header_block) % 0x10:
        skel_header_block.extend(b'\x00')
    model_data_block.extend(skel_header_block)
    # Textures
    tex_header_block = bytearray()
    tex_block = bytearray()
    start_t_offset = mesh_block_start + len(mesh_data_block) + len(skel_block)
    for i in range(len(image_struct)):
        tex_header_block.extend(struct.pack("<I", start_t_offset + len(tex_block)))
        tex_block.extend(write_string(image_struct[i]['name'], round_up(len(image_struct[i]['name'])+1, 0x10)))
        tex_header_block.extend(struct.pack("<I", start_t_offset + len(tex_block)))
        tex_block.extend(write_string(image_struct[i]['meta_name'], round_up(len(image_struct[i]['meta_name'])+1, 0x10)))
    while len(tex_header_block) % 0x10:
        tex_header_block.extend(b'\x00')
    model_data_block.extend(tex_header_block)
    # Data sections (meshes, skeleton, textures)
    model_data_block.extend(mesh_data_block)
    model_data_block.extend(skel_block)
    model_data_block.extend(tex_block)
    # Final alignment is probably unneeded, but just in case
    while len(model_data_block) % 0x10:
        model_data_block.extend(b'\x00')
    return(model_data_block)

def write_texture_data_block (model_filename):
    model_basename = model_filename[:-4]
    image_struct = json.loads(open(model_basename + '/image_info.json').read())
    header_block = bytearray()
    data_block = bytearray()
    header_block_size = round_up(8 * len(image_struct), 0x10) + 0x10
    header_block.extend(struct.pack("<4I", len(image_struct), 0, 0, 0))
    for i in range(len(image_struct)):
        try:
            t_data = open('textures/' + image_struct[i]['name'],'rb').read()
        except FileNotFoundError:
            input("textures/{} is missing!  Press Enter to abort.")
            raise
        header_block.extend(struct.pack("<2I", header_block_size + len(data_block), len(t_data)))
        data_block.extend(t_data)
        if i < len(image_struct) - 1:
            while len(data_block) % 0x10:
                data_block.extend(b'\x00')
    while len(header_block) % 0x10:
        header_block.extend(b'\x00')
    return(header_block+data_block)

def create_pck (model_filename):
    print("Processing {}...".format(model_filename))
    with open(model_filename, 'rb') as f:
        file_data = split_files(f)
    file_data[0] = write_model_data_block(model_filename)
    file_data[1] = write_texture_data_block(model_filename)
    header_block = bytearray()
    data_block = bytearray()
    header_block_size = 0x30
    header_block.extend(struct.pack("<4I", 4, 0, 0, 0))
    for i in range(4):
        header_block.extend(struct.pack("<2I", header_block_size + len(data_block), len(file_data[i])))
        data_block.extend(file_data[i])
        while len(data_block) % 0x10:
            data_block.extend(b'\x00')
    # Instead of overwriting backups, it will just tag a number onto the end
    backup_suffix = ''
    if os.path.exists(model_filename + '.bak' + backup_suffix):
        backup_suffix = '1'
        if os.path.exists(model_filename + '.bak' + backup_suffix):
            while os.path.exists(model_filename + '.bak' + backup_suffix):
                backup_suffix = str(int(backup_suffix) + 1)
        shutil.copy2(model_filename, model_filename + '.bak' + backup_suffix)
    else:
        shutil.copy2(model_filename, model_filename + '.bak')
    with open(model_filename,'wb') as f:
        f.write(header_block+data_block)
    return

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to import into file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('model_filename', help="Name of model (.pck) file to import into (required).")
        args = parser.parse_args()
        if os.path.exists(args.model_filename) and args.model_filename[-4:].lower() == '.pck':
            create_pck(args.model_filename)
    else:
        model_files = glob.glob('*.pck')
        model_files = [x for x in model_files if os.path.isdir(x[:-4])]
        for i in range(len(model_files)):
            create_pck(model_files[i])
