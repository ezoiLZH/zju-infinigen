
# Infinigen 代码能力考核实验报告

## 环境配置过程与问题解决

本次考核在 WSL2 (Ubuntu 20.04) 环境下完成。最初尝试在 Windows 原生环境中配置，遇到了以下典型问题：

1. **Git 克隆速度极慢**：使用 `ghproxy.net` 镜像加速，配置 `git config --global url."https://ghproxy.net/".insteadOf "https://github.com/"` 后解决。
2. **`pip install -r requirements.txt` 要求私有仓库**：官方文档明确指出应使用 `pip install -e .` 而非直接安装 requirements.txt，遵循文档后解决。
3. **`scikit-image` 编译失败**：Windows 下缺少 `clang-cl.exe`，改用 `conda install scikit-image` 预编译包，但 conda 又遇到 `UnicodeDecodeError`（与路径编码有关）。
4. **Blender 无法找到 conda 环境中的包**：Blender 自带 Python 解释器与 conda 环境隔离，即使通过 `sys.path.append` 也难以完全兼容。

鉴于上述问题在 Windows 上难以彻底解决，且 Infinigen 官方主要面向 Linux 环境，我转向已有的 WSL2 Ubuntu 20.04。在 WSL 中：
- 通过 `apt install` 一次性安装所有系统依赖（`libglm-dev`、`libglew-dev`、`libglfw3-dev` 等）。
- `pip install -e .` 顺利完成，包括 `python-fcl` 等需要编译的包也一次通过。
- Blender 使用 Windows 宿主机上的可执行文件，通过 `export PATH` 加入到 WSL 环境中，渲染调用正常。

至此环境准备就绪，后续所有生成均在 WSL 中完成。

---

## 1. 任务一：指定类别资产生成

### 1.1 批量生成方案

在源码中找到对应工厂对应的位置。
编写脚本 `task1.py`，使用 `blender --background --python` 执行。对每个工厂和种子：
1. 清空场景（删除默认立方体、相机、灯光）。
2. 实例化工厂，发现有的工厂生成需要特殊参数，针对 `CeilingClassicLampFactory` 和 `MushroomFactory` 的特殊接口进行适配。
3. 调用 `create_asset` 生成模型。
4. 自动添加相机（基于物体包围盒计算最佳视角）和太阳光。
5. 保存 `.blend` 文件并渲染 PNG。

### 1.2 生成结果

| 类别 | Factory | seeds | 生成文件 |
|------|---------|-------|----------|
| 椅子 | ChairFactory | 1, 17 | ![1](task1/ChairFactory/seed_1/ChairFactory_1.png) ![17](task1/ChairFactory/seed_17/ChairFactory_17.png) |
| 桌子 | TableDiningFactory | 2, 13 | ![2](task1/TableDiningFactory/seed_2/TableDiningFactory_2.png) ![13](task1/TableDiningFactory/seed_13/TableDiningFactory_13.png) |
| 书架 | SimpleBookcaseFactory | 1, 41 | ![1](task1/SimpleBookcaseFactory/seed_1/SimpleBookcaseFactory_1.png) ![41](task1/SimpleBookcaseFactory/seed_41/SimpleBookcaseFactory_41.png) |
| 灯具 | CeilingClassicLampFactory | 23, 47 | ![23](task1/CeilingClassicLampFactory/seed_23/CeilingClassicLampFactory_23.png) ![47](task1/CeilingClassicLampFactory/seed_47/CeilingClassicLampFactory_47.png) |
| 电视 | TVFactory | 29, 2 | ![29](task1/TVFactory/seed_29/TVFactory_29.png) ![2](task1/TVFactory/seed_2/TVFactory_2.png) |
| 浴缸 | BathtubFactory | 31, 59 | ![31](task1/BathtubFactory/seed_31/BathtubFactory_31.png) ![59](task1/BathtubFactory/seed_59/BathtubFactory_59.png) |
| 多肉植物 | SucculentFactory | 11, 61 | ![11](task1/SucculentFactory/seed_11/SucculentFactory_11.png) ![61](task1/SucculentFactory/seed_61/SucculentFactory_61.png) |
| 蘑菇 | MushroomFactory | 1, 2 | ![1](task1/MushroomFactory/seed_1/MushroomFactory_1.png) ![2](task1/MushroomFactory/seed_2/MushroomFactory_2.png) |

（所有文件已上传至 Hugging Face，截图详见附件）

### 1.3 对各工厂生成方式的理解

