from omg.wad import *
from omg.mapedit import *

import math
import struct

import struct_helper

class FixedMapEditor(MapEditor):
    def to_lumps(self):
        m = NameGroup()
        m["_HEADER_"] = Lump("")
        m["VERTEXES"] = Lump(join([x.pack() for x in self.vertexes]))
        m["THINGS"] = Lump(join([x.pack() for x in self.things]))
        m["LINEDEFS"] = Lump(join([x.pack() for x in self.linedefs]))
        m["SIDEDEFS"] = Lump(join([x.pack() for x in self.sidedefs]))
        m["SECTORS"] = Lump(join([x.pack() for x in self.sectors]))
        m["NODES"] = Lump("")
        m["SEGS"] = Lump("")
        m["SSECTORS"] = Lump(join([x.pack() for x in self.ssectors]))
        m["BLOCKMAP"] = Lump("")
        m["REJECT"] = Lump("")
        return m


class MissingLinedefError(BaseException):
    pass


class MapSectionType(object):
    @classmethod
    def load_from_pmst(cls, pmst_filename):
        pmst_file = struct_helper.BinaryFile(pmst_filename)

        # Getting the WAD filename string
        wad_filename = pmst_file.read_binary_string()

        # Getting the map name string
        map_name = pmst_file.read_binary_string()

        # Getting the texture map
        texture_map_size = pmst_file.read_binary("I")[0]
        texture_map = {}

        current_position = texture_map_size

        while current_position > 0:
            texture_name_size = pmst_file.read_binary("I")[0]
            texture_name = pmst_file.read_binary(str(texture_name_size) + "s")[0]
            texture_map[texture_name] = pmst_file.read_binary("i")[0]

            current_position -= 1

        # Getting the flat map
        flat_map_size = pmst_file.read_binary("I")[0]
        flat_map = {}

        current_position = flat_map_size

        while current_position > 0:
            flat_name_size = pmst_file.read_binary("I")[0]
            flat_name = pmst_file.read_binary(str(flat_name_size) + "s")[0]
            flat_map[flat_name] = pmst_file.read_binary("i")[0]

            current_position -= 1

        # Getting the start and end lines
        start_line = pmst_file.read_binary("i")[0]

        num_end_lines = pmst_file.read_binary("H")[0]
        end_lines = []

        current_position = num_end_lines

        while current_position > 0:
            end_lines.append(pmst_file.read_binary("I")[0])

            current_position -= 1

        # Getting the section type
        section_type = pmst_file.read_binary_string()

        # Getting the section's theme
        theme = pmst_file.read_binary_string()

        print "Loaded texture map {} and flat map {}!".format(texture_map, flat_map)

        try:
            return cls(wad_filename, map_name, texture_map, flat_map, start_line, end_lines, section_type, theme)

        except AssertionError:
            print "Missing WAD \'{}\'!".format(wad_filename)
            raise

    def export_to_pmst(self, pmst_filename):
        pmst_file = struct_helper.BinaryFile(pmst_filename, True)

        # Writing the WAD filename string
        pmst_file.write_binary_string(False, self.wad_filename)

        # Writing the map name string
        pmst_file.write_binary_string(False, self.map_name)

        # Writing the texture map
        pmst_file.write_binary(False, "I", len(self.texture_map))

        for texture, number in self.texture_map.items():
            pmst_file.write_binary_string(False, texture)
            pmst_file.write_binary(False, "i", number)

        # Writing the flat map
        pmst_file.write_binary(False, "I", len(self.flat_map))

        for flat, number in self.flat_map.items():
            pmst_file.write_binary_string(False, flat)
            pmst_file.write_binary(False, "i", number)

        # Writing the start and end lines
        pmst_file.write_binary(False, "i", self.start_line_numbers)
        pmst_file.write_binary(False, "H", len(self.end_line_numbers))

        for number in self.end_line_numbers:
            pmst_file.write_binary(False, "I", number)

        # Writing the section type
        pmst_file.write_binary_string(False, self.section_type)

        # Writing the theme
        pmst_file.write_binary_string(False, self.theme)

    def __init__(
            self,
            wad_filename,
            map_name="MAP01",
            texture_map=(),
            flat_map=(),
            start_line=0,
            end_lines=(1,),
            section_type="room",
            theme=None
    ):
        self.section_type = section_type
        self.wad_filename = wad_filename
        self.map_name = map_name
        self.theme = theme
        self.wad_itself = WAD()
        self.wad_itself.from_file(wad_filename)

        self.wad_map = MapEditor(self.wad_itself.maps[map_name])

        self.things = self.wad_map.things
        self.linedefs = self.wad_map.linedefs
        self.sidedefs = self.wad_map.sidedefs
        self.sectors = self.wad_map.sectors

        self.texture_map = dict(texture_map)
        self.flat_map = dict(flat_map)

        for texture in (
                        [sidedef.tx_up for sidedef in self.wad_map.sidedefs] +
                        [sidedef.tx_mid for sidedef in self.wad_map.sidedefs] +
                    [sidedef.tx_low for sidedef in self.wad_map.sidedefs]
        ):
            if texture not in self.texture_map.keys():
                print "Warning: Texture {} not in texture map! Only textures present: {}".format(
                    texture,
                    ", ".join(self.texture_map.keys())
                )
                self.texture_map[texture] = -1

        for flat in (
                    [sector.tx_floor for sector in self.wad_map.sectors] +
                    [sector.tx_ceil for sector in self.wad_map.sectors]
        ):
            if flat not in self.flat_map.keys():
                print "Warning: Flat {} not in flat map! Only flats present: {}".format(
                    flat,
                    ", ".join(self.flat_map.keys())
                )
                self.flat_map[flat] = -1

        try:
            if start_line != -1:
                self.has_start_line = True
                self.start_line_numbers = start_line
                self.start_line = self.wad_map.linedefs[start_line]
                a = self.wad_map.vertexes[self.start_line.vx_a]
                b = self.wad_map.vertexes[self.start_line.vx_b]
                self.start_width = math.sqrt(abs((b.x - a.x) ** 2 + (b.y - a.y) ** 2))
                self.start_line.impassable = False
                self.start_line.two_sided = True

            else:
                self.has_start_line = False
                self.start_line = -1

        except IndexError:
            raise MissingLinedefError("The linedef {} of map {} in WAD {} is missing as a map section's"
                                      " start line!".format(
                start_line,
                map_name,
                wad_filename
            ))

        try:
            self.end_line_numbers = end_lines
            self.end_lines = [self.wad_map.linedefs[line] for line in end_lines]

            self.end_widths = []

            for line in self.end_lines:
                a = self.wad_map.vertexes[line.vx_a]
                b = self.wad_map.vertexes[line.vx_b]
                self.end_widths.append(math.sqrt(abs((b.x - a.x) ** 2 + (b.y - a.y) ** 2)))

        except IndexError:
            raise MissingLinedefError("The linedef {} of map {} in WAD {} is missing as a map section's"
                                      "end line!".format(
                line,
                map_name,
                wad_filename
            ))

        self.section_top_left_coordinates = [float("inf")] * 2
        self.section_size = [float("-inf")] * 2

        for vertex in self.wad_map.vertexes:
            if vertex.x < self.section_top_left_coordinates[0]:
                self.section_top_left_coordinates[0] = vertex.x

            if vertex.y < self.section_top_left_coordinates[1]:
                self.section_top_left_coordinates[1] = vertex.y

            if vertex.x + self.section_top_left_coordinates[0] > self.section_size[0]:
                self.section_size[0] = vertex.x + self.section_top_left_coordinates[0]

            if vertex.y + self.section_top_left_coordinates[1] > self.section_size[1]:
                self.section_size[1] = vertex.y + self.section_top_left_coordinates[1]

        sl = start_line
        els = end_lines

        def l(n):
            # type: (int) -> Linedef

            return self.wad_map.linedefs[n]

        def v(n):
            # type: (int) -> Vertex

            return self.wad_map.vertexes[n]

        self.start_angle, self.exit_angles = (
            angle_between([v(l(sl).vx_a).x, v(l(sl).vx_a).y], [v(l(sl).vx_b).x, v(l(sl).vx_b).y]),
            [angle_between(a, b) for (a, b) in
             [[(v(vertex).x, v(vertex).y) for vertex in (l(line).vx_a, l(line).vx_b)] for line in els]]
        )

        for line in tuple((self.wad_map.linedefs[i] for i in end_lines)) + (self.wad_map.linedefs[start_line],):
            line.impassable = False
            line.double_sided = True


def angle_between(a, b):
    # type: (iter(float, float), iter(float, float)) -> float
    """
    Measures the angle from point a to point b.
    Point a and b both have the structure of an iterator (point's x coordinate, point's y coordinate).

    :rtype: float
    :param a: The origin point to measure angle from.
    :param b: The point to measure angle to.
    :return: The angle between them, duh. More specifically, a float in degrees.
    """
    c_x = b[0] - a[0]
    c_y = b[1] - a[1]

    return math.degrees(math.atan2(c_x, c_y))
