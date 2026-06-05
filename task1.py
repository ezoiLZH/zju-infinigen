import bpy
import sys
from pathlib import Path
from mathutils import Vector
from infinigen.core.util.math import FixedSeed

# 添加项目根目录到 Python 路径
sys.path.append('/home/astin/infinigen')

# 资产列表： (工厂名, [种子列表])
assets = [
    ("ChairFactory", [1, 17]),
    ("TableDiningFactory", [2, 13]),
    ("SimpleBookcaseFactory", [1, 41]),
    ("CeilingClassicLampFactory", [23, 47]),
    ("TVFactory", [29, 2]),
    ("BathtubFactory", [31, 59]),
    ("SucculentFactory", [11, 61]),
    ("MushroomFactory", [1, 2]),
]

# 工厂类到其模块路径的映射
factory_modules = {
    "ChairFactory": "infinigen.assets.objects.seating.chairs",
    "TableDiningFactory": "infinigen.assets.objects.tables.dining_table",
    "SimpleBookcaseFactory": "infinigen.assets.objects.shelves.simple_bookcase",
    "CeilingClassicLampFactory": "infinigen.assets.objects.lamp.ceiling_classic_lamp",
    "TVFactory": "infinigen.assets.objects.appliances.tv",
    "BathtubFactory": "infinigen.assets.objects.bathroom.bathtub",
    "SucculentFactory": "infinigen.assets.objects.small_plants.succulent",
    "MushroomFactory": "infinigen.assets.objects.mushroom.generate",
}

def import_factory(factory_name):
    """动态导入工厂类"""
    module_path = factory_modules.get(factory_name)
    if not module_path:
        raise ImportError(f"Unknown factory: {factory_name}")
    module = __import__(module_path, fromlist=[factory_name])
    return getattr(module, factory_name)

def setup_scene():
    """清空场景，为生成新资产做准备"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def generate_asset(factory, factory_name, seed):
    """根据工厂类型，使用正确的方式生成资产"""
    print(f"  正在生成资产...")
    
    # 特殊处理：CeilingClassicLampFactory
    if factory_name == "CeilingClassicLampFactory":
        placeholder = factory.create_placeholder()
        factory.create_asset(i=0, placeholder=placeholder, face_size=0.1)
        if placeholder and placeholder.name in bpy.data.objects:
            bpy.data.objects.remove(placeholder, do_unlink=True)
        return

    # 特殊处理：MushroomFactory
    if factory_name == "MushroomFactory":
        factory.create_asset(i=0, face_size=0.1)
        return

    # 默认处理：尝试无参调用 create_asset
    if hasattr(factory, 'create_asset'):
        factory.create_asset()
    elif hasattr(factory, 'generate'):
        factory.generate()
    else:
        raise AttributeError(f"{factory_name} does not have 'create_asset' or 'generate' method.")

def add_camera_and_light(obj, distance_factor=3):
    """
    为场景添加相机和光源，并调整相机位置使其对准物体。
    distance_factor: 距离系数，越大相机越远（默认3.5，比之前的1.5更远）
    """
    # 计算物体的包围盒中心及尺寸
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_x = min(v.x for v in bbox_corners)
    max_x = max(v.x for v in bbox_corners)
    min_y = min(v.y for v in bbox_corners)
    max_y = max(v.y for v in bbox_corners)
    min_z = min(v.z for v in bbox_corners)
    max_z = max(v.z for v in bbox_corners)
    center = Vector(((min_x+max_x)/2, (min_y+max_y)/2, (min_z+max_z)/2))
    size = max(max_x-min_x, max_y-min_y, max_z-min_z)
    distance = size * distance_factor  # 距离与物体尺寸成正比，系数调大

    # 相机位置：前侧上方 (x, -y, z)
    camera_location = center + Vector((distance, -distance, distance * 0.8))
    # 创建相机
    bpy.ops.object.camera_add(location=camera_location)
    camera = bpy.context.object
    # 让相机看向物体中心
    direction = center - camera_location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = camera

    # 添加太阳光（从上方斜照）
    bpy.ops.object.light_add(type='SUN', location=center + Vector((2, 2, 5)))
    sun = bpy.context.object
    sun.data.energy = 2.5
    # 可选：添加一个补光的环境光（通过世界材质）
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs['Strength'].default_value = 1  # 环境光强度

def render_image(output_path):
    """渲染当前场景并保存为 PNG"""
    bpy.context.scene.render.engine = 'CYCLES'  # 也可改用 'BLENDER_EEVEE' 加快速度
    bpy.context.scene.render.filepath = str(output_path)
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    # 设置渲染采样数（降低可加速，但质量稍降）
    bpy.context.scene.cycles.samples = 128
    bpy.ops.render.render(write_still=True)

def main():
    for factory_name, seeds in assets:
        print(f"处理工厂: {factory_name}")
        try:
            FactoryClass = import_factory(factory_name)
        except Exception as e:
            print(f"  ❌ 导入工厂失败: {e}")
            continue

        for seed in seeds:
            print(f"  种子: {seed}")
            setup_scene()
            try:
                with FixedSeed(seed):  # 设置固定随机种子
                    factory_instance = FactoryClass(seed)
                    generate_asset(factory_instance, factory_name, seed)

                # 获取生成的物体（第一个Mesh物体）
                obj = None
                for o in bpy.data.objects:
                    if o.type == 'MESH':
                        obj = o
                        break
                if obj is None:
                    print("    ⚠️ 未找到生成的物体，跳过渲染")
                else:
                    # 添加相机和灯光（距离较远）
                    add_camera_and_light(obj, distance_factor=3)
                    # 创建输出目录
                    output_dir = Path(f"task1/{factory_name}/seed_{seed}")
                    output_dir.mkdir(parents=True, exist_ok=True)
                    blend_path = output_dir / f"{factory_name}_{seed}.blend"
                    png_path = output_dir / f"{factory_name}_{seed}.png"
                    # 保存 blend
                    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
                    # 渲染 PNG
                    render_image(png_path)
                    print(f"    ✅ 已保存: {blend_path} 和 {png_path}")
            except Exception as e:
                print(f"    ❌ 生成失败: {e}")
                import traceback
                traceback.print_exc()

        print("-" * 30)

    print("任务一所有资产生成完毕（含渲染图）！")

if __name__ == "__main__":
    main()
