import bpy
import sys
import os
from pathlib import Path
from mathutils import Vector

sys.path.append('/home/astin/infinigen')

# 需要修改的案例列表
cases = [
    {
        "name": "A",
        "factory": "TableDiningFactory",
        "seed": 13,
        "param": "Top Thickness",
        "new_value": 0.1,          # 原始值为0.03~0.06，增大到0.1
        "module": "infinigen.assets.objects.tables.dining_table"
    },
    {
        "name": "B",
        "factory": "TableDiningFactory",
        "seed": 2,
        "param": "Leg Diameter",
        "new_value": 0.15,          # 原始0.05~0.1之间，增大
        "module": "infinigen.assets.objects.tables.dining_table"
    },
    {
        "name": "C",
        "factory": "CeilingClassicLampFactory",
        "seed": 23,
        "param": "bottom_radius",
        "new_value": 0.5,          # 原始范围0.22-0.35，增大到0.5
        "module": "infinigen.assets.objects.lamp.ceiling_classic_lamp"
    },
    {
        "name": "D",
        "factory": "ChairFactory",
        "seed": 17,
        "param": "back_height",
        "new_value": 0.8,           # 原始0.4~0.5左右，增大
        "module": "infinigen.assets.objects.seating.chairs"
    }
]

def import_factory(module_path, factory_name):
    module = __import__(module_path, fromlist=[factory_name])
    return getattr(module, factory_name)

def setup_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def align_camera_and_light(obj):
    """自动对准相机和太阳光"""
    # 获取包围盒
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_x = min(v.x for v in bbox_corners)
    max_x = max(v.x for v in bbox_corners)
    min_y = min(v.y for v in bbox_corners)
    max_y = max(v.y for v in bbox_corners)
    min_z = min(v.z for v in bbox_corners)
    max_z = max(v.z for v in bbox_corners)
    center = Vector(((min_x+max_x)/2, (min_y+max_y)/2, (min_z+max_z)/2))
    size = max(max_x-min_x, max_y-min_y, max_z-min_z)
    distance = size * 1.5
    # 相机位置：斜前方
    camera_loc = center + Vector((distance, -distance, distance*0.8))
    # 查找或创建相机
    camera = None
    for o in bpy.data.objects:
        if o.type == 'CAMERA':
            camera = o
            break
    if camera is None:
        bpy.ops.object.camera_add()
        camera = bpy.context.object
    camera.location = camera_loc
    direction = center - camera_loc
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = camera
    # 添加太阳光
    if not any(o.type == 'LIGHT' for o in bpy.data.objects):
        bpy.ops.object.light_add(type='SUN', location=(2,2,4))
        bpy.context.object.data.energy = 2

def render_png(path):
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.filepath = str(path)
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)

def generate_asset(factory_class, seed, param_name=None, new_value=None, extra_args=None):
    """生成资产，可选择修改参数"""
    # 实例化工厂
    factory = factory_class(seed)
    # 修改参数（如果提供）
    if param_name is not None and new_value is not None:
        # 尝试修改 factory.params 字典
        if hasattr(factory, 'params') and param_name in factory.params:
            old_val = factory.params[param_name]
            factory.params[param_name] = new_value
            print(f"    修改参数 {param_name}: {old_val} -> {new_value}")
        else:
            # 如果参数不在 params 中，尝试直接设置属性
            if hasattr(factory, param_name):
                old_val = getattr(factory, param_name)
                setattr(factory, param_name, new_value)
                print(f"    修改属性 {param_name}: {old_val} -> {new_value}")
            else:
                print(f"    警告：未找到参数 {param_name}，跳过修改")
    # 生成资产（需处理特殊工厂）
    factory_name = factory.__class__.__name__
    if factory_name == "CeilingClassicLampFactory":
        placeholder = factory.create_placeholder()
        factory.create_asset(i=0, placeholder=placeholder, face_size=0.1)
        if placeholder and placeholder.name in bpy.data.objects:
            bpy.data.objects.remove(placeholder, do_unlink=True)
    elif factory_name == "MushroomFactory":
        factory.create_asset(i=0, face_size=0.1)
    else:
        factory.create_asset()
    # 获取生成的物体
    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        for o in bpy.data.objects:
            if o.type == 'MESH':
                obj = o
                break
    return obj

def process_case(case):
    print(f"\n处理案例 {case['name']}: {case['factory']} seed={case['seed']} 修改 {case['param']}")
    # 导入工厂类
    FactoryClass = import_factory(case['module'], case['factory'])
    # 输出目录
    out_dir = Path(f"task2/{case['name']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    before_blend = out_dir / "before.blend"
    after_blend = out_dir / "after.blend"
    before_png = out_dir / "before.png"
    after_png = out_dir / "after.png"

    # 1. 生成 before（不修改参数）
    print("  生成 before...")
    setup_scene()
    obj_before = generate_asset(FactoryClass, case['seed'])
    align_camera_and_light(obj_before)
    bpy.ops.wm.save_as_mainfile(filepath=str(before_blend))
    render_png(before_png)
    print(f"  已保存 before: {before_blend}, {before_png}")

    # 2. 生成 after（修改参数）
    print("  生成 after...")
    setup_scene()
    obj_after = generate_asset(FactoryClass, case['seed'], case['param'], case['new_value'])
    align_camera_and_light(obj_after)
    bpy.ops.wm.save_as_mainfile(filepath=str(after_blend))
    render_png(after_png)
    print(f"  已保存 after: {after_blend}, {after_png}")

    # 记录参数取值（写入文本文件）
    info_path = out_dir / "params.txt"
    with open(info_path, 'w') as f:
        f.write(f"Factory: {case['factory']}\n")
        f.write(f"Seed: {case['seed']}\n")
        f.write(f"Modified parameter: {case['param']}\n")
        f.write(f"New value: {case['new_value']}\n")
        # 可以记录原始值，但需要从工厂实例获取，这里留空，实际运行时可以补充
        f.write("Note: Original value can be found in the factory code or logs.\n")
    print(f"  参数记录保存至: {info_path}")

def main():
    for case in cases:
        process_case(case)
    print("\n任务二全部完成！")

if __name__ == "__main__":
    main()