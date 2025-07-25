# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import bpy
from . import auto_load
from bpy.props import PointerProperty
from .UI import UIParams

auto_load.init()


def register():
    auto_load.register()
    bpy.types.Scene.ubio_params = PointerProperty(type=UIParams)


def unregister():
    auto_load.unregister()
    del bpy.types.Scene.ubio_params


auto_load.init()


