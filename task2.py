import bpy
import sys
import inspect
from pathlib import Path
from mathutils import Vector
from contextlib import contextmanager
from infinigen.core.util.math import FixedSeed
import numpy as np

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

param_name = ''
old_value = 0
new_value = 0
@contextmanager
def override_assignment(cls, params_overrides={}):
    """
    临时重写 cls 的 __setattr__ 方法，以及 np.random.choice 和 np.random.uniform，
    以在工厂实例化过程中强制覆盖指定参数的赋值。
    params_overrides : dict, 如 {'leg_width': 0.1, 'has_arm': True}，用于覆盖工厂实例的属性
    """
    if params_overrides == None:
        params_overrides = {}
    original_setattr = cls.__setattr__
    def new_setattr(self, name, value):
        print(f"  尝试赋值 {name} = {value}")
        if params_overrides != None and name in params_overrides:
            print(f"        ✅成功修改属性 {name}: {value} -> {params_overrides[name]}")
            global old_value, new_value, param_name
            param_name = name
            old_value = value
            new_value = params_overrides[name]
            value = params_overrides[name]
        original_setattr(self, name, value)
    cls.__setattr__ = new_setattr

    def intercept(names):
        """获取被赋值的是哪个目标变量名"""
        print(f"    intercept called with names={names}")
        if names is None:
            return None
        # 获取上一级调用栈帧（调用随机函数的那个帧）
        frame = inspect.currentframe().f_back.f_back  # 两层：decorator -> wrapper -> caller
        if frame is None:
            return None
        # 获取源代码行
        line = inspect.getframeinfo(frame).code_context
        if not line:
            return None
        line = line[0].strip()
        # 检查是否是形如 "self.xxx = ..." 或 "xxx = ..." 的赋值语句，且左边变量名匹配
        print(f"    检查调用行: {line}")
        import re
        # 匹配模式：变量名（可能带 self.）后跟等号
        for name in names:
            pattern = rf'^\s*(?:self\.)?({name})\s*='
            if re.search(pattern, line):
                return name
        return None
    
    original_choice = np.random.choice
    original_uniform = np.random.uniform
    
    def forced_choice(a, size=None, replace=True, p=None):
        print(f"  np.random.choice called with a={a}, size={size}, replace={replace}, p={p}")
        original_result = original_choice(a, size, replace, p)   # 注意参数顺序
        if not params_overrides:
            return original_result
        name = intercept(params_overrides.keys())
        if name is not None:
            target = params_overrides[name]
            if target in a:
                print(f"        ✅成功修改属性 {name}: {original_result} -> {target}")
                global old_value, new_value, param_name
                param_name = name
                old_value = original_result
                new_value = target
                return target
            else:
                print(f"        ❌修改值不合法，合法列表：{name} -> {a}")
        return original_result
    
    def forced_uniform(low, high=None, size=None):
        # 如果赋值对象是目标，则返回目标值
        print(f"  np.random.uniform called with low={low}, high={high}, size={size}")
        original_result = original_uniform(low, high, size)
        if not params_overrides:
            return original_result
        name = intercept(params_overrides.keys())
        if name != None:
            print(f"        ✅成功修改属性 {name}: {original_result} -> {params_overrides[name]}")
            global old_value, new_value, param_name
            param_name = name
            old_value = original_result
            new_value = params_overrides[name]
            return params_overrides[name]
        return original_result
    
    np.random.choice = forced_choice
    np.random.uniform = forced_uniform

    try:
        yield
    finally:
        cls.__setattr__ = original_setattr
        np.random.choice = original_choice
        np.random.uniform = original_uniform
def generate_asset(factory_class, factory_name, seed, override_params=None):
    """
    生成资产，支持覆盖参数（通过修改 factory.params 或属性）
    override_params: dict, 如 {'leg_width': 0.1, 'has_arm': True}
    """
    try:
        with override_assignment(factory_class, params_overrides=override_params):
            with FixedSeed(seed):
                factory = factory_class(seed)
                print(f"  生成 {factory_name} seed={seed}")
                # 修改字典类参数
                if override_params != None: 
                    for name, value in override_params.items():
                        if hasattr(factory, 'params') and name in factory.params:
                            old_val = factory.params[name]
                            factory.params[name] = value
                            print(f"         ✅修改参数 {name}: {old_val} -> {value}")
                            global old_value, new_value, param_name
                            param_name = name
                            old_value = old_val
                        new_value = value
                # 处理特殊工厂
                if factory_name == "CeilingClassicLampFactory":  # 不涉及，但以防
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
        # 获取生成的物体（通常是活动物体或第一个mesh）
        obj = bpy.context.active_object
        if not obj or obj.type != 'MESH':
            for o in bpy.data.objects:
                if o.type == 'MESH':
                    obj = o
                    break
        return obj
    except Exception as e:
        import traceback
        traceback.print_exc()   # 添加这一行
        raise   # 可选，重新抛出异常

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
    sun.data.energy = 2.5
    # 环境光
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs['Strength'].default_value = 1

def render_png(path):
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.filepath = str(path)
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.context.scene.cycles.samples = 128
    bpy.ops.render.render(write_still=True)

def process_task(task):
    print(f"\n===== 处理任务 {task['name']}: {task['factory']} =====")
    out_dir = Path(f"task2/{task['name']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    # 记录分析和结果
    report_file = out_dir / "report.txt"
    with open(report_file, 'w') as f:
        f.write(f"Task {task['name']}: \n")
        f.write(f"Factory: {task['factory']}\n")
        f.write(f"seed tested: {task['seed']}\n")
        f.write(f"Parameter to modify: {task.get('param')}\n")
        f.write("\n")

    try:
        FactoryClass = import_factory(task['module'], task['factory'])
    except ImportError as e:
        print(f"  ❌ 无法导入工厂 {task['factory']}: {e}")
        with open(report_file, 'a') as f:
            f.write(f"FAILURE: Cannot import factory - {e}\n")
            f.write("Analysis: The factory path may be incorrect or the module doesn't exist.\n")
            f.write("Next step: Check the actual module location in infinigen/assets/... and update factory_modules mapping.\n")
        return

    seed = task['seed']
    print(f"  测试 seed={seed}")
    seed_dir = out_dir / f"seed_{seed}"
    seed_dir.mkdir(exist_ok=True)
    before_blend = seed_dir / "before.blend"
    after_blend = seed_dir / "after.blend"
    before_png = seed_dir / "before.png"
    after_png = seed_dir / "after.png"

    # ----- Before -----
    setup_scene()
    try:
        obj_before = generate_asset(FactoryClass, task['factory'], seed, override_params=None)
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

    # ----- After -----
    setup_scene()
    try:
        obj_after = generate_asset(FactoryClass, task['factory'], seed, override_params={task['param']: task['new_value']})
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

    # 记录成功
    with open(report_file, 'a') as f:
        global old_value, new_value, param_name
        f.write(f"Seed {seed}: SUCCESS. Modified parameter {param_name} from {old_value} to {new_value}\n")

    # 如果没有成功任何种子，再补充全局失败分析
    print(f"===== 任务 {task['name']} 处理结束 =====\n")

def main():
    for task in cases:
        process_task(task)
    print("\n任务二所有尝试完成。请检查 task2/ 目录下的报告和输出文件。")

if __name__ == "__main__":
    main()