- **ChairFactory**：由坐面、靠背、椅腿、可选扶手组成。随机因素包括腿的截面形状（圆柱/方柱）、靠背高度、扶手有无、坐面轮廓。不同 seed 生成的椅子在风格上有明显差异。
- **TableDiningFactory**：桌面可为圆形或方形，桌腿数量 1‑4 根。随机参数包含桌面厚度、桌腿直径、材质等。seed 变化影响桌面形状和腿的数量。
- **CeilingClassicLampFactory**：灯罩为喇叭形曲面，由底部半径、顶部半径、高度控制。电缆长度随机。seed 主要影响灯罩的扩展程度和电缆下垂幅度。
- **TVFactory**：由屏幕和底座构成。底座分为 two‑legged 和 single‑legged 两种类型，屏幕宽高比、腿的宽度均为随机。不同 seed 下底座类型和屏幕外观会变化。
- **SucculentFactory**：多肉植物由多个叶片围绕中心旋转排列。叶片数量、大小、颜色、扭曲程度均随机，不同 seed 生成截然不同的植株形态。
- **MushroomFactory**：菌盖可为半球形或伞形，菌柄高矮粗细随机。seed 影响菌盖的曲率和菌柄的比例。

---

## 2. 任务二：基础参数改造

### 2.1 实现方法

从源码里找到对应参数。

为保持除目标参数外其他特征不变，采用“复用同一工厂实例”的策略：
- 先生成 `before`，保存场景和渲染图。
- 不重新实例化，直接修改实例上的对应参数。
- 清空场景后再次调用 `create_asset`，生成 `after` 并保存。

渲染部分使用自动相机（基于物体包围盒计算距离和朝向）和太阳光（强度 2.0），确保前后光照一致。

### 2.2 各改造案例详情

#### 案例 A：TableDiningFactory，seed=13，增大桌面厚度

- **参数名**：`Top Thickness`
![alt text](<屏幕截图 2026-06-04 230730.png>)
- **原始值**：0.048271273882838334（由 `uniform(0.02,0.08)` 随机生成）
- **新值**：0.1
- **修改位置**：`infinigen/assets/objects/tables/dining_table.py` 中的 `self.params` 字典
- **效果**：桌面显著增厚，桌面长宽、材质、桌腿参数未变。
- **对比图**：
![before](task2/A/before.png) ![after](task2/A/after.png)]

#### 案例 B：TableDiningFactory，seed=2，增大桌腿直径

- **参数名**：`Leg Diameter`
![alt text](<屏幕截图 2026-06-04 230739.png>)
- **原始值**：0.056606696420077485
- **新值**：0.15
- **效果**：桌腿明显变粗，桌腿数量（4 根）和桌面形状保持不变。
- **对比图**：
![before](task2/B/before.png) ![after](task2/B/after.png)

#### 案例 C：CeilingClassicLampFactory，seed=23，增大灯罩底部半径

- **参数名**：`bottom_radius`
![alt text](<屏幕截图 2026-06-04 230850.png>)
- **原始值**：0.24873589722401485
- **新值**：0.5
- **效果**：灯罩底部明显扩大，灯罩高度、电缆长度、材质均未变化。
- **对比图**：
![before](task2/C/before.png) ![after](task2/C/after.png)

#### 案例 D：ChairFactory，seed=17，增大靠背高度

- **参数名**：`back_height`
- **原始值**：0.4051193665620454
- **新值**：0.80
- **效果**：靠背显著增高，椅子类型（是否带扶手）、坐面、椅腿、材质均未改变。
- **对比图**：
![before](task2/D/before.png) ![after](task2/D/after.png)

---

## 3. 任务三：进阶改造与失败分析

### 3.1 成功项

#### E. TVFactory – 对 two‑legged 样本增大 leg_width

- **选择 seed**：29（经验证该 seed 生成两条腿的底座）, seed 2为单腿
- **参数定位**：在 `infinigen/assets/objects/appliances/tv.py` 中找到 `self.leg_width` 属性。
- **实现**：复用实例，修改 `leg_width` 修改为到 0.10。
- **结果**：两条腿的间距明显变窄（变为0.1），屏幕材质会同时发生一定的变化。对于 single‑legged 样本（seed=2），`leg_width` 无效，因为生成单腿电视机的分支不会调用 `self.leg_width`。
- **对比图**：
seed=29
![before](task3_/E/seed_29/before.png) ![after](task3_/E/seed_29/after.png)
seed=2
![before](task3_/E/seed_2/before.png) ![after](task3_/E/seed_2/before.png)

