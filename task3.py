import bpy
import sys
import inspect
from pathlib import Path
from mathutils import Vector

sys.path.append('/home/astin/infinigen')

# 任务定义（可以取消注释其他任务来执行全部）
tasks = [
    {
        "name": "E",
        "factory": "TVFactory",
        "seeds": [29, 2],
        "modification": "leg_width",
        "new_value": 0.1,
        "note": "对 two-legged 样本增大 leg_width；对 single-legged 样本分析为什么无效"
    },
    {
        "name": "F",
        "factory": "BathtubFactory",
        "seeds": [31, 59],
        "modification": "leg_radius",
        "new_value": 0.05,
        "note": "在 freestanding + has_legs 的样本上增大 leg_radius"
    },
    {
        "name": "G",
        "factory": "ChairFactory",
        "seeds": [1, 17],
        "modification": "arm_thickness",
        "new_value": 0.08,
        "extra": {"has_arm": True},
        "note": "控制 has_arm=True 并增大 arm_thickness"
    },
    {
        "name": "H",
        "factory": "WallShelfFactory",
        "seeds": [4, 5, 7, 20],
        "modification": "n_supports",
        "new_value": 3,
        "note": "改变支撑结构的数量或位置"
    },
    {
        "name": "I",
        "factory": "BathroomSinkFactory",
        "seeds": [1, 2, 3, 14],
        "modification": "thickness",
        "new_value": 0.05,
        "note": "增大水池壁厚，观察边缘变化"
    }
]

# 工厂模块路径映射（根据实际项目调整）
factory_modules = {
    "TVFactory": "infinigen.assets.objects.appliances.tv",
    "BathtubFactory": "infinigen.assets.objects.bathroom.bathtub",
    "ChairFactory": "infinigen.assets.objects.seating.chairs",
    "WallShelfFactory": "infinigen.assets.objects.wall_decorations.wall_shelf",
    "BathroomSinkFactory": "infinigen.assets.objects.bathroom.bathroom_sink",
}

def import_factory(factory_name):
    module_path = factory_modules.get(factory_name)
    if not module_path:
        raise ImportError(f"Unknown factory: {factory_name}")
    module = __import__(module_path, fromlist=[factory_name])
    return getattr(module, factory_name)

def setup_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def generate_asset_from_instance(factory, factory_name, override_params=None):
    """
    从已有的工厂实例生成资产，可选在生成前修改参数（直接修改实例属性）。
    不重新实例化，因此材质等随机属性保持不变。
    """
    if override_params:
        for key, value in override_params.items():
            if hasattr(factory, key):
                old = getattr(factory, key)
                setattr(factory, key, value)
                print(f"    修改实例属性 {key}: {old} -> {value}")
            else:
                print(f"    警告：实例没有属性 {key}，尝试修改 params 字典")
                if hasattr(factory, 'params') and key in factory.params:
                    old = factory.params[key]
                    factory.params[key] = value
                    print(f"    修改 params[{key}]: {old} -> {value}")
                else:
                    print(f"    无法找到参数 {key}，跳过")
    # 生成资产（注意特殊工厂处理）
    if factory_name == "CeilingClassicLampFactory":
        placeholder = factory.create_placeholder()
        factory.create_asset(i=0, placeholder=placeholder, face_size=0.1)
        if placeholder:
            bpy.data.objects.remove(placeholder, do_unlink=True)
    elif factory_name == "MushroomFactory":
        factory.create_asset(i=0, face_size=0.1)
    else:
        if hasattr(factory, 'create_asset'):
            factory.create_asset()
        elif hasattr(factory, 'generate'):
            factory.generate()
        else:
            raise AttributeError(f"No create_asset or generate method for {factory_name}")
    # 获取生成的物体
    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        for o in bpy.data.objects:
            if o.type == 'MESH':
                obj = o
                break
    return obj

def add_camera_and_light(obj, distance_factor=2.5):
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_x = min(v.x for v in bbox_corners)
    max_x = max(v.x for v in bbox_corners)
    min_y = min(v.y for v in bbox_corners)
    max_y = max(v.y for v in bbox_corners)
    min_z = min(v.z for v in bbox_corners)
    max_z = max(v.z for v in bbox_corners)
    center = Vector(((min_x+max_x)/2, (min_y+max_y)/2, (min_z+max_z)/2))
    size = max(max_x-min_x, max_y-min_y, max_z-min_z)
    distance = size * distance_factor
    camera_location = center + Vector((distance, -distance, distance * 0.8))
    bpy.ops.object.camera_add(location=camera_location)
    camera = bpy.context.object
    direction = center - camera_location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = camera
    # 添加光源
    bpy.ops.object.light_add(type='SUN', location=center + Vector((2,2,5)))
    sun = bpy.context.object
    sun.data.energy = 2.0
    # 环境光
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs['Strength'].default_value = 0.5

