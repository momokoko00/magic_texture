bl_info = {
    "name": "Magic Texture",
    "blender": (3, 6, 0),
    "category": "Object",
}

import bpy
import os
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty
from bpy.types import Operator, Panel

from bpy_extras.io_utils import ImportHelper

def read_image(context, filepath):
    # Placeholder for image reading logic
    bpy.ops.image.open(filepath=filepath)

def create_material(context, material_name):
    # Add a new material
    material = bpy.data.materials.new(name=material_name)
    
    # Set the material to use the Principled BSDF shader
    material.use_nodes = True
    principled_bsdf = material.node_tree.nodes.get("Principled BSDF")

    # Create a new texture node for each imported image and align them vertically
    node_spacing_y = -400  # Adjust this value for desired vertical spacing
    node_spacing_x = -600  # Adjust this value for desired horizontal spacing
    current_y = 0

    # Track whether we have found and connected an image with "Base" or "dif" in its name
    connected_base_color = False
    ao_yes = False
    normal_yes = False
    height_yes = False
    bump_yes = False
    

    for image_index, image in enumerate(bpy.data.images):
        if "normaldx" in image.name.lower():
            continue
        
        texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
        texture_node.image = image
        texture_node.location.x = principled_bsdf.location.x + node_spacing_x  # Adjust this value for horizontal spacing
        texture_node.location.y = principled_bsdf.location.y + current_y
        current_y += node_spacing_y
        
        
        # Base Color
        if "base" in image.name.lower() or "albedo" in image.name.lower() or "dif" in image.name.lower() or "color" in image.name.lower():
            material.node_tree.links.new(principled_bsdf.inputs['Base Color'], texture_node.outputs['Color'])
            connected_base_color = True
        # Metallic
        if "metalness" in image.name.lower() or "metallic" in image.name.lower():
            # Add a Gamma node and connect it to the Metallic input of Principled BSDF
            gamma_node = material.node_tree.nodes.new(type='ShaderNodeGamma')
            material.node_tree.links.new(gamma_node.inputs['Color'], texture_node.outputs['Color'])
            material.node_tree.links.new(principled_bsdf.inputs['Metallic'], gamma_node.outputs['Color'])
            texture_node.image.colorspace_settings.name = 'Non-Color'

        # Roughness
        if "rough" in image.name.lower() or "roughness" in image.name.lower():
            # Add a Color Ramp node and connect it to the Roughness input of Principled BSDF
            color_ramp_node = material.node_tree.nodes.new(type='ShaderNodeValToRGB')
            material.node_tree.links.new(color_ramp_node.inputs['Fac'], texture_node.outputs['Color'])
            material.node_tree.links.new(principled_bsdf.inputs['Roughness'], color_ramp_node.outputs['Color'])
            texture_node.image.colorspace_settings.name = 'Non-Color'    
        # Displacement 
        if "displace" in image.name.lower() or "height" in image.name.lower():
            # Add a Displacement node and connect it to the Displacement input of Material Output
            displacement_node = material.node_tree.nodes.new(type='ShaderNodeDisplacement')
            material.node_tree.links.new(displacement_node.inputs['Height'], texture_node.outputs['Color'])
            material.node_tree.links.new(material.node_tree.nodes['Material Output'].inputs['Displacement'], displacement_node.outputs['Displacement'])
            texture_node.image.colorspace_settings.name = 'Non-Color'
        # Normal 
        if "normal" in image.name.lower():
            # Add a Normal map node and connect it to the Normal input of Principled BSDF
            normal_node = material.node_tree.nodes.new(type='ShaderNodeNormalMap')
            material.node_tree.links.new(normal_node.inputs['Color'], texture_node.outputs['Color'])
            material.node_tree.links.new(principled_bsdf.inputs['Normal'], normal_node.outputs['Normal'])
            texture_node.image.colorspace_settings.name = 'Non-Color'
        # Bump
        if "bump" in image.name.lower():
            # Add a Bump node and connect it to the Normal input of Principled BSDF
            bump_node = material.node_tree.nodes.new(type='ShaderNodeBump')
            material.node_tree.links.new(bump_node.inputs['Height'], texture_node.outputs['Color'])
            material.node_tree.links.new(principled_bsdf.inputs['Normal'], bump_node.outputs['Normal'])
            texture_node.image.colorspace_settings.name = 'Non-Color'
        # AO 
        if "ao" in image.name.lower() or "ambient" in image.name.lower() or "occlusion" in image.name.lower():
            mix_color_node = material.node_tree.nodes.new(type='ShaderNodeMixRGB')
            mix_color_node.blend_type = 'MULTIPLY'
            material.node_tree.links.new(mix_color_node.inputs['Color2'], texture_node.outputs['Color'])
            texture_node.image.colorspace_settings.name = 'Non-Color'
            ao_yes= True
            
            
        # Rename the texture node to reflect the image name
        texture_node.name = f"Texture_{image.name}"
        
        albedo_keywords = ["albedo", "dif", "base", "color"]
        albedo_texture = None

        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and any(keyword in node.image.filepath.lower() for keyword in albedo_keywords):
                albedo_texture = node
                break

        # If an appropriate image texture is found, link it to the MixRGB node as Color1
        # If no image with "Base" or "dif" was found, connect albedo directly to Base Color
        if ao_yes:
            if albedo_texture and connected_base_color:
                material.node_tree.links.new(mix_color_node.inputs['Color1'], albedo_texture.outputs['Color'])
                material.node_tree.links.new(principled_bsdf.inputs['Base Color'], mix_color_node.outputs['Color'])

    return material


class OBJECT_OT_multi_image_import(Operator, ImportHelper):
    bl_idname = "object.multi_image_import"
    bl_label = "Multi-Image Import"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".png;.jpg;.jpeg;.bmp;.tif;.tiff"

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff",
        options={'HIDDEN'},
        maxlen=255,
    )

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    directory: StringProperty(
        subtype='DIR_PATH',
    )

    def execute(self, context):
        # Clear existing material and texture nodes
        selected_object = bpy.context.active_object
        if selected_object:
            if selected_object.data.materials:
                selected_object.data.materials.clear()

        # Unload existing images from memory
        for image in bpy.data.images:
            bpy.data.images.remove(image)

        # Import new images
        for current_file in self.files:
            filepath = os.path.join(self.directory, current_file.name)
            read_image(context, filepath)

        # Create a new material with imported images
        material_name = "Magic_Texture"
        material = create_material(context, material_name)

        # Assign the material to the selected object
        if selected_object:
            if selected_object.data.materials:
                # If the object already has materials, append the new material
                selected_object.data.materials.append(material)
            else:
                # If the object doesn't have any materials, assign the new material
                selected_object.data.materials.append(material)

        return {'FINISHED'}

class OBJECT_PT_multi_image_import_panel(Panel):
    bl_label = "Magic Texture"
    bl_idname = "PT_multi_image_import_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator("object.multi_image_import", text="Import Multiple Images")

def menu_func_import(self, context):
    self.layout.operator(OBJECT_OT_multi_image_import.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_multi_image_import)
    bpy.utils.register_class(OBJECT_PT_multi_image_import_panel)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_multi_image_import)
    bpy.utils.unregister_class(OBJECT_PT_multi_image_import_panel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
