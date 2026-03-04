# Tool to export model data from the dlb/dlp format used by Tales of Innocence R.
#
# Usage:  Run by itself without commandline arguments and it will search for PCK files
# and export raw meshes, textures as well as a .gib file.
#
# For command line options, run:
# /path/to/python3 toir_export_model.py --help
#
# Requires lib_fmtibvb.py, put in the same directory
#
# GitHub eArmada8/toir_model_tool

try:
    import struct, io, copy, json, glob, os, sys
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def transpose_4x4_mtx (mtx):
    if len(mtx) == 16:
        new_mtx = []
        new_mtx.extend([mtx[0], mtx[4], mtx[8], mtx[12]])
        new_mtx.extend([mtx[1], mtx[5], mtx[9], mtx[13]])
        new_mtx.extend([mtx[2], mtx[6], mtx[10], mtx[14]])
        new_mtx.extend([mtx[3], mtx[7], mtx[11], mtx[15]])
        return(new_mtx)
    else:
        return(mtx)
        
def read_string (f, len_ = 0x20):
    return(f.read(len_).rstrip(b'x\00').decode())

def make_fmt(uv = True, normals = True, weights = True):
    semantic_count = 0
    fmt = {'stride': '12', 'topology': 'trianglelist', 'format': 'DXGI_FORMAT_R16_UINT',\
        'elements': [{'id': str(semantic_count), 'SemanticName': 'POSITION', 'SemanticIndex': '0',\
        'Format': 'R32G32B32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': '0',\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}]}
    stride = 12 # Position only
    if uv:
        semantic_count += 1
        fmt['elements'].append({'id': str(semantic_count), 'SemanticName': 'TEXCOORD',\
        'SemanticIndex': '0', 'Format': 'R32G32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': str(stride),\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'})
        stride += 8
    if normals:
        semantic_count += 1
        fmt['elements'].append({'id': str(semantic_count), 'SemanticName': 'NORMAL',\
        'SemanticIndex': '0', 'Format': 'R32G32B32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': str(stride),\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'})
        stride += 12
    if weights:
        semantic_count += 1
        fmt['elements'].append({'id': str(semantic_count), 'SemanticName': 'BLENDINDICES',\
        'SemanticIndex': '0', 'Format': 'R8G8B8A8_UINT', 'InputSlot': '0', 'AlignedByteOffset': str(stride),\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'})
        stride += 4
        semantic_count += 1
        fmt['elements'].append({'id': str(semantic_count), 'SemanticName': 'BLENDWEIGHT',\
        'SemanticIndex': '0', 'Format': 'R32G32B32A32_FLOAT', 'InputSlot': '0', 'AlignedByteOffset': str(stride),\
        'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'})
        stride += 16
    fmt['stride'] = str(stride)
    return(fmt)

def read_hierarchy (f, offset, hierarchy = []):
    f.seek(offset)
    bone = {}
    bone['internal_id'], = struct.unpack("<I", f.read(4))
    bone['name'] = read_string(f)
    bone['matrix'] = list(struct.unpack("<16f", f.read(64)))
    child_count, child_offset = struct.unpack("<2I", f.read(8))
    bone['children'] = []
    for i in range(child_count):
        hierarchy, child_id = read_hierarchy (f, child_offset + (i * 0x6C), hierarchy)
        bone['children'].append(child_id)
    hierarchy.append(bone)
    return(hierarchy, bone['internal_id'])

# Accepts a file stream (meant to be used with BytesIO)
def read_model_file (f):
    f.seek(0,2)
    eof = f.tell()
    f.seek(0)
    magic = f.read(4)
    unk0, unk1 = struct.unpack("<2H", f.read(4))
    toc = []
    for _ in range(4): #unk0?
        toc_entry = {}
        toc_entry['num_entries'], toc_entry['offset'] = struct.unpack("<2I", f.read(8))
        toc.append(toc_entry)
    #Textures
    texture_offsets = []
    f.seek(toc[2]['offset'])
    for _ in range(toc[2]['num_entries']*2):
        tex_entry = {}
        offset, = struct.unpack("<I", f.read(4))
        texture_offsets.append(offset)
    texture_offsets.append(eof)
    texture_name_len = [texture_offsets[i+1]-texture_offsets[i] for i in range(len(texture_offsets)-1)]
    textures = []
    for i in range(toc[2]['num_entries']):
        texture = {}
        f.seek(texture_offsets[i*2])
        texture['name'] = read_string(f, len_ = texture_name_len[i*2])
        f.seek(texture_offsets[i*2+1])
        texture['meta_name'] = read_string(f, len_ = texture_name_len[i*2+1])
        textures.append(texture)
    #Materials
    materials = []
    f.seek(toc[0]['offset'])
    for i in range(toc[0]['num_entries']):
        name = read_string(f)
        vals = struct.unpack("<5i8h", f.read(36))
        tex = textures[vals[5]]['name']
        materials.append({'name': name, 'texture': tex, 'vals': vals})
    #Hierarchy
    f.seek(toc[3]['offset'])
    hierarchies = []
    for i in range(toc[3]['num_entries']): # Should always be one entry?
        hierarchy = []
        hierarchy, _ = read_hierarchy(f, toc[3]['offset'], hierarchy)
        # Fix the order of the nodes, as the recursive function appends parent nodes after child nodes
        h_ids = [x['internal_id'] for x in hierarchy]
        sorted_ids = sorted(list(set(h_ids)))
        old_to_new_ids = {sorted_ids[i]:i for i in range(len(sorted_ids))}
        new_to_old_ids = {i:sorted_ids[i] for i in range(len(sorted_ids))}
        ordered_hierarchy = []
        for j in range(len(sorted_ids)):
            ordered_hierarchy.append(hierarchy[h_ids.index(new_to_old_ids[j])])
        # Correct the children lists, to point to position (glTF) instead of internal_id
        for j in range(len(ordered_hierarchy)):
            ordered_hierarchy[j]['children'] = sorted([old_to_new_ids[x] for x in ordered_hierarchy[j]['children']])
        hierarchies.append(ordered_hierarchy)
    #Meshes
    mesh_data = []
    f.seek(toc[1]['offset'])
    for i in range(toc[1]['num_entries']):
        mesh = {}
        mesh['name'] = read_string(f)
        mesh['node'] = read_string(f)
        mesh['unk_str'] = read_string(f)
        mesh['v_count'], mesh['v_offset'], mesh['inv_mtx_count'], mesh['inv_mtx_offset'], mesh['palette_offset'] = struct.unpack("<5I", f.read(20))
        mesh['unk_matrix'] = struct.unpack("<16f", f.read(64))
        mesh['unk_floats'] = struct.unpack("<9f", f.read(36))
        mesh['i_count'], mesh['i_offset'], mesh['unk0'], mesh['unk1'], mesh['unk2'] = struct.unpack("<5I", f.read(20))
        mesh_data.append(mesh)
    meshes = []
    fmt = make_fmt()
    for i in range(len(mesh_data)):
        vb = [{'SemanticName':fmt['elements'][i]['SemanticName'], 'SemanticIndex': fmt['elements'][i]['SemanticIndex'],
            'Buffer': []} for i in range(len(fmt['elements']))]
        f.seek(mesh_data[i]['v_offset'])
        for j in range(mesh_data[i]['v_count']):
            vb[0]['Buffer'].append(list(struct.unpack("<3f", f.read(12)))) # POSITION
            vb[1]['Buffer'].append(list(struct.unpack("<2f", f.read(8))))  # TEXCOORD
            vb[2]['Buffer'].append(list(struct.unpack("<3f", f.read(12)))) # NORMAL
            f.seek(4,1) # PADDING
            vb[3]['Buffer'].append(list(struct.unpack("<4B", f.read(4)))) # BLENDINDICES
            vb[4]['Buffer'].append(list(struct.unpack("<4f", f.read(16)))) # BLENDWEIGHT
        f.seek(mesh_data[i]['inv_mtx_offset'])
        inv_mtx = [list(struct.unpack("<16f", f.read(64))) for _ in range(mesh_data[i]['inv_mtx_count'])]
        f.seek(mesh_data[i]['palette_offset'])
        palette = list(struct.unpack("<{}h".format(mesh_data[i]['inv_mtx_count']), f.read(mesh_data[i]['inv_mtx_count'] * 2)))
        sub_indices = []
        sub_indices_info = []
        f.seek(mesh_data[i]['i_offset'])
        for j in range(mesh_data[i]['i_count']):
            sub_index_info = {}
            sub_index_info['flags'], sub_index_info['num_indices'], sub_index_info['offset'] = struct.unpack("<3I", f.read(12))
             # This is a guess, another guess is (sub_index_info['flags'] & 0xF)//4, neither is clearly correct
            sub_index_info['material'] = (sub_index_info['flags'] >> 6) - 1
            sub_indices_info.append(sub_index_info)
        mesh_data[i]['sub_indices_info'] = sub_indices_info
        for j in range(mesh_data[i]['i_count']):
            f.seek(sub_indices_info[j]['offset'])
            sub_index = list(struct.unpack("<{}h".format(sub_indices_info[j]['num_indices']),
                f.read(sub_indices_info[j]['num_indices'] * 2)))
            sub_indices.append(sub_index)
        h_bones = [[x['name'] for x in y] for y in hierarchies]
        containing_h = [j for j in range(len(h_bones)) if mesh_data[i]['node'] in h_bones[j]]
        if len(containing_h) > 0:
            h_to_use = hierarchies[containing_h[0]]
            h_to_use_index = {x['internal_id']:x['name'] for x in h_to_use}
            h_id_to_use = containing_h[0]
            vgmap = {x['name']:x['internal_id'] for x in h_to_use if x['internal_id'] in palette}
            # Remap blend indices to local values instead of global (required for glTF)
            remap = {list(vgmap.values())[i]:i for i in range(len(vgmap.values()))}
            new_blend_idx = []
            for j in range(len(vb[3]['Buffer'])):
                new_blend_idx.append([remap[x] if x in remap else 0 for x in vb[3]['Buffer'][j]])
            vb[3]['Buffer'] = new_blend_idx
            named_palette = [h_to_use_index[x] for x in palette]
            vgmap = {named_palette[i]:i for i in range(len(named_palette))}  
        else:
            vgmap = {}
            h_id_to_use = 0
            named_palette = []
        submesh = {'fmt': fmt, 'ibs': sub_indices, 'vb': vb, 'inv_mtx': inv_mtx, 'vgmap': vgmap,
            'palette': named_palette, 'hierarchy': h_id_to_use}
        meshes.append(submesh)
    return (textures, materials, mesh_data, meshes, hierarchies)

def convert_format_for_gltf(dxgi_format):
    dxgi_format = dxgi_format.split('DXGI_FORMAT_')[-1]
    dxgi_format_split = dxgi_format.split('_')
    if len(dxgi_format_split) == 2:
        numtype = dxgi_format_split[1]
        vec_format = re.findall("[0-9]+",dxgi_format_split[0])
        vec_bits = int(vec_format[0])
        vec_elements = len(vec_format)
        if numtype in ['FLOAT', 'UNORM', 'SNORM']:
            componentType = 5126
            componentStride = len(re.findall('[0-9]+', dxgi_format)) * 4
            dxgi_format = "".join(['R32','G32','B32','A32','D32'][0:componentStride//4]) + "_FLOAT"
        elif numtype == 'UINT':
            if vec_bits == 32:
                componentType = 5125
                componentStride = len(re.findall('[0-9]+', dxgi_format)) * 4
            elif vec_bits == 16:
                componentType = 5123
                componentStride = len(re.findall('[0-9]+', dxgi_format)) * 2
            elif vec_bits == 8:
                componentType = 5121
                componentStride = len(re.findall('[0-9]+', dxgi_format))
        accessor_types = ["SCALAR", "VEC2", "VEC3", "VEC4"]
        accessor_type = accessor_types[len(re.findall('[0-9]+', dxgi_format))-1]
        return({'format': dxgi_format, 'componentType': componentType,\
            'componentStride': componentStride, 'accessor_type': accessor_type})
    else:
        return(False)

def convert_fmt_for_gltf(fmt):
    new_fmt = copy.deepcopy(fmt)
    stride = 0
    new_semantics = {'BLENDWEIGHT': 'WEIGHTS', 'BLENDINDICES': 'JOINTS'}
    need_index = ['WEIGHTS', 'JOINTS', 'COLOR', 'TEXCOORD']
    for i in range(len(fmt['elements'])):
        if new_fmt['elements'][i]['SemanticName'] in new_semantics.keys():
            new_fmt['elements'][i]['SemanticName'] = new_semantics[new_fmt['elements'][i]['SemanticName']]
        new_info = convert_format_for_gltf(fmt['elements'][i]['Format'])
        new_fmt['elements'][i]['Format'] = new_info['format']
        if new_fmt['elements'][i]['SemanticName'] in need_index:
            new_fmt['elements'][i]['SemanticName'] = new_fmt['elements'][i]['SemanticName'] + '_' +\
                new_fmt['elements'][i]['SemanticIndex']
        new_fmt['elements'][i]['AlignedByteOffset'] = stride
        new_fmt['elements'][i]['componentType'] = new_info['componentType']
        new_fmt['elements'][i]['componentStride'] = new_info['componentStride']
        new_fmt['elements'][i]['accessor_type'] = new_info['accessor_type']
        stride += new_info['componentStride']
    index_fmt = convert_format_for_gltf(fmt['format'])
    new_fmt['format'] = index_fmt['format']
    new_fmt['componentType'] = index_fmt['componentType']
    new_fmt['componentStride'] = index_fmt['componentStride']
    new_fmt['accessor_type'] = index_fmt['accessor_type']
    new_fmt['stride'] = stride
    return(new_fmt)

def fix_strides(submesh):
    offset = 0
    for i in range(len(submesh['vb'])):
        submesh['vb'][i]['fmt']['AlignedByteOffset'] = str(offset)
        submesh['vb'][i]['stride'] = get_stride_from_dxgi_format(submesh['vb'][i]['fmt']['Format'])
        offset += submesh['vb'][i]['stride']
    return(submesh)

def write_gltf(model_filename, materials, mesh_data, meshes, hierarchies, overwrite = False, write_binary_gltf = True):
    gltf_data = {}
    gltf_data['asset'] = { 'version': '2.0' }
    gltf_data['accessors'] = []
    gltf_data['bufferViews'] = []
    gltf_data['buffers'] = []
    gltf_data['meshes'] = []
    gltf_data['materials'] = []
    gltf_data['nodes'] = []
    gltf_data['samplers'] = []
    gltf_data['scenes'] = [{}]
    gltf_data['scenes'][0]['nodes'] = [] # Base hierarchies
    gltf_data['scene'] = 0
    gltf_data['skins'] = []
    gltf_data['textures'] = []
    giant_buffer = bytes()
    buffer_view = 0
    # Materials
    material_dict = [{'name': materials[i]['name'], 'texture': materials[i]['texture']} for i in range(len(materials))]
    texture_list = sorted(list(set([x['texture'] for x in material_dict if not x['texture'] == ''])))
    gltf_data['images'] = [{'uri':'textures/{}'.format(x)} for x in texture_list]
    for mat in material_dict:
        material = { 'name': mat['name'] }
        material['pbrMetallicRoughness'] = { 'metallicFactor' : 0.0, 'roughnessFactor' : 1.0 }
        if not mat['texture'] == '':
            sampler = { 'wrapS': 10497, 'wrapT': 10497 } # I have no idea if this setting exists
            texture = { 'source': texture_list.index(mat['texture']), 'sampler': len(gltf_data['samplers']) }
            material['pbrMetallicRoughness']['baseColorTexture'] = { 'index' : len(gltf_data['textures']), }
            gltf_data['samplers'].append(sampler)
            gltf_data['textures'].append(texture)
        gltf_data['materials'].append(material)
    material_list = [x['name'] for x in gltf_data['materials']]
    missing_textures = [x['uri'] for x in gltf_data['images'] if not os.path.exists(x['uri'])]
    if len(missing_textures) > 0:
        print("Warning:  The following textures were not found:")
        for texture in missing_textures:
            print("{}".format(texture))
    # Nodes
    for i in range(len(hierarchies)):
        base_val = len(gltf_data['nodes'])
        gltf_data['scenes'][0]['nodes'].append(base_val)
        for j in range(len(hierarchies[i])):
            g_node = {'children': [x + base_val for x in hierarchies[i][j]['children']],
                'name': hierarchies[i][j]['name']}
            if not hierarchies[i][j]['matrix'] == [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]:
                g_node['matrix'] = transpose_4x4_mtx(hierarchies[i][j]['matrix'])
            gltf_data['nodes'].append(g_node)
    for i in range(len(gltf_data['nodes'])):
        if len(gltf_data['nodes'][i]['children']) == 0 and j > 0:
            del(gltf_data['nodes'][i]['children'])
    if len(gltf_data['nodes']) == 0:
        gltf_data['nodes'].append({'children': [], 'name': 'root'})
    # Meshes
    node_list = [x['name'] for x in gltf_data['nodes']]
    for i in range(len(meshes)):
        gltf_fmt = convert_fmt_for_gltf(meshes[i]['fmt'])
        # Vertex Buffer
        primitives = []
        primitive = {"attributes":{}}
        vb_stream = io.BytesIO()
        write_vb_stream(meshes[i]['vb'], vb_stream, gltf_fmt, e='<', interleave = False)
        block_offset = len(giant_buffer)
        for element in range(len(gltf_fmt['elements'])):
            primitive["attributes"][gltf_fmt['elements'][element]['SemanticName']]\
                = len(gltf_data['accessors'])
            gltf_data['accessors'].append({"bufferView" : len(gltf_data['bufferViews']),\
                "componentType": gltf_fmt['elements'][element]['componentType'],\
                "count": len(meshes[i]['vb'][element]['Buffer']),\
                "type": gltf_fmt['elements'][element]['accessor_type']})
            if gltf_fmt['elements'][element]['SemanticName'] == 'POSITION':
                gltf_data['accessors'][-1]['max'] =\
                    [max([x[0] for x in meshes[i]['vb'][element]['Buffer']]),\
                     max([x[1] for x in meshes[i]['vb'][element]['Buffer']]),\
                     max([x[2] for x in meshes[i]['vb'][element]['Buffer']])]
                gltf_data['accessors'][-1]['min'] =\
                    [min([x[0] for x in meshes[i]['vb'][element]['Buffer']]),\
                     min([x[1] for x in meshes[i]['vb'][element]['Buffer']]),\
                     min([x[2] for x in meshes[i]['vb'][element]['Buffer']])]
            gltf_data['bufferViews'].append({"buffer": 0,\
                "byteOffset": block_offset,\
                "byteLength": len(meshes[i]['vb'][element]['Buffer']) *\
                gltf_fmt['elements'][element]['componentStride'],\
                "target" : 34962})
            block_offset += len(meshes[i]['vb'][element]['Buffer']) *\
                gltf_fmt['elements'][element]['componentStride']
        vb_stream.seek(0)
        giant_buffer += vb_stream.read()
        vb_stream.close()
        del(vb_stream)
        # Index Buffers
        for j in range(len(meshes[i]['ibs'])):
            current_primitive = copy.deepcopy(primitive)
            ib_stream = io.BytesIO()
            write_ib_stream(meshes[i]['ibs'][j], ib_stream, gltf_fmt, e='<')
            # IB is 16-bit so can be misaligned, unlike VB
            while (ib_stream.tell() % 4) > 0:
                ib_stream.write(b'\x00')
            current_primitive["indices"] = len(gltf_data['accessors'])
            gltf_data['accessors'].append({"bufferView" : len(gltf_data['bufferViews']),\
                "componentType": gltf_fmt['componentType'],\
                "count": len(meshes[i]['ibs'][j]),\
                "type": gltf_fmt['accessor_type']})
            gltf_data['bufferViews'].append({"buffer": 0,\
                "byteOffset": len(giant_buffer),\
                "byteLength": ib_stream.tell(),\
                "target" : 34963})
            ib_stream.seek(0)
            giant_buffer += ib_stream.read()
            ib_stream.close()
            del(ib_stream)
            current_primitive["mode"] = 4 #TRIANGLES
            current_primitive["material"] = mesh_data[i]['sub_indices_info'][j]['material']
            primitives.append(current_primitive)
        # Mesh Node
        if mesh_data[i]['node'] in node_list:
            mesh_node = node_list.index(mesh_data[i]['node'])
            gltf_data['nodes'][mesh_node]['mesh'] = len(gltf_data['meshes'])
        else: # Add new node
            mesh_node = len(gltf_data['nodes'])
            gltf_data['nodes'][0]['children'].append(mesh_node)
            gltf_data['nodes'].append({'name': mesh_data[i]['name'], 'mesh': len(gltf_data['meshes'])})
        gltf_data['meshes'].append({"primitives": primitives, "name": mesh_data[i]['name']})
        # Skinning
        #if weights == True:
        if 1:
            joints = [node_list.index(x) for x in meshes[i]['palette']]
            bind_matrix_buffer = bytearray()
            for j in range(len(meshes[i]['inv_mtx'])):
                bind_matrix_buffer.extend(struct.pack("<16f", *transpose_4x4_mtx(meshes[i]['inv_mtx'][j])))
            gltf_data['nodes'][mesh_node]['skin'] = len(gltf_data['skins'])
            gltf_data['skins'].append({"inverseBindMatrices": len(gltf_data['accessors']),
                "joints": joints})
            gltf_data['accessors'].append({"bufferView" : len(gltf_data['bufferViews']),
                "componentType": 5126,
                "count": len(meshes[i]['inv_mtx']),
                "type": "MAT4"})
            gltf_data['bufferViews'].append({"buffer": 0,\
                "byteOffset": len(giant_buffer),\
                "byteLength": len(bind_matrix_buffer)})
            giant_buffer += bind_matrix_buffer
    # Write GLB
    gltf_data['buffers'].append({"byteLength": len(giant_buffer)})
    if (os.path.exists(model_filename + '.gltf') or os.path.exists(model_filename + '.glb')) and (overwrite == False):
        if str(input(model_filename + ".glb/.gltf exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not (os.path.exists(model_filename + '.gltf') or os.path.exists(model_filename+ '.glb')):
        if write_binary_gltf == True:
            with open(model_filename+'.glb', 'wb') as f:
                jsondata = json.dumps(gltf_data).encode('utf-8')
                jsondata += b' ' * (4 - len(jsondata) % 4)
                f.write(struct.pack('<III', 1179937895, 2, 12 + 8 + len(jsondata) + 8 + len(giant_buffer)))
                f.write(struct.pack('<II', len(jsondata), 1313821514))
                f.write(jsondata)
                f.write(struct.pack('<II', len(giant_buffer), 5130562))
                f.write(giant_buffer)
        else:
            gltf_data['buffers'][0]["uri"] = model_filename+'.bin'
            with open(model_filename+'.bin', 'wb') as f:
                f.write(giant_buffer)
            with open(model_filename+'.gltf', 'wb') as f:
                f.write(json.dumps(gltf_data, indent=4).encode("utf-8"))

def split_files (f):
    file_data = []
    num_files, = struct.unpack("<I",f.read(4))
    f.seek(0x10)
    files = []
    for _ in range(num_files):
        file = {}
        file['offset'], file['size'] = struct.unpack("<2I", f.read(8))
        files.append(file)
    for i in range(len(files)):
        f.seek(files[i]['offset'])
        file_data.append(f.read(files[i]['size']))
    return(file_data)

def process_pck (model_filename, overwrite = False, write_binary_gltf = True):
    print("Processing {}...".format(model_filename))
    with open(model_filename, 'rb') as f:
        file_data = split_files(f)
    with io.BytesIO(file_data[0]) as f:
        textures, materials, mesh_data, meshes, hierarchies = read_model_file (f)
        if os.path.exists(model_filename[:-4]) and (os.path.isdir(model_filename[:-4])) and (overwrite == False):
            if str(input(model_filename[:-4] + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(model_filename[:-4]):
            if not os.path.exists(model_filename[:-4]):
                os.mkdir(model_filename[:-4])
            open(model_filename[:-4] + '/image_info.json','wb').write(json.dumps(textures, indent=4).encode())
            open(model_filename[:-4] + '/material_info.json','wb').write(json.dumps(materials, indent=4).encode())
            open(model_filename[:-4] + '/mesh_info.json','wb').write(json.dumps(mesh_data, indent=4).encode())
            open(model_filename[:-4] + '/skeleton_info.json','wb').write(json.dumps(hierarchies, indent=4).encode())
            for i in range(len(meshes)):
                for j in range(len(meshes[i]['ibs'])):
                    len(meshes[i]['ibs'][j])
                    unique_verts = sorted(list(set(meshes[i]['ibs'][j])))
                    old_to_new = {unique_verts[k]:k for k in range(len(unique_verts))}
                    ib = [old_to_new[x] for x in meshes[i]['ibs'][j]]
                    vb = [{'SemanticName':meshes[i]['fmt']['elements'][i]['SemanticName'],
                        'SemanticIndex': meshes[i]['fmt']['elements'][i]['SemanticIndex'],
                        'Buffer': []} for i in range(len(meshes[i]['fmt']['elements']))]
                    for k in range(len(unique_verts)):
                        vb[0]['Buffer'].append(meshes[i]['vb'][0]['Buffer'][unique_verts[k]])
                        vb[1]['Buffer'].append(meshes[i]['vb'][1]['Buffer'][unique_verts[k]])
                        vb[2]['Buffer'].append(meshes[i]['vb'][2]['Buffer'][unique_verts[k]])
                        vb[3]['Buffer'].append(meshes[i]['vb'][3]['Buffer'][unique_verts[k]])
                        vb[4]['Buffer'].append(meshes[i]['vb'][4]['Buffer'][unique_verts[k]])
                    filename = model_filename[:-4] + "/{0:02d}_{1}_{2:02d}".format(i, mesh_data[i]['name'], j)
                    write_fmt(meshes[i]['fmt'], filename+'.fmt')
                    write_ib(ib, filename+'.ib', meshes[i]['fmt'])
                    write_vb(vb, filename+'.vb', meshes[i]['fmt'])
                    if len(meshes[i]['vgmap']) > 0:
                        open(filename+'.vgmap','wb').write(json.dumps(meshes[i]['vgmap'], indent=4).encode())
    with io.BytesIO(file_data[1]) as f:
        if not os.path.exists('textures'):
            os.mkdir('textures')
        texture_data = split_files(f)
        for i in range(len(texture_data)):
            texture_name = (textures[i]['name'] if i < len(textures)
                else 'texture_{0:02d}.tga'.format(i))
            open('textures/'+texture_name,'wb').write(texture_data[i])
    write_gltf(model_filename[:-4], materials, mesh_data, meshes, hierarchies,
        overwrite = overwrite, write_binary_gltf = write_binary_gltf)
    return

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-t', '--textformat', help="Write gltf instead of glb", action="store_false")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('pck_filename', help="Name of model pck file to export from (required).")
        args = parser.parse_args()
        if os.path.exists(args.pck_filename) and args.pck_filename[-4:].lower() == '.pck':
            process_pck(args.pck_filename, write_binary_gltf = args.textformat, overwrite = args.overwrite)
    else:
        pck_files = glob.glob('*.pck')
        for i in range(len(pck_files)):
            process_pck(pck_files[i])