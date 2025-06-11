import bpy
from .util import Const, find_level_asset_coll

#TODO: 批量选择同样class的对象
#TODO：设置 bpy.context.object.color 
#TODO: 设置bl显示模式




# class SetObjectColorByClassOperator(bpy.types.Operator):
#     bl_idname = "ubio.set_object_color_by_class"
#     bl_label = "Set Object Color By Class"
#     bl_description = "根据Class属性为所有Level Asset对象设置随机颜色。"
#     bl_options = {'REGISTER', 'UNDO'}

#     def execute(self, context):
#         level_asset_coll = find_level_asset_coll(Const.UECOLL, Const.COLL_LEVEL)
#         if not level_asset_coll:
#             self.report({'WARNING'}, "未找到 Level Asset Collection。请确保场景中存在UnrealIO/Level集合。")
#             return {'CANCELLED'}

#         # 根据ACTORCLASS对对象进行分组
#         class_objects = {}
#         for obj in level_asset_coll.objects:
#             if Const.ACTORCLASS in obj:
#                 actor_class = obj[Const.ACTORCLASS]
#                 if actor_class not in class_objects:
#                     class_objects[actor_class] = []
#                 class_objects[actor_class].append(obj)

#         # 为每个Class生成一个随机颜色，并设置对象颜色
#         import random
#         assigned_colors = set()
#         colors_set_count = 0

#         for actor_class, objects in class_objects.items():
#             # 生成一个独特的随机颜色
#             color = (random.random(), random.random(), random.random(), 1.0)
#             # 确保颜色在一定程度上是独特的，避免过于相近的颜色
#             while color in assigned_colors:
#                 color = (random.random(), random.random(), random.random(), 1.0)
            
#             assigned_colors.add(color)

#             for obj in objects:
#                 obj.color=color
#                 colors_set_count += 1

#         if colors_set_count > 0:
#             bpy.context.space_data.shading.color_type = 'OBJECT'
#             bpy.context.space_data.shading.type = 'SOLID'
#             bpy.context.space_data.shading.light = 'MATCAP'

#             self.report({'INFO'}, f"成功为 {len(class_objects)} 种不同 Class 的 {colors_set_count} 个对象设置了颜色。")
#             return {"FINISHED"}
#         else:
#             self.report({'INFO'}, "没有找到带有Class属性的对象或没有设置颜色。")
#             return {'CANCELLED'}