#### F. BathtubFactory – 增大 leg_radius（仅限 freestanding + has_legs）

- **选择 seed**：31（该样本为独立式且有腿）seed=59 为方形无腿浴缸
- **参数定位**：`self.leg_radius`
- **实现**：原值约 0.015 改为 0.05。
- **结果**：腿半径增大，浴缸主体未变化。对于无腿的浴缸无变化
- **对比图**：
seed=31
![before](task3_/F/seed_31/before.png) ![after](task3_/F/seed_31/after.png)
seed=59
![before](task3_/F/seed_59/before.png) ![after](task3_/F/seed_59/after.png)


#### G. ChairFactory – 强制有扶手并增大 arm_thickness

- **选择 seed**：1（原始无扶手），17（原始有扶手）
- **实现**：先生成 `before`，然后设置 `has_arm=True` 和 `arm_thickness=0.08`
- **结果**：`after` 出现粗壮的扶手，坐面、椅腿、靠背的随机形态与 `before` 完全一致。对于原本有扶手的情况，也成功让扶手变粗,其他不变。
- **对比图**：
seed=1
![before](task3_/G/seed_1/before.png) ![after](task3_/G/seed_1/after.png)
seed=17
![before](task3_/G/seed_17/before.png) ![after](task3_/G/seed_17/after.png)

#### H. WallShelfFactory – 增加 n_support

- **选择 seed**：4、5、7、20
- **参数定位**：`self.n_support`
- **实现**：复用实例，修改 `n_support` 为 3。
- **结果**：未能成功改变支撑数量，且材质与样式出现较大变化（见下失败分析）。
- **对比图**：
seed=4
![before](task3_/H/seed_4/before.png) ![after](task3_/H/seed_4/after.png)
seed=5
![before](task3_/H/seed_5/before.png) ![after](task3_/H/seed_5/after.png)
seed=7
![before](task3_/H/seed_7/before.png) ![after](task3_/H/seed_7/after.png)
seed=20
![before](task3_/H/seed_20/before.png) ![after](task3_/H/seed_20/after.png)

#### I. BathroomSinkFactory – 修改厚度 (thickness)

- **选择 seed**：1、2、3、14
- **参数**：`thickness` 改为 0.05。
- **结果**：水池边缘成功变厚，但水龙头样式和材质颜色也发生了变化（见下失败分析）。
- **对比图**：
seed=1
![before](task3_/I/seed_1/before.png) ![after](task3_/I/seed_1/after.png)
seed=2
![before](task3_/I/seed_2/before.png) ![after](task3_/I/seed_2/after.png)
seed=3
![before](task3_/I/seed_3/before.png) ![after](task3_/I/seed_3/after.png)
seed=14
![before](task3_/I/seed_14/before.png) ![after](task3_/I/seed_14/after.png)




### 3.2 失败分析

#### (1) TVFactory – single‑legged 样本修改 leg_width 无效

- **尝试**：对 seed=2（单腿）修改 `leg_width`。
- **现象**：腿宽无变化。
- **原因**：阅读源码发现，单腿的粗细由 `leg_diameter` 控制，`leg_width` 仅用于两条腿的情况。这是设计上的参数分支。

#### (2) BathroomSinkFactory – 修改 thickness 导致水龙头和材质改变

- **尝试**：复用同一实例，仅修改 `thickness`。
- **现象**：`after` 的水龙头样式、材质颜色与 `before` 不同。
- **原因分析**：
  - `BathroomSinkFactory` 的 `create_asset` 方法内部使用了 `np.random.randint` 生成水龙头的随机种子（`self.tap_factory(np.random.randint(1e7))`）。
  - 材质生成器 `self.surface_material_gen` 在 `apply` 时也可能依赖全局随机状态。
  - 即使复用实例且种子相同，两次 `create_asset` 调用会因随机数序列偏移而产生不同的水龙头和材质。
  **第一次生成：**
  ![before](task3/I/seed_1/before.png)
  **第二次生成：**
  ![after](task3/I/seed_1/after.png)
  发现即使没有修改参数，使用同一个种子生成出的模型也不同，因此这是其代码内部问题。即使复用实例依然如此。

- **结论**：该工厂的设计未保证 `create_asset` 的幂等性，属于内部随机状态耦合。

#### (3) WallShelfFactory – 修改 n_support 无效