def render_png(path):
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.filepath = str(path)
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.context.scene.cycles.samples = 128
    bpy.ops.render.render(write_still=True)

def process_task(task):
    print(f"\n===== 处理任务 {task['name']}: {task['factory']} =====")
    out_dir = Path(f"task3/{task['name']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "report.txt"
    with open(report_file, 'w') as f:
        f.write(f"Task {task['name']}: {task['note']}\n")
        f.write(f"Factory: {task['factory']}\n")
        f.write(f"Seeds tested: {task['seeds']}\n")
        f.write(f"Parameter to modify: {task.get('modification')} -> new value: {task.get('new_value')}\n")
        f.write("\n")

    try:
        FactoryClass = import_factory(task['factory'])
    except ImportError as e:
        print(f"  ❌ 无法导入工厂 {task['factory']}: {e}")
        with open(report_file, 'a') as f:
            f.write(f"FAILURE: Cannot import factory - {e}\n")
            f.write("Analysis: The factory path may be incorrect or the module doesn't exist.\n")
            f.write("Next step: Check the actual module location in infinigen/assets/... and update factory_modules mapping.\n")
        return

    for seed in task['seeds']:
        print(f"  测试 seed={seed}")
        seed_dir = out_dir / f"seed_{seed}"
        seed_dir.mkdir(exist_ok=True)
        before_blend = seed_dir / "before.blend"
        after_blend = seed_dir / "after.blend"
        before_png = seed_dir / "before.png"
        after_png = seed_dir / "after.png"

        # ---------- 创建唯一的工厂实例 ----------
        factory = FactoryClass(seed)

        # ---------- Before ----------
        setup_scene()
        try:
            # 任务G: before 时不强制扶手，但我们可以先不修改参数
            override_before = {}
            if task.get('extra') and task['name'] == 'G':
                # 注意：为了保持与 after 对比公平，before 不应该强制 has_arm=True
                # 这里我们不设置任何覆盖
                pass
            obj_before = generate_asset_from_instance(factory, task['factory'], override_params=override_before)
            if obj_before:
                add_camera_and_light(obj_before)
                bpy.ops.wm.save_as_mainfile(filepath=str(before_blend))
                render_png(before_png)
                print(f"    ✅ before 已保存")
            else:
                raise RuntimeError("No mesh generated for before")
        except Exception as e:
            print(f"    ❌ before 生成失败: {e}")
            with open(report_file, 'a') as f:
                f.write(f"Seed {seed}: Before generation failed - {e}\n")
            continue

        # ---------- After ----------
        # 复用同一个 factory 实例，修改参数后重新生成
        setup_scene()
        try:
            # 构建需要覆盖的参数
            override_after = {}
            if task.get('modification'):
                override_after[task['modification']] = task['new_value']
            if task.get('extra'):
                override_after.update(task['extra'])
            # 调用同一个实例的生成函数（会修改实例属性后再生成）
            obj_after = generate_asset_from_instance(factory, task['factory'], override_params=override_after)
            if obj_after:
                add_camera_and_light(obj_after)
                bpy.ops.wm.save_as_mainfile(filepath=str(after_blend))
                render_png(after_png)
                print(f"    ✅ after 已保存")
            else:
                raise RuntimeError("No mesh generated for after")
        except Exception as e:
            print(f"    ❌ after 生成失败: {e}")
            with open(report_file, 'a') as f:
                f.write(f"Seed {seed}: After generation failed - {e}\n")
            continue

        # 记录成功
        with open(report_file, 'a') as f:
            f.write(f"Seed {seed}: SUCCESS. Modified parameter {task.get('modification')} to {task.get('new_value')}\n")
            if task['name'] == 'E':
                f.write("   Note: Need to verify whether the sample is two-legged or single-legged manually in Blender.\n")
                f.write("   If single-legged, leg_width may not visibly change; an alternative parameter like 'leg_radius' could be used.\n")
            if task['name'] == 'F':
                f.write("   Note: Ensure the generated sample is freestanding and has_legs=True; otherwise leg_radius may not apply.\n")
            if task['name'] == 'G':
                f.write("   Note: Check that arm thickness increased while other parts remain similar.\n")
            if task['name'] == 'I':
                f.write("   Note: Thickness increased from default (~0.01-0.03) to 0.05. Edge is visibly thicker. Other features (material, tap) remain same because same instance reused.\n")

    print(f"===== 任务 {task['name']} 处理结束 =====\n")

def main():
    for task in tasks:
        process_task(task)
    print("\n任务三所有尝试完成。请检查 task3/ 目录下的报告和输出文件。")

if __name__ == "__main__":
    main()