- **尝试**：修改 `n_support` 参数（试图改变支撑数量）。
- **现象**：支撑数量无变化。
- **原因**：源码显示 `n_support` 仅为局部变量，在 `__init__` 中用于计算 `self.support_locs`，未保存为实例属性。`create_asset` 直接使用 `self.support_locs`。
![alt text](image.png)
![alt text](image-1.png)
- **改进建议**：应修改 `self.support_locs` 数组或直接干预随机生成逻辑（如固定随机种子并调整概率参数）。

### 3.3 探索过程中的经验

- **参数定位**：使用 `grep -r "参数名" infinigen/assets/` 结合工厂类名可快速定位。
- **确认参数生效**：采用“复用实例”方法对比修改前后几何差异，无效则阅读源码查证该参数的真实用途。
- **不同工厂的适配差异**：
  - 参数在 `self.params` 字典中的工厂（如桌子、椅子），直接修改字典即可。
  - 参数为实例属性的工厂（如电视的 `leg_width`），直接修改属性。
  - 参数被固化为中间数组的工厂（如墙壁搁架的 `n_support`），需修改更深层的数据结构。
- **确定性问题的发现**：通过两次相同种子独立生成，观察到材质和水龙头变化，揭示了 Infinigen 内部随机状态管理的不完善。这为后续规模化数据生成提供了重要警示。

---

## 4. 任务三进阶：规模化编辑对构建的思考

如果要大规模生成各类 factory 的编辑对数据用于训练（例如几何编辑模型、参数到形状映射等），需构建如下自动化 pipeline：

### 4.1 提取和选择可编辑参数

- **静态代码扫描**：使用 AST 遍历所有工厂类的 `__init__` 方法，收集 `self.params` 字典的键以及直接赋值的数值属性（如 `self.width`、`self.height`）。
- **启发式过滤**：保留类型为 `float`/`int` 且名称包含 `thickness`、`radius`、`height`、`width`、`depth`、`margin` 等几何关键词的参数。
- **有效性验证**：对每个候选参数随机选择 3 个 seed，生成 before/after（修改幅度 ±20%），计算包围盒体积变化率。若变化率 >1%，则标记为有效参数。

### 4.2 确保修改的参数生效

- **确定性生成**：所有生成统一使用“复用工厂实例”模式，避免重新实例化导致的随机链偏移。同时在生成前固定 `random.seed` 和 `np.random.seed`。
- **统一注入接口**：封装 `set_param(factory, key, value)` 函数，自动判断参数在 `params` 字典还是实例属性中。
- **异常处理**：若 `create_asset` 抛出异常（如参数超出有效范围），自动回退到默认值或缩小步长重试。

### 4.3 编辑对质量控制

- **几何质量**：使用 `trimesh` 计算 before/after 的 Hausdorff 距离或包围盒体积变化率，设定阈值（如体积变化 >5%）为合格。
- **视觉质量**：从固定视角渲染低分辨率（256×256）灰度图，计算 SSIM，保留 0.2 < SSIM < 0.9 的样本（变化明显但不至面目全非）。
- **人工抽样**：每 1000 对随机抽取 1 对，在 Blender 中人工检查是否符合语义（例如修改“桌腿直径”应仅改变腿粗，而非影响桌面）。
- **元数据记录**：每个编辑对附带 JSON 文件，包含工厂名、seed、参数名、新旧值、几何差异指标、SSIM、时间戳，便于后续分析与过滤。

---

## 5. AI 使用说明

在本次考核中，我使用了 AI 辅助工具（Deepseek）进行以下工作：
- 帮助分析解决环境依赖问题
- 生成批量脚本的初始框架，以及调试 Blender 自动相机、光照设置的代码。
- 协助分析同种子两次生成结果不一致的可能原因（全局随机状态未隔离）。

所有 AI 提供的代码和建议均在我本人的 WSL 环境中经过手动验证与修改。最终提交的 `.blend` 文件和渲染图均由我运行的脚本生成。报告中的文字由我根据实际探索过程撰写，AI 仅用于语法校对和思路启发。

---

**附件清单**：
- 任务一结果：`task1/` 目录（含所有 `.blend` 与 `.png`）
- 任务二结果：`task2/A/` ～ `task2/D/`（每个目录含 before/after）
- 任务三结果：`task3/E/` ～ `task3/I/`（包含 before/after）
- 本报告 PDF

（所有文件已上传至 Hugging Face 仓库，GitHub 代码仓库链接见邮件）